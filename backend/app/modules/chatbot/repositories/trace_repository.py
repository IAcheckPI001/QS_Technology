"""Lưu và đọc trace của lượt chat (public.chat_traces)."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tracing import Trace
from app.db.models.trace import ChatTrace


class TraceRepository:
    """Mỗi thao tác mở session DB riêng và commit ngay.

    Trace được ghi sau khi stream kết thúc (kể cả khi lỗi hoặc client ngắt), lúc
    transaction của request có thể đã rollback; lỗi ghi trace không được ảnh hưởng
    lượt chat (người gọi bắt và chỉ log).
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None) -> None:
        self._session_factory = session_factory

    def _session(self) -> AsyncSession:
        if self._session_factory is None:
            from app.db.session import AsyncSessionFactory

            self._session_factory = AsyncSessionFactory
        return self._session_factory()

    async def save(
        self,
        trace: Trace,
        *,
        history_id: UUID | None,
        session_id: UUID | None,
        channel: str,
        outcome: str,
    ) -> None:
        payload = trace.to_dict()
        async with self._session() as db:
            db.add(ChatTrace(
                trace_id=trace.trace_id,
                request_id=trace.request_id,
                history_id=history_id,
                session_id=session_id,
                channel=channel,
                outcome=outcome,
                duration_ms=round(trace.duration_ms),
                span_count=len(trace.spans),
                trace=payload,
            ))
            await db.commit()

    async def latest_for_session(
        self,
        session_id: UUID,
        history_id: UUID | None = None,
    ) -> ChatTrace | None:
        """Trace mới nhất của phiên, hoặc của đúng lượt `history_id` trong phiên."""
        query = select(ChatTrace).where(ChatTrace.session_id == session_id)
        if history_id is not None:
            query = query.where(ChatTrace.history_id == history_id)
        query = query.order_by(ChatTrace.created_at.desc()).limit(1)
        async with self._session() as db:
            return (await db.execute(query)).scalar_one_or_none()
