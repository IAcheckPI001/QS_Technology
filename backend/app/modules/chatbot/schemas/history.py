from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ChatChannel = Literal["website", "crm"]
ChatStatus = Literal["completed", "blocked", "error", "cancelled"]
# Nguồn câu trả lời của một lượt (FRONTEND_REQUIREMENTS 19.14):
# documents: có tra cứu tài liệu (xem retrieval_status để biết có kết quả không) · crm_data: gọi công
# cụ CRM, không tra tài liệu · documents_and_crm: cả hai · direct: không tra cứu, không gọi công cụ ·
# none: lượt không có snapshot (bị chặn, nhân viên đang xử lý, bản ghi cũ).
AnswerSource = Literal["documents", "crm_data", "documents_and_crm", "direct", "none"]


class ToolUsage(BaseModel):
    """Số lần gọi một công cụ của trợ lý trong lượt (từ agent_steps, không chứa nội dung)."""

    name: str
    calls: int = 0
    # Lần gọi có status khác ok/deduplicated.
    failed: int = 0
    # Mã lỗi → số lần (vd. {"crm_query_invalid": 1}).
    errors: dict[str, int] = Field(default_factory=dict)


class TurnSources(BaseModel):
    """Tóm tắt nguồn câu trả lời của một lượt, đủ để hiện nhãn dưới lượt ở màn Chi tiết hội thoại."""

    answer_source: AnswerSource
    # ok · no_hits · partial_error · error · incomplete · not_applicable; None khi không có snapshot.
    retrieval_status: str | None = None
    chunk_count: int = 0
    # Công cụ trợ lý đã gọi, trừ công cụ tra tài liệu (product_docs_ask: thể hiện qua chunk).
    tools: list[ToolUsage] = Field(default_factory=list)
    has_tool_errors: bool = False


class TurnUsageInfo(BaseModel):
    """Nguồn của số token/chi phí của lượt (B3)."""

    # trace: usage thật OpenAI trả về của mọi lần gọi AI + embedding, giá theo model ·
    # estimate: bản ghi cũ, đếm từ chữ câu hỏi/câu trả lời theo giá gpt-4o-mini.
    source: Literal["trace", "estimate"]
    llm_calls: int | None = None
    # Lời gọi hết giờ/bị huỷ/stream bị ngắt trước khi có usage: token của chúng là ước tính.
    estimated_calls: int | None = None
    cached_input_tokens: int | None = None
    embedding_tokens: int | None = None
    # Model chưa có giá: chi phí của chúng không được cộng (thiếu).
    unpriced_models: list[str] = Field(default_factory=list)


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
    # Nguồn câu trả lời của lượt (B5); None khi client đọc schema cũ.
    sources: TurnSources | None = None
    # B3: nguồn số liệu token/chi phí; None khi lượt không gọi AI (bị chặn, nhân viên xử lý).
    usage: TurnUsageInfo | None = None
    # cost_usd × USD_TO_VND_RATE.
    cost_vnd: float | None = None
    # B2 (19.7, W3): giờ hỏi = created_at − latency_ms (null khi thiếu latency); giờ trả lời = created_at.
    asked_at: datetime | None = None
    answered_at: datetime | None = None
    # Số thứ tự (từ 1) của lượt trong cả phiên, đúng cả khi phân trang.
    turn_number: int | None = None
    # Có dòng chat_traces cho lượt này (mở được "Xem diễn biến xử lý").
    has_trace: bool | None = None


# Bộ lọc trạng thái hội thoại: trạng thái lượt mới nhất, hoặc `handoff` = phiên có chuyển nhân viên.
ConversationStatusFilter = Literal["completed", "handoff", "blocked", "error", "cancelled"]


class ConversationMatch(BaseModel):
    """Lượt khớp từ khoá `q` (lượt khớp mới nhất của phiên)."""

    history_id: UUID
    turn_number: int
    query: str


class ConversationSummary(BaseModel):
    session_id: UUID
    model: str | None = None
    # Model sản phẩm và ticket: legacy lấy từ conversation_state của lượt mới nhất; B2 lấy từ bảng
    # tóm tắt (model của lượt gần nhất có model, ticket gần nhất).
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
    # B2 (19.4); null ở đường legacy (không gửi tham số mới).
    question_count: int | None = None
    has_handoff: bool | None = None
    has_tool_errors: bool | None = None
    cost_vnd: float | None = None
    match: ConversationMatch | None = None


class ConversationDetail(ConversationSummary):
    """19.6: đầu màn Chi tiết hội thoại khi mở bằng link."""

    # Nhân viên CRM của phiên (chat_sessions); null với khách website hoặc phiên chưa có dòng.
    acting_user_id: str | None = None


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    # Đường legacy (không gửi tham số B2): tổng và số liệu như cũ. Đường B2: null, lấy ở /metrics.
    total: int | None = None
    conversation_count: int | None = None
    handoff_count: int | None = None
    total_tokens: int | None = None
    # Ước tính từ token câu hỏi/câu trả lời, chưa gồm prompt context và embedding.
    total_cost_vnd: float | None = None
    # Đường B2 có `limit`: cursor của trang sau, null khi hết.
    next_cursor: str | None = None


class ConversationMetricsResponse(BaseModel):
    """19.5: số liệu của đúng tập hội thoại khớp bộ lọc (không trả token, Q12)."""

    conversation_count: int
    handoff_count: int
    # Có from/to: chỉ tính lượt trong khoảng; không có: mọi lượt của các hội thoại khớp.
    question_count: int
    cost_usd: float
    cost_vnd: float


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
    # Nguồn của đoạn (W1, lượt ghi từ 2026-11-18); None với bản ghi cũ.
    chunk_id: str | None = None
    doc_id: str | None = None
    section_title: str | None = None
    section_path: list[str] = Field(default_factory=list)
    # S1, S2…: khớp trích dẫn [S1] trong câu trả lời.
    source_id: str | None = None


class RetrievalTask(BaseModel):
    task_id: str
    status: str
    error_code: str | None = None
    no_hits: bool = False
    fallback: bool = False


class AgentStepItem(BaseModel):
    """Một bước của trợ lý CRM (lần gọi LLM hoặc tool), chỉ metadata."""

    step: int
    kind: str
    name: str | None = None
    tool_call_id: str | None = None
    status: str
    latency_ms: int = 0
    finish_reason: str | None = None


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
    # B5: trạng thái lượt (completed, error, blocked, cancelled) và tóm tắt nguồn.
    turn_status: str | None = None
    sources: TurnSources | None = None
    retrieval_tasks: list[RetrievalTask] = Field(default_factory=list)
    agent_steps: list[AgentStepItem] = Field(default_factory=list)
    answered_without_tools: bool | None = None
    invalid_citations: list[str] = Field(default_factory=list)
    # Lượt agent: lý do kết thúc vòng lặp (answered, limit, plateau, ambiguous, budget, no_answer).
    final_reason: str | None = None


class ChatHistoryResponse(BaseModel):
    session_id: UUID
    messages: list[ChatHistoryItem]
    # Có `limit`: cursor tới các lượt cũ hơn (null khi đã tới lượt đầu). Không có `limit`: luôn null.
    next_cursor: str | None = None


class TraceSpan(BaseModel):
    """Một span của trace: chỉ metadata, không chứa nội dung tin nhắn hay output tool."""

    span_id: str
    parent_id: str | None = None
    name: str
    kind: str
    # Mốc tính từ lúc dịch vụ nhận request (ms).
    start_ms: float
    duration_ms: float | None = None
    # ok · error · cancelled · unfinished hoặc mã nghiệp vụ (tool_timeout, http_503, ...).
    status: str
    attributes: dict[str, str | int | float | bool | list[str] | None] = Field(default_factory=dict)


class TraceSummary(BaseModel):
    span_count: int
    dropped_spans: int
    llm_calls: int
    tool_calls: int
    # Mọi span lỗi, kể cả span cha nhận lỗi lan lên (đếm lặp một lỗi).
    error_spans: int
    # Nơi lỗi phát sinh: span lỗi không có span con nào lỗi.
    root_error_spans: int
    failed_tool_calls: int
    # Token thật do OpenAI trả về, khác ước tính trong chat_history.
    input_tokens: int
    output_tokens: int
    embedding_tokens: int


class ChatTraceResponse(BaseModel):
    session_id: UUID
    history_id: UUID | None = None
    trace_id: str
    request_id: str
    channel: str
    # ok hoặc mã lỗi SSE (analysis_error, agent_error, ...), client_disconnected.
    outcome: str
    duration_ms: int
    created_at: datetime
    summary: TraceSummary
    spans: list[TraceSpan]
