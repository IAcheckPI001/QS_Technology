
from uuid import UUID

from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.schemas.system import (
    Conversation,
    ConversationMessage,
    RetrievalScope,
    QueryInfo,
    RunContext,
    RunState
)
from app.modules.chatbot.schemas.inbound import ChannelType, InboundRequest


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
            conversation=Conversation(summary=None, history=messages),
            query=QueryInfo(origin=request.message.text),
            retrieval_scope=self.resolve_retrieval_scope(request),
        )
        state.context_input = context
        state.context_status = "loaded"
        return context

