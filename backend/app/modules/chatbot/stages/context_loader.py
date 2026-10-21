
import logging
from uuid import UUID

from pydantic import ValidationError

from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.schemas.system import (
    Conversation,
    ConversationMessage,
    ConversationState,
    RetrievalScope,
    QueryInfo,
    RunContext,
    RunState
)
from app.modules.chatbot.schemas.inbound import ChannelType, InboundRequest


log = logging.getLogger(__name__)


class ContextBudgetError(RuntimeError):
    """The mandatory context payload cannot fit the configured budget."""


class ContextConfigurationError(RuntimeError):
    """Context/pruning configuration is missing or invalid."""


class ContextLoader:
    name = "context_loader"

    def __init__(self, history_repository: HistoryRepository) -> None:
        self._history_repository = history_repository

    def resolve_retrieval_scope(self, request: InboundRequest) -> RetrievalScope:
        if request.channel.type is ChannelType.WEBSITE:
            return RetrievalScope(collections=[
                "crm-technical",
                "crm-sale",
            ])
        collection = (
            "crm-technical"
            if request.channel.branch is Branch.SUPPORT_TECHNICAL
            else "crm-sale"
        )
        return RetrievalScope(collections=[collection])

    async def execute(self, state: RunState) -> RunContext:
        request = state.input
        histories = await self._history_repository.list_for_context(
            session_id=UUID(request.session.session_id),
        )
        messages: list[ConversationMessage] = []
        for history in histories:
            base_id = str(history.id)
            messages.append(ConversationMessage(
                role="user",
                content=history.query_origin,
                message_id=f"{base_id}:user",
            ))
            if history.answer:
                messages.append(ConversationMessage(
                    role="assistant",
                    content=history.answer,
                    message_id=f"{base_id}:assistant",
                ))
        context = RunContext(
            conversation=Conversation(
                summary=None,
                state=self._load_state(histories),
                history=messages,
            ),
            query=QueryInfo(origin=request.message.text),
            retrieval_scope=self.resolve_retrieval_scope(request),
        )
        state.context_input = context
        state.context_status = "loaded"
        return context

    @staticmethod
    def _load_state(histories: list) -> ConversationState:
        """State is carried by the latest completed turn; invalid data resets it."""
        raw = getattr(histories[-1], "conversation_state", None) if histories else None
        if not raw:
            return ConversationState()
        try:
            return ConversationState.model_validate(raw)
        except ValidationError:
            log.warning("Invalid conversation_state in chat history; using default state")
            return ConversationState()

