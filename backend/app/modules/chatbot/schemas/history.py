from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ChatChannel = Literal["website", "crm"]
ChatStatus = Literal["completed", "blocked", "error", "cancelled"]


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    query_origin: str = Field(min_length=1)
    answer: str | None = None
    status: str = Field(min_length=1)
    created_at: datetime
    updated_date: datetime
    channel: ChatChannel
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    latency_ms: int | None = None


class ConversationSummary(BaseModel):
    session_id: UUID
    model: str | None = None
    # Model sản phẩm và ticket lấy từ conversation_state của lượt mới nhất.
    product_models: list[str] = Field(default_factory=list)
    ticket_id: str | None = None
    last_query: str
    channel: ChatChannel
    # created_at: tin nhắn đầu tiên của session; updated_date: tin nhắn cuối.
    created_at: datetime
    updated_date: datetime
    # Trạng thái của lượt mới nhất.
    status: str
    total_tokens: int = 0
    cost_usd: float = 0


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    total: int
    conversation_count: int
    handoff_count: int
    total_tokens: int
    # Ước tính từ token câu hỏi/câu trả lời, chưa gồm prompt context và embedding.
    total_cost_vnd: float


class ChunkResult(BaseModel):
    rank: int
    score: float
    content: str
    domain: str | None = None
    scopes: list[str] = Field(default_factory=list)
    control_interface: list[str] = Field(default_factory=list)
    spec_attributes: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    page_label: str | None = None


class RetrievalSnapshotResponse(BaseModel):
    session_id: UUID
    history_id: UUID
    query: str
    model: str | None = None
    product_models: list[str] = Field(default_factory=list)
    highest_score: float | None = None
    latency_ms: int | None = None
    total_tokens: int = 0
    # ok · no_hits · partial_error · error · incomplete · not_applicable; None với bản ghi cũ.
    retrieval_status: str | None = None
    chunks: list[ChunkResult]


class ChatHistoryResponse(BaseModel):
    session_id: UUID
    messages: list[ChatHistoryItem]
