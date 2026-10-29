import asyncio
import logging
from collections.abc import AsyncIterator
from time import perf_counter
from uuid import UUID

import anyio

from app.core.config import settings
from app.util.token_counter import count_tokens
from app.modules.chatbot.schemas.security.principal import PrincipalContext, RequestContext
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.schemas.inbound import InboundRequest
from app.modules.chatbot.clarification import update_conversation_state
from app.modules.chatbot.orchestration import select_direct_response_code
from app.modules.chatbot.prompts.direct_responses import get_direct_response
from app.modules.chatbot.providers.handoff import DisabledHandoffProvider, HandoffProvider
from app.modules.chatbot.schemas.system import (
    ConversationState,
    Mode,
    RunState,
    RetrievalScope,
    TaskKind,
    TaskStatus,
)
from app.modules.chatbot.stages.prune_stage import Prune
from app.modules.chatbot.stages.context_loader import ContextLoader
from app.modules.chatbot.stages.security import SecurityBlockedError, SecurityStage
from app.modules.chatbot.stages.security import get_response_message, normalize_locale
from app.modules.chatbot.stages.analysis_stage import AnalysisStage
from app.modules.chatbot.schemas.system.security import SecurityAction
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from app.modules.chatbot.stages.answer_composer import AnswerComposer
from app.modules.chatbot.stages.clarification_resume_stage import ClarificationResumeStage
from app.util.normalize import guess_reply_language

logger = logging.getLogger(__name__)


class ChatbotService:
    def __init__(
        self,
        provider: OpenAIProvider,
        history_repository: HistoryRepository,
        security_stage: SecurityStage | None = None,
        context_loader: ContextLoader | None = None,
        prune: Prune | None = None,
        analysis_stage: AnalysisStage | None = None,
        execution_stage: ExecutionStage | None = None,
        answer_composer: AnswerComposer | None = None,
        clarification_stage: ClarificationResumeStage | None = None,
        handoff_provider: HandoffProvider | None = None,
    ) -> None:
        self._provider = provider
        self._history_repository = history_repository
        self._security_stage = security_stage or SecurityStage()
        self._context_loader = context_loader or ContextLoader(history_repository)
        self._prune = prune or Prune(settings.context_token_budget)
        self._analysis_stage = analysis_stage or AnalysisStage(provider)
        self._execution_stage = execution_stage or ExecutionStage()
        self._answer_composer = answer_composer or AnswerComposer(provider)
        self._clarification_stage = clarification_stage or ClarificationResumeStage()
        self._handoff_provider = handoff_provider or DisabledHandoffProvider()

    async def stream_reply(
        self,
        inbound: InboundRequest,
        principal: PrincipalContext,
        request_context: RequestContext,
    ) -> AsyncIterator[str]:
        started_at = perf_counter()
        message = inbound.message.text
        session_id = UUID(inbound.session.session_id)
        locale = inbound.client_context.locale if inbound.client_context else None
        channel = inbound.channel.type.value
        # Cột chung cho mọi bản ghi của lượt này (completed/error/blocked).
        turn_ids = {
            "history_id": UUID(inbound.message.message_id),
            "idempotency_key": inbound.message.idempotency_key,
        }
        security_decision = self._security_stage.inspect(message)
        if security_decision.action is SecurityAction.BLOCK:
            # Chặn trước khi nạp context: chỉ có locale của client hoặc heuristic,
            # không gửi nội dung bị chặn tới LLM chỉ để biết ngôn ngữ.
            reply_language = normalize_locale(locale) if locale else guess_reply_language(message)
            await self._history_repository.create_blocked(
                session_id=session_id,
                query_origin=message,
                answer=get_response_message("request_blocked", reply_language),
                latency_ms=round((perf_counter() - started_at) * 1000),
                channel=channel,
                **turn_ids,
            )
            raise SecurityBlockedError(security_decision, reply_language)

        # Theo dõi lượt để ghi status='cancelled' khi client ngắt giữa chừng.
        answer_parts: list[str] = []
        state: RunState | None = None
        finalized = False
        try:
            state = RunState(
                input=inbound,
                principal=principal,
                request_context=request_context,
                security=security_decision,
            )
            load_context_time = perf_counter()
            context = await self._context_loader.execute(state)
            context = self._prune.execute(context, self._provider.model)
            logger.debug("context loaded in %.2fs", perf_counter() - load_context_time)
            state.context = context
            state.context_status = "pruned"

            conversation_state = context.conversation.state
            if conversation_state.mode is not Mode.BOT:
                # A human agent owns the conversation: the bot does not answer.
                answer = get_direct_response(
                    "agent.active" if conversation_state.mode is Mode.WITH_AGENT else "agent.awaiting",
                    conversation_state.language
                    or _locale_language(locale)
                    or guess_reply_language(message),
                )
                answer_parts.append(answer)
                yield answer
                await self._history_repository.create(
                    session_id=session_id,
                    query_origin=message,
                    answer=answer,
                    status="completed",
                    model=None,
                    latency_ms=round((perf_counter() - started_at) * 1000),
                    conversation_state=conversation_state.model_dump(mode="json"),
                    channel=channel,
                    **turn_ids,
                )
                finalized = True
                return

            # Mọi lỗi sau khi đã nạp context (analysis, execution, compose, stream)
            # đều để lại một bản ghi status='error' rồi mới ném tiếp cho router.
            try:
                analysis_time = perf_counter()
                await self._clarification_stage.execute(state)
                await self._analysis_stage.execute(state)
                self._clarification_stage.apply_attempt_limit(state)
                await self._execution_stage.execute(state)
                # Chỉ log số liệu định tuyến, không log câu hỏi/analysis đầy đủ.
                logger.debug(
                    "analysis+execution in %.2fs intents=%s routes=%s tasks=%s",
                    perf_counter() - analysis_time,
                    [sub_query.intent for sub_query in state.analysis.sub_queries],
                    [sub_query.route.value for sub_query in state.analysis.sub_queries],
                    [f"{task.kind.value}:{task.status.value}" for task in state.plan.tasks],
                )

                assert state.plan is not None and state.analysis is not None
                # Ngôn ngữ trả lời: analysis -> ngôn ngữ của phiên -> locale client -> vi.
                language = (
                    state.analysis.language
                    or conversation_state.language
                    or _locale_language(locale)
                    or "vi"
                )
                context.query.language = language
                direct_code = select_direct_response_code(state.plan, language)
                if direct_code is not None:
                    answer_parts.append(get_direct_response(direct_code, language))
                    yield answer_parts[0]
                else:
                    async for chunk in self._answer_composer.stream(state):
                        answer_parts.append(chunk)
                        yield chunk

                next_state = await self._transfer_handoff(
                    state,
                    session_id,
                    update_conversation_state(state),
                )
            except Exception:
                answer = "".join(answer_parts)
                await self._history_repository.create(
                    session_id=session_id,
                    query_origin=message,
                    answer=answer or None,
                    status="error",
                    model=self._provider.model,
                    latency_ms=round((perf_counter() - started_at) * 1000),
                    channel=channel,
                    **turn_ids,
                    normalized_query=_normalized_query(state),
                    retrieval_snapshot=self._retrieval_snapshot(state),
                    **self._usage(message, answer),
                )
                finalized = True
                raise

            answer = "".join(answer_parts)
            await self._history_repository.create(
                session_id=session_id,
                query_origin=message,
                answer=answer,
                status="completed",
                model=self._provider.model,
                latency_ms=round((perf_counter() - started_at) * 1000),
                conversation_state=next_state.model_dump(mode="json"),
                channel=channel,
                **turn_ids,
                normalized_query=_normalized_query(state),
                retrieval_snapshot=self._retrieval_snapshot(state),
                **self._usage(message, answer),
            )
            finalized = True
        except (asyncio.CancelledError, GeneratorExit):
            # Client ngắt kết nối: Starlette huỷ task (CancelledError) hoặc đóng
            # generator (GeneratorExit). Không lọt vào except Exception ở trên.
            if not finalized:
                await self._record_cancelled(
                    state,
                    session_id=session_id,
                    message=message,
                    channel=channel,
                    turn_ids=turn_ids,
                    answer="".join(answer_parts),
                    started_at=started_at,
                )
            raise

    def _retrieval_snapshot(self, state: RunState) -> dict:
        """Chunk đã chọn của lượt này, xếp theo score giảm dần cho màn Kết quả chunk."""
        hits = [
            hit
            for task in (state.plan.tasks if state.plan else [])
            if task.result is not None and task.result.retrieval is not None
            for result in task.result.retrieval.results
            for hit in result.hits
        ]
        hits.sort(key=lambda hit: hit.score, reverse=True)
        status, retrieval_tasks = retrieval_status(state.plan.tasks if state.plan else [])
        if status in ("error", "partial_error"):
            logger.warning(
                "retrieval failed status=%s session_id=%s failed_tasks=%d",
                status,
                state.input.session.session_id,
                sum(1 for task in retrieval_tasks if task["status"] == TaskStatus.FAILED.value),
            )
        return {
            "query": state.input.message.text,
            # Lỗi tra cứu không ném lên client (LLM trả lời mềm): lưu lại để truy vết.
            "retrieval_status": status,
            "retrieval_tasks": retrieval_tasks,
            "model": self._provider.model,
            "product_models": list(dict.fromkeys(
                model
                for trace in state.retrieval_traces
                for model in trace.params.filters.product_models or []
            )),
            "latency_ms": max((trace.latency_ms for trace in state.retrieval_traces), default=0),
            "chunks": [
                {
                    "rank": rank,
                    "score": hit.score,
                    "content": hit.content,
                    "domain": hit.domain,
                    "scopes": hit.scopes,
                    "control_interface": hit.control_interface,
                    "spec_attributes": hit.spec_attributes,
                    "page_start": hit.page_start,
                    "page_end": hit.page_end,
                    "page_label": _page_label(hit.page_start, hit.page_end),
                }
                for rank, hit in enumerate(hits, start=1)
            ],
        }

    async def _record_cancelled(
        self,
        state: RunState | None,
        *,
        session_id: UUID,
        message: str,
        channel: str,
        turn_ids: dict,
        answer: str,
        started_at: float,
    ) -> None:
        """Ghi lượt bị client ngắt bằng session DB riêng (session của request bị rollback).

        Shield để lệnh ghi không bị huỷ theo task; không ghi conversation_state vì
        lượt chưa hoàn tất. Lỗi ghi chỉ log, không che exception huỷ gốc.
        """
        logger.warning(
            "chat turn cancelled by client session_id=%s answer_chars=%d",
            session_id,
            len(answer),
        )
        try:
            with anyio.CancelScope(shield=True):
                await self._history_repository.create_audit(
                    status="cancelled",
                    session_id=session_id,
                    query_origin=message,
                    answer=answer or None,
                    model=self._provider.model,
                    latency_ms=round((perf_counter() - started_at) * 1000),
                    channel=channel,
                    **turn_ids,
                    normalized_query=_normalized_query(state) if state else None,
                    retrieval_snapshot=self._retrieval_snapshot(state) if state else None,
                    **self._usage(message, answer),
                )
        except Exception:
            logger.exception("failed to record cancelled chat turn session_id=%s", session_id)

    def _usage(self, message: str, answer: str) -> dict:
        # Ước tính từ câu hỏi và câu trả lời; chưa gồm prompt/context gửi LLM và embedding.
        input_tokens = count_tokens(message, self._provider.model)
        output_tokens = count_tokens(answer, self._provider.model)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(
                (
                    input_tokens * settings.gpt4o_mini_input_usd_per_million
                    + output_tokens * settings.gpt4o_mini_output_usd_per_million
                )
                / 1_000_000,
                8,
            ),
        }

    async def _transfer_handoff(
        self,
        state: RunState,
        session_id: UUID,
        conversation_state: ConversationState,
    ) -> ConversationState:
        """Hand the conversation to an agent when a handoff task was produced."""
        assert state.plan is not None and state.context is not None
        task = next(
            (task for task in state.plan.tasks if task.status is TaskStatus.HANDED_OFF),
            None,
        )
        if task is None:
            return conversation_state
        reason = (task.result.metadata.get("handoff_reason") if task.result else None)
        ticket = await self._handoff_provider.transfer(
            session_id,
            state.context.conversation.history,
            reason or "human_request",
        )
        if ticket is None:
            # No agent platform connected: stay in bot mode.
            return conversation_state
        return conversation_state.model_copy(update={
            "mode": ticket.mode,
            "ticket_id": ticket.ticket_id,
        })


def retrieval_status(tasks) -> tuple[str, list[dict]]:
    """Trạng thái tra cứu của lượt và chi tiết từng task retrieve (không chứa nội dung).

    not_applicable: không có task retrieve · ok · no_hits: mọi task không có kết quả ·
    partial_error / error: một phần / mọi task lỗi · incomplete: có task chưa chạy xong.
    """
    rows = []
    for task in tasks:
        if task.kind is not TaskKind.RETRIEVE:
            continue
        result = task.result
        metadata = result.metadata if result else {}
        rows.append({
            "task_id": task.task_id,
            "status": task.status.value,
            "error_code": result.error.code if result and result.error else None,
            "no_hits": metadata.get("no_hits") == "true",
            "fallback": metadata.get("fallback") == "true",
        })
    if not rows:
        return "not_applicable", rows
    failed = sum(1 for row in rows if row["status"] == TaskStatus.FAILED.value)
    completed = sum(1 for row in rows if row["status"] == TaskStatus.COMPLETED.value)
    if failed == len(rows):
        status = "error"
    elif failed:
        status = "partial_error"
    elif completed < len(rows):
        status = "incomplete"
    elif all(row["no_hits"] for row in rows):
        status = "no_hits"
    else:
        status = "ok"
    return status, rows


def _locale_language(locale: str | None) -> str | None:
    """Mã ngôn ngữ từ locale client (vd. vi-VN -> vi); locale đã được validate ở schema."""
    return locale.strip().lower().replace("_", "-").split("-", 1)[0] if locale else None


def _normalized_query(state: RunState) -> str | None:
    """Câu hỏi đã chuẩn hóa (tiếng Việt) của các sub-query, lưu log ở chat_history."""
    if state.analysis is None:
        return None
    return "\n".join(sub_query.standalone_query for sub_query in state.analysis.sub_queries)


def _page_label(page_start: int | None, page_end: int | None) -> str | None:
    if not page_start:
        return None
    if not page_end or page_end == page_start:
        return f"page {page_start}"
    return f"page {page_start} - {page_end}"
