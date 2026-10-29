
import logging
from uuid import UUID

from pydantic import ValidationError

from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.schemas.system import (
    Conversation,
    ConversationMessage,
    ConversationState,
    PendingClarification,
    RetrievalScope,
    QueryInfo,
    RunContext,
    RunState
)
from app.modules.chatbot.schemas.inbound import Branch, ChannelType, InboundRequest
# Re-export: router và test đang import các lỗi này từ context_loader.
from app.modules.chatbot.stages.errors import ContextBudgetError, ContextConfigurationError

__all__ = ["ContextBudgetError", "ContextConfigurationError", "ContextLoader", "load_conversation_state"]

log = logging.getLogger(__name__)


class ContextLoader:
    name = "context_loader"

    def __init__(self, history_repository: HistoryRepository) -> None:
        self._history_repository = history_repository

    @staticmethod
    def resolve_retrieval_scope(request: InboundRequest) -> RetrievalScope:
        # Website, hoặc CRM chưa có branch (branch chưa dùng): tra cả hai collection.
        if request.channel.type is ChannelType.WEBSITE or request.channel.branch is None:
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
                state=self._load_state(histories, request.session.session_id),
                history=messages,
            ),
            query=QueryInfo(origin=request.message.text),
            retrieval_scope=self.resolve_retrieval_scope(request),
        )
        state.context_input = context
        state.context_status = "loaded"
        return context

    @staticmethod
    def _load_state(histories: list, session_id: str) -> ConversationState:
        """State is carried by the latest completed turn; invalid fields are dropped one by one."""
        raw = getattr(histories[-1], "conversation_state", None) if histories else None
        state, dropped = load_conversation_state(raw)
        if dropped:
            # Chỉ log tên field, không log giá trị (có thể chứa nội dung hội thoại).
            log.warning(
                "conversation_state partially invalid session_id=%s dropped_fields=%s",
                session_id,
                ",".join(dropped),
            )
        return state


def load_conversation_state(raw: object) -> tuple[ConversationState, list[str]]:
    """Đọc state đã lưu mà không reset toàn bộ khi schema đổi.

    1. Bỏ field không còn trong schema (chỉ khi đọc; khi ghi model vẫn extra="forbid").
    2. Nếu vẫn lỗi: gán từng field lên state mặc định (validate_assignment), giữ field
       hợp lệ như mode/ticket_id, bỏ field lỗi (vd. pending hỏng thì bỏ pending).
    Trả về state và tên các field bị bỏ.
    """
    if not raw:
        return ConversationState(), []
    if not isinstance(raw, dict):
        return ConversationState(), ["<root>"]

    fields = ConversationState.model_fields
    dropped = [key for key in raw if key not in fields]
    data = {key: value for key, value in raw.items() if key in fields}
    pending = data.get("pending")
    if isinstance(pending, dict):
        pending_fields = PendingClarification.model_fields
        dropped += [f"pending.{key}" for key in pending if key not in pending_fields]
        data["pending"] = {key: value for key, value in pending.items() if key in pending_fields}

    try:
        return ConversationState.model_validate(data), dropped
    except ValidationError:
        pass

    state = ConversationState()
    for key, value in data.items():
        try:
            setattr(state, key, value)
        except ValidationError:
            dropped.append(key)
    return state, dropped

