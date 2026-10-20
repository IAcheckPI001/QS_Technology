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
from app.modules.chatbot.schemas.system import RunState, RetrievalScope
from app.modules.chatbot.stages.prune_stage import Prune
from app.modules.chatbot.stages.context_loader import ContextLoader
from app.modules.chatbot.stages.security import SecurityBlockedError, SecurityStage
from app.modules.chatbot.stages.security import get_response_message, normalize_locale
from app.modules.chatbot.stages.analysis_stage import AnalysisStage
from app.modules.chatbot.schemas.system.security import SecurityAction
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from app.modules.chatbot.stages.answer_composer import AnswerComposer
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
    ) -> None:
        self._provider = provider
        self._history_repository = history_repository
        self._security_stage = security_stage or SecurityStage()
        self._context_loader = context_loader or ContextLoader(history_repository)
        self._prune = prune or Prune(settings.context_token_budget)
        self._analysis_stage = analysis_stage or AnalysisStage(provider)
        self._execution_stage = execution_stage or ExecutionStage()
        self._answer_composer = answer_composer or AnswerComposer(provider)

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

        analysis_time = perf_counter()

        await self._analysis_stage.execute(state)
        await self._execution_stage.execute(state)
        print(f"_analysis_stage: {state.analysis}")
        print(f"_execution_stage: {state.plan}")
        print(f"Analysis + execution time: {perf_counter() - analysis_time:.2f} s")

        answer_parts: list[str] = []
        try:
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

        await self._history_repository.create(
            session_id=session_id,
            query_origin=message,
            answer="".join(answer_parts),
            status="completed",
            model=self._provider.model,
            latency_ms=round((perf_counter() - started_at) * 1000),
        )
