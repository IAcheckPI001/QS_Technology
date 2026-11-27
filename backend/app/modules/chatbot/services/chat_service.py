import asyncio
import logging
from collections.abc import AsyncIterator
from time import perf_counter
from typing import TYPE_CHECKING
from uuid import UUID

import anyio

from app.core.config import settings
from app.core.pricing import cost_usd, price_for
from app.core.tracing import current_trace, set_root, span
from app.modules.chatbot.services.turn_errors import turn_error
from app.modules.chatbot.services.turn_sources import turn_flags
from app.modules.chatbot.services.turn_usage import USAGE_SOURCE_ESTIMATE, TurnUsage, usage_from_trace
from app.util.token_counter import count_tokens
from app.modules.chatbot.schemas.security.principal import PrincipalContext, RequestContext
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.schemas.inbound import InboundRequest
from app.modules.chatbot.tools.product_docs import product_docs_plans
from app.modules.chatbot.clarification import (
    update_agent_conversation_state,
    update_conversation_state,
)
from app.modules.chatbot.orchestration import select_direct_response_code
from app.modules.chatbot.prompts.direct_responses import get_direct_response
from app.modules.chatbot.providers.handoff import DisabledHandoffProvider, HandoffProvider
from app.modules.chatbot.providers.supabase_storage import AssetSigner
from app.modules.chatbot.sources import SourceItem, build_sources
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.system import (
    ConversationState,
    ExecutionPlan,
    Mode,
    RunState,
    TaskKind,
    TaskStatus,
)
from app.modules.chatbot.stages.prune_stage import Prune
from app.modules.chatbot.stages.context_loader import ContextLoader
from app.modules.chatbot.stages.security import SecurityBlockedError, SecurityStage
from app.modules.chatbot.stages.security import get_response_message, normalize_locale
from app.modules.chatbot.stages.analysis_stage import AnalysisStage
from app.modules.chatbot.schemas.system.security import SecurityAction, SecurityDecision
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from app.modules.chatbot.stages.answer_composer import AnswerComposer
from app.modules.chatbot.stages.clarification_resume_stage import ClarificationResumeStage
from app.modules.chatbot.stages.retrieval_pipeline import RetrievalPipeline
from app.util.normalize import guess_reply_language

if TYPE_CHECKING:
    from app.modules.chatbot.agent import AgentRunner

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
        agent_runner: "AgentRunner | None" = None,
        asset_signer: AssetSigner | None = None,
        source_images_max: int = 3,
    ) -> None:
        self._provider = provider
        self._history_repository = history_repository
        self._security_stage = security_stage or SecurityStage()
        self._context_loader = context_loader or ContextLoader(
            history_repository, history_turns=settings.context_history_turns,
        )
        self._prune = prune or Prune(settings.context_token_budget)
        self._analysis_stage = analysis_stage or AnalysisStage(provider)
        self._execution_stage = execution_stage or ExecutionStage()
        self._answer_composer = answer_composer or AnswerComposer(provider)
        self._clarification_stage = clarification_stage or ClarificationResumeStage()
        self._handoff_provider = handoff_provider or DisabledHandoffProvider()
        self._retrieval_pipeline = RetrievalPipeline(
            self._clarification_stage,
            self._analysis_stage,
            self._execution_stage,
        )
        # Chỉ được inject khi CRM_CHAT_FLOW=agent; không có thì CRM chạy pipeline cũ.
        self._agent_runner = agent_runner
        # Nguồn đã trích dẫn kèm ảnh của lượt; router phát thành event SSE `sources` sau khi hết `delta`.
        # Rỗng khi tính năng tắt (không có signer) hoặc không có trích dẫn.
        self._asset_signer = asset_signer
        self._source_images_max = source_images_max
        self.turn_sources: list[SourceItem] = []

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
        with span("stage.security", "stage") as security_span:
            security_decision = self._security_stage.inspect(message)
            security_span.set(**security_attributes(security_decision))
        if security_decision.action is SecurityAction.BLOCK:
            # Chặn trước khi nạp context: chỉ có locale của client hoặc heuristic,
            # không gửi nội dung bị chặn tới LLM chỉ để biết ngôn ngữ.
            reply_language = normalize_locale(locale) if locale else guess_reply_language(message)
            set_root(flow="blocked", history_status="blocked")
            with span("history.write", "db", history_status="blocked"):
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
            with span("stage.context_load", "stage") as load_span:
                context = await self._context_loader.execute(state)
                load_span.set(history_messages=len(context.conversation.history))
            with span("stage.prune", "stage") as prune_span:
                context = self._prune.execute(context, self._provider.model)
                prune_span.set(history_messages=len(context.conversation.history))
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
                set_root(flow="human_agent_mode", history_status="completed")
                yield answer
                with span("history.write", "db", history_status="completed"):
                    state_json = conversation_state.model_dump(mode="json")
                    await self._history_repository.create(
                        session_id=session_id,
                        query_origin=message,
                        answer=answer,
                        status="completed",
                        model=None,
                        latency_ms=round((perf_counter() - started_at) * 1000),
                        conversation_state=state_json,
                        channel=channel,
                        **turn_ids,
                        **turn_flags(None, state_json),
                    )
                finalized = True
                return

            # Mọi lỗi sau khi đã nạp context (analysis, execution, compose, stream)
            # đều để lại một bản ghi status='error' rồi mới ném tiếp cho router.
            try:
                if self._agent_runner is not None and request_context.channel is ChannelType.CRM:
                    set_root(flow="agent")
                    # Kênh CRM: agent tự gọi tool tra cứu. Conversation state chỉ cập nhật
                    # ngữ cảnh model (không pending, không handoff sang người thật).
                    async for chunk in self._agent_runner.run(state):
                        answer_parts.append(chunk)
                        yield chunk
                    next_state = update_agent_conversation_state(state, [
                        model
                        for tool_plan in product_docs_plans(state.agent)
                        for model in tool_plan.product_models
                    ])
                else:
                    set_root(flow="pipeline")
                    analysis_time = perf_counter()
                    await self._retrieval_pipeline.run(state)
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
                        set_root(direct_response=direct_code)
                        # Span ngắn cho dòng hoạt động: trả lời cố định (chào hỏi, hỏi lại, chuyển nhân viên…).
                        with span("stage.direct", "stage", code=direct_code):
                            answer_parts.append(get_direct_response(direct_code, language))
                        yield answer_parts[0]
                    else:
                        with span("stage.compose", "stage"):
                            async for chunk in self._answer_composer.stream(state):
                                answer_parts.append(chunk)
                                yield chunk

                    next_state = await self._transfer_handoff(
                        state,
                        session_id,
                        update_conversation_state(state),
                    )
            except Exception as error:
                answer = "".join(answer_parts)
                set_root(history_status="error")
                with span("history.write", "db", history_status="error"):
                    await self._history_repository.create(
                        session_id=session_id,
                        query_origin=message,
                        answer=answer or None,
                        status="error",
                        model=self._turn_model(state),
                        latency_ms=round((perf_counter() - started_at) * 1000),
                        channel=channel,
                        **turn_ids,
                        normalized_query=_normalized_query(state),
                        **self._turn_record(state, message, answer, error=error),
                    )
                finalized = True
                raise

            answer = "".join(answer_parts)
            await self._collect_sources(state, answer)
            set_root(history_status="completed")
            with span("history.write", "db", history_status="completed"):
                await self._history_repository.create(
                    session_id=session_id,
                    query_origin=message,
                    answer=answer,
                    status="completed",
                    model=self._turn_model(state),
                    latency_ms=round((perf_counter() - started_at) * 1000),
                    channel=channel,
                    **turn_ids,
                    normalized_query=_normalized_query(state),
                    **self._turn_record(state, message, answer, next_state.model_dump(mode="json")),
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

    async def _collect_sources(self, state: RunState, answer: str) -> None:
        """Dựng `turn_sources` từ chunk được trích dẫn. Lỗi ở đây không được làm hỏng câu trả lời đã stream."""
        self.turn_sources = []
        if self._asset_signer is None:
            return
        try:
            hits = [
                hit
                for _, plan in _executed_plans(state)
                for task in plan.tasks
                if task.result is not None and task.result.retrieval is not None
                for result in task.result.retrieval.results
                for hit in result.hits
            ]
            with span("sources.build", "internal") as sources_span:
                self.turn_sources = await build_sources(
                    _unique_hits(hits), answer, self._asset_signer, max_images=self._source_images_max)
                sources_span.set(sources=len(self.turn_sources),
                                 images=sum(len(item.images) for item in self.turn_sources))
        except Exception:
            logger.exception("building sources failed session_id=%s", state.input.session.session_id)
            self.turn_sources = []

    def _retrieval_snapshot(self, state: RunState) -> dict:
        """Chunk đã chọn của lượt này, xếp theo score giảm dần cho màn Kết quả chunk."""
        plans = _executed_plans(state)
        tasks = [task for _, plan in plans for task in plan.tasks]
        hits = [
            hit
            for task in tasks
            if task.result is not None and task.result.retrieval is not None
            for result in task.result.retrieval.results
            for hit in result.hits
        ]
        hits.sort(key=lambda hit: hit.score, reverse=True)
        hits = _unique_hits(hits)
        status, retrieval_tasks = retrieval_status(tasks)
        # Root trace: lọc được lượt trả lời không có tài liệu (no_hits) hay tra cứu lỗi.
        set_root(retrieval_status=status)
        # Luồng agent: nhiều lần tra cứu có cùng task_id, gắn tool_call_id để phân biệt.
        prefixes = [
            prefix
            for prefix, plan in plans
            for task in plan.tasks
            if task.kind is TaskKind.RETRIEVE
        ]
        for row, prefix in zip(retrieval_tasks, prefixes):
            if prefix:
                row["task_id"] = f"{prefix}:{row['task_id']}"
        if status in ("error", "partial_error"):
            logger.warning(
                "retrieval failed status=%s session_id=%s failed_tasks=%d",
                status,
                state.input.session.session_id,
                sum(1 for task in retrieval_tasks if task["status"] == TaskStatus.FAILED.value),
            )
        snapshot = {
            "query": state.input.message.text,
            # Lỗi tra cứu không ném lên client (LLM trả lời mềm): lưu lại để truy vết.
            "retrieval_status": status,
            "retrieval_tasks": retrieval_tasks,
            "model": self._turn_model(state),
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
                    # Nguồn của đoạn cho màn "Nguồn câu trả lời" (FRONTEND_REQUIREMENTS 19.15, W1).
                    # source_id (S1…) khớp trích dẫn trong câu trả lời.
                    "chunk_id": _as_text(getattr(hit, "chunk_id", None)),
                    "doc_id": getattr(hit, "doc_id", None),
                    "section_title": getattr(hit, "section_title", None),
                    "section_path": list(getattr(hit, "section_path", None) or []),
                    "source_id": getattr(hit, "source_id", None),
                    # WU-17 đợt 2: độ giống cosine (hiện ×10) và tham chiếu ảnh (bucket/path/trang, không phải URL);
                    # URL ký được cấp lại mỗi lần đọc lượt.
                    "similarity": getattr(hit, "similarity", None),
                    "assets": [asset.model_dump(mode="json") for asset in getattr(hit, "assets", None) or []],
                }
                for rank, hit in enumerate(hits, start=1)
            ],
        }
        agent = getattr(state, "agent", None)
        if agent is not None:
            # Nội bộ: trace từng bước của agent (không chứa nội dung tin nhắn/tool output).
            snapshot["agent_steps"] = [step.model_dump(mode="json") for step in agent.steps]
            snapshot["answered_without_tools"] = agent.answered_without_tools
            snapshot["invalid_citations"] = list(agent.invalid_citations)
            snapshot["final_reason"] = agent.final_reason
        return snapshot

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
        set_root(history_status="cancelled")
        try:
            with anyio.CancelScope(shield=True), span("history.write", "db", history_status="cancelled"):
                await self._history_repository.create_audit(
                    status="cancelled",
                    session_id=session_id,
                    query_origin=message,
                    answer=answer or None,
                    model=self._turn_model(state),
                    latency_ms=round((perf_counter() - started_at) * 1000),
                    channel=channel,
                    **turn_ids,
                    normalized_query=_normalized_query(state) if state else None,
                    **self._turn_record(state, message, answer),
                )
        except Exception:
            logger.exception("failed to record cancelled chat turn session_id=%s", session_id)

    def _turn_model(self, state: RunState | None) -> str:
        """Model trả lời của lượt: model của vòng lặp agent (AGENT_MODEL) ở lượt CRM chạy agent."""
        if (
            self._agent_runner is not None
            and state is not None
            and state.request_context.channel is ChannelType.CRM
        ):
            return self._agent_runner.model
        return self._provider.model

    def _usage(self, message: str, answer: str) -> TurnUsage:
        """Usage thật của lượt từ trace đang chạy (B3); không có trace thì ước tính như cũ."""
        trace = current_trace()
        if trace is not None:
            return usage_from_trace(trace, settings.llm_price_overrides)
        # Ước tính từ câu hỏi và câu trả lời; chưa gồm prompt/context gửi LLM và embedding.
        input_tokens = count_tokens(message, self._provider.model)
        output_tokens = count_tokens(answer, self._provider.model)
        # Giá theo model đang trả lời (core/pricing.py, có ghi đè LLM_PRICES_JSON); model lạ thì tính theo gpt-4o-mini.
        price = price_for(self._provider.model, settings.llm_price_overrides) or price_for("gpt-4o-mini")
        cost = cost_usd(price, input_tokens=input_tokens, output_tokens=output_tokens)
        return TurnUsage(
            source=USAGE_SOURCE_ESTIMATE, input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost,
        )

    def _turn_record(
        self,
        state: RunState | None,
        message: str,
        answer: str,
        conversation_state: dict | None = None,
        error: BaseException | None = None,
    ) -> dict:
        """Snapshot tra cứu (kèm chi tiết usage), các cột token/chi phí và cờ B2 cho một dòng
        chat_history. `conversation_state` chỉ có ở lượt completed và cũng được ghi vào dòng.
        `error`: lượt lỗi ghi mã lỗi vào snapshot (WU-17 đợt 2), lượt chưa có state vẫn có snapshot."""
        usage = self._usage(message, answer)
        snapshot = self._retrieval_snapshot(state) if state is not None else None
        if error is not None:
            snapshot = snapshot if snapshot is not None else {"query": message, "chunks": []}
            snapshot["error"] = turn_error(error)
        if snapshot is not None:
            snapshot["usage"] = usage.detail()
        record = {"retrieval_snapshot": snapshot, **usage.columns(), **turn_flags(snapshot, conversation_state)}
        if conversation_state is not None:
            record["conversation_state"] = conversation_state
        return record

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
        with span("handoff.transfer", "internal", reason=reason or "human_request") as handoff_span:
            ticket = await self._handoff_provider.transfer(
                session_id,
                state.context.conversation.history,
                reason or "human_request",
            )
            # no_provider: chưa nối nền tảng nhân viên, phiên giữ chế độ bot.
            handoff_span.set(
                result="transferred" if ticket is not None else "no_provider",
                mode=ticket.mode.value if ticket is not None else None,
            )
        set_root(handoff="transferred" if ticket is not None else "no_provider")
        if ticket is None:
            # No agent platform connected: stay in bot mode.
            return conversation_state
        return conversation_state.model_copy(update={
            "mode": ticket.mode,
            "ticket_id": ticket.ticket_id,
        })


def security_attributes(decision: SecurityDecision) -> dict[str, object]:
    """Thuộc tính trace của quyết định security: mã luật/nhóm, không có nội dung tin nhắn."""
    attributes: dict[str, object] = {
        "action": decision.action.value,
        "policy_version": decision.policy_version,
    }
    if decision.findings:
        attributes.update(
            rule_ids=list(dict.fromkeys(finding.rule_id for finding in decision.findings)),
            categories=list(dict.fromkeys(finding.category for finding in decision.findings)),
            highest_severity=(
                decision.highest_severity.value if decision.highest_severity else None
            ),
        )
    return attributes


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


def _executed_plans(state: RunState) -> list[tuple[str | None, ExecutionPlan]]:
    """Plan đã chạy của lượt: plan của pipeline, hoặc plan của từng lần agent gọi tra cứu."""
    agent = getattr(state, "agent", None)
    if agent is not None:
        return [(tool_plan.tool_call_id, tool_plan.plan) for tool_plan in product_docs_plans(agent)]
    return [(None, state.plan)] if state.plan is not None else []


def _normalized_query(state: RunState) -> str | None:
    """Câu hỏi đã chuẩn hóa (tiếng Việt) của các sub-query, lưu log ở chat_history.

    Luồng agent: các câu hỏi agent đã gửi cho tool tra cứu.
    """
    agent = getattr(state, "agent", None)
    if agent is not None:
        questions = [tool_plan.question for tool_plan in product_docs_plans(agent)]
        return "\n".join(questions) if questions else None
    if state.analysis is None:
        return None
    return "\n".join(sub_query.standalone_query for sub_query in state.analysis.sub_queries)


def _as_text(value: object) -> str | None:
    return None if value is None else str(value)


def _unique_hits(hits: list) -> list:
    """Bỏ đoạn trùng giữa các lần tra cứu của cùng lượt (agent gọi tra cứu nhiều lần).

    `hits` đã xếp theo điểm giảm dần nên giữ lần xuất hiện đầu là giữ điểm cao nhất. Hit không có
    `chunk_id` thì giữ nguyên (Toma duyệt 2026-11-18, FRONTEND_REQUIREMENTS 19.15).
    """
    seen: set[str] = set()
    unique = []
    for hit in hits:
        chunk_id = getattr(hit, "chunk_id", None)
        if chunk_id is not None:
            key = str(chunk_id)
            if key in seen:
                continue
            seen.add(key)
        unique.append(hit)
    return unique


def _page_label(page_start: int | None, page_end: int | None) -> str | None:
    if not page_start:
        return None
    if not page_end or page_end == page_start:
        return f"page {page_start}"
    return f"page {page_start} - {page_end}"
