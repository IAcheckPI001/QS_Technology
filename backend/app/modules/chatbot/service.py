from collections.abc import AsyncIterator
from time import perf_counter
from uuid import UUID

from app.core.config import settings
from app.util.token_counter import count_tokens
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.schemas.inbound import (
    ChannelType,
    InboundRequest,
    MessageUser,
    SessionInfo
)
from app.modules.chatbot.clarification import update_conversation_state
from app.modules.chatbot.orchestration import select_direct_response_code
from app.modules.chatbot.prompts.direct_responses import get_direct_response
from app.modules.chatbot.providers.handoff import DisabledHandoffProvider, HandoffProvider
from app.modules.chatbot.schemas.system import (
    ConversationState,
    Mode,
    RunState,
    RetrievalScope,
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
from app.util.uuid_generate import generate_session_id


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

    async def resolve_session_id(self, session_id: str | None) -> UUID:
        if session_id:
            try:
                parsed_session_id = UUID(session_id)
            except ValueError:
                parsed_session_id = None
            if (
                parsed_session_id is not None
                and await self._history_repository.session_exists(parsed_session_id)
            ):
                return parsed_session_id

        return UUID(generate_session_id())

    async def stream_reply(
        self,
        message: str,
        session_id: UUID,
        locale: str | None = None,
    ) -> AsyncIterator[str]:
        started_at = perf_counter()
        security_decision = self._security_stage.inspect(message)
        if security_decision.action is SecurityAction.BLOCK:
            await self._history_repository.create_blocked(
                session_id=session_id,
                query_origin=message,
                answer=get_response_message("request_blocked", normalize_locale(locale)),
                latency_ms=round((perf_counter() - started_at) * 1000),
            )
            raise SecurityBlockedError(security_decision, locale)

        inbound = InboundRequest(
            message=MessageUser(message_id=f"request-{session_id}", text=message),
            session=SessionInfo(session_id=str(session_id)),
            channel={"type": ChannelType.WEBSITE, "branch": "support-technical"},
        )
        state = RunState(input=inbound, security=security_decision)
        load_context_time = perf_counter()
        context = await self._context_loader.execute(state)
        context = self._prune.execute(context, self._provider.model)
        print(f"Load context time: {perf_counter() - load_context_time:.2f} s")
        state.context = context
        state.context_status = "pruned"

        conversation_state = context.conversation.state
        if conversation_state.mode is not Mode.BOT:
            # A human agent owns the conversation: the bot does not answer.
            answer = get_direct_response(
                "agent.active" if conversation_state.mode is Mode.WITH_AGENT else "agent.awaiting",
                locale,
                context.query.language,
            )
            yield answer
            await self._history_repository.create(
                session_id=session_id,
                query_origin=message,
                answer=answer,
                status="completed",
                model=None,
                latency_ms=round((perf_counter() - started_at) * 1000),
                conversation_state=conversation_state.model_dump(mode="json"),
                channel=context.query.channel.dict() if context.query.channel else None,
            )
            return

        analysis_time = perf_counter()

        await self._clarification_stage.execute(state)
        await self._analysis_stage.execute(state)
        self._clarification_stage.apply_attempt_limit(state)
        await self._execution_stage.execute(state)
        # print(f"_analysis_stage: {state.analysis}")
        # print(f"_execution_stage: {state.plan}")
        print(f"Analysis + execution time: {perf_counter() - analysis_time:.2f} s")

        assert state.plan is not None
        direct_code = select_direct_response_code(state.plan)
        answer_parts: list[str] = []
        try:
            if direct_code is not None:
                answer_parts.append(get_direct_response(direct_code, locale, context.query.language))
                yield answer_parts[0]
            else:
                async for chunk in self._answer_composer.stream(state):
                    answer_parts.append(chunk)
                    yield chunk
        except Exception:
            await self._history_repository.create(
                session_id=session_id,
                query_origin=message,
                answer="".join(answer_parts) or None,
                status="error",
                model=self._provider.model,
                latency_ms=round((perf_counter() - started_at) * 1000),
            )
            raise

        next_state = await self._transfer_handoff(
            state,
            session_id,
            update_conversation_state(state),
        )
        await self._history_repository.create(
            session_id=session_id,
            query_origin=message,
            answer="".join(answer_parts),
            status="completed",
            model=self._provider.model,
            latency_ms=round((perf_counter() - started_at) * 1000),
            conversation_state=next_state.model_dump(mode="json"),
        )

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
