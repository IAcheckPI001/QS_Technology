from collections.abc import AsyncIterator
from time import perf_counter
from uuid import UUID, uuid4

from app.modules.chatbot.prompts.default import SYSTEM_PROMPT
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.stages.security import SecurityBlockedError, SecurityStage
from app.modules.chatbot.stages.security import get_response_message, normalize_locale
from app.modules.chatbot.schemas.system.security import SecurityAction
from app.util.uuid_generate import generate_session_id


class ChatbotService:
    def __init__(
        self,
        provider: OpenAIProvider,
        history_repository: HistoryRepository,
        security_stage: SecurityStage | None = None,
    ) -> None:
        self._provider = provider
        self._history_repository = history_repository
        self._security_stage = security_stage or SecurityStage()

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

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]
        answer_parts: list[str] = []
        try:
            async for chunk in self._provider.stream_chat(messages):
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
