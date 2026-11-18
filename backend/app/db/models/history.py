from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Computed, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"
    __table_args__ = {"schema": "public"}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    query_origin: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="completed",
        server_default="completed",
    )
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        Computed("input_tokens + output_tokens", persisted=True),
    )
    cost_usd: Mapped[float | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
    )
    retrieved_chunk_ids: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        nullable=True,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ConversationState after this turn (pending clarification, mode, last models).
    conversation_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retrieval_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    channel: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="website",
        server_default="website",
    )
    # Cờ của lượt do Python tính lúc ghi (B2, sql/chat_conversations.sql); trigger cộng dồn vào
    # chat_conversations. Bản ghi cũ được điền bằng scripts/backfill_history_flags.py.
    has_tool_errors: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_handoff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    product_models: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default="{}",
    )
    ticket_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Header Idempotency-Key của client; hiện chỉ lưu, chưa chống xử lý trùng.
    idempotency_key: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChatConversation(Base):
    """Bảng tóm tắt một dòng mỗi phiên (B2). Chỉ đọc từ Python; trigger trong Postgres ghi
    (sql/chat_conversations.sql, FRONTEND_REQUIREMENTS 19.11)."""

    __tablename__ = "chat_conversations"
    __table_args__ = {"schema": "public"}

    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_history_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    last_query: Mapped[str] = mapped_column(Text, nullable=False)
    last_status: Mapped[str] = mapped_column(Text, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    has_handoff: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_tool_errors: Mapped[bool] = mapped_column(Boolean, nullable=False)
    product_models: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    ticket_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
