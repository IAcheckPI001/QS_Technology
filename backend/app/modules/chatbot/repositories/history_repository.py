from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models.history import ChatHistory
from app.db.models.trace import ChatTrace


@dataclass(frozen=True)
class HistoryPage:
    rows: list[ChatHistory]
    # Còn lượt cũ hơn trang này.
    has_more: bool
    # Số thứ tự (từ 1) của lượt đầu trang trong cả phiên.
    first_turn_number: int


@dataclass(frozen=True)
class ConversationRow:
    """Lượt mới nhất của một session kèm số liệu gộp của cả session."""

    latest: ChatHistory
    started_at: datetime
    last_message_at: datetime
    total_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class ConversationMetrics:
    conversation_count: int
    handoff_count: int
    total_tokens: int
    cost_usd: float


def _id_kwargs(history_id: UUID | None) -> dict[str, UUID]:
    """Dùng message_id do server sinh làm khóa chính; không có thì để default uuid4."""
    return {"id": history_id} if history_id is not None else {}


class HistoryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def session_exists(self, session_id: UUID) -> bool:
        result = await self.db.execute(
            select(ChatHistory.id)
            .where(ChatHistory.session_id == session_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_for_history(
        self,
        *,
        session_id: UUID,
    ) -> list[ChatHistory]:
        """Return all visible statuses for the session history UI."""
        result = await self.db.execute(
            select(ChatHistory)
            .where(ChatHistory.session_id == session_id)
            .order_by(ChatHistory.created_at, ChatHistory.id)
        )
        return list(result.scalars().all())

    async def history_page(
        self,
        *,
        session_id: UUID,
        limit: int,
        before: tuple[datetime, UUID] | None = None,
    ) -> HistoryPage:
        """19.7: `limit` lượt ngay trước `before` (trang đầu: mới nhất), xếp tăng dần trong trang."""
        key = tuple_(ChatHistory.created_at, ChatHistory.id)
        query = select(ChatHistory).where(ChatHistory.session_id == session_id)
        if before is not None:
            query = query.where(key < tuple_(*before))
        result = await self.db.execute(
            query.order_by(ChatHistory.created_at.desc(), ChatHistory.id.desc()).limit(limit + 1)
        )
        newest_first = list(result.scalars().all())
        rows = list(reversed(newest_first[:limit]))
        if not rows:
            return HistoryPage(rows=[], has_more=False, first_turn_number=1)
        earlier = await self.db.execute(
            select(func.count()).where(
                ChatHistory.session_id == session_id,
                key < tuple_(rows[0].created_at, rows[0].id),
            )
        )
        return HistoryPage(rows=rows, has_more=len(newest_first) > limit, first_turn_number=int(earlier.scalar_one()) + 1)

    async def traced_history_ids(self, history_ids: list[UUID]) -> set[UUID]:
        """Lượt có dòng chat_traces (index chat_traces_history_idx)."""
        if not history_ids:
            return set()
        result = await self.db.execute(
            select(ChatTrace.history_id).where(ChatTrace.history_id.in_(history_ids)).distinct()
        )
        return {history_id for history_id in result.scalars().all() if history_id is not None}

    async def get_turn(self, *, session_id: UUID, history_id: UUID) -> ChatHistory | None:
        """Một lượt của đúng phiên (lọc cả session_id để không đọc lượt của phiên khác)."""
        result = await self.db.execute(
            select(ChatHistory).where(
                ChatHistory.id == history_id,
                ChatHistory.session_id == session_id,
            )
        )
        return result.scalar_one_or_none()

    async def latest_retrieval_turn(self, *, session_id: UUID) -> ChatHistory | None:
        """Lượt mới nhất của phiên có chunk trong retrieval_snapshot (hành vi cũ của /retrieval)."""
        rows = await self.list_for_history(session_id=session_id)
        return next(
            (row for row in reversed(rows) if (row.retrieval_snapshot or {}).get("chunks")),
            None,
        )

    async def list_for_context(
        self,
        *,
        session_id: UUID,
    ) -> list[ChatHistory]:
        """Return only successful provider turns for context construction."""
        result = await self.db.execute(
            select(ChatHistory)
            .where(
                ChatHistory.session_id == session_id,
                ChatHistory.status == "completed",
            )
            .order_by(ChatHistory.created_at, ChatHistory.id)
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        session_id: UUID,
        query_origin: str,
        answer: str | None,
        status: str,
        model: str | None,
        latency_ms: int | None,
        normalized_query: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float | None = None,
        retrieved_chunk_ids: list[UUID] | None = None,
        conversation_state: dict | None = None,
        channel: str = "website",
        retrieval_snapshot: dict | None = None,
        history_id: UUID | None = None,
        idempotency_key: UUID | None = None,
        has_tool_errors: bool = False,
        is_handoff: bool = False,
        product_models: list[str] | None = None,
        ticket_id: str | None = None,
    ) -> ChatHistory:
        history = ChatHistory(
            **_id_kwargs(history_id),
            session_id=session_id,
            query_origin=query_origin,
            normalized_query=normalized_query,
            answer=answer,
            status=status,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            retrieved_chunk_ids=retrieved_chunk_ids,
            latency_ms=latency_ms,
            conversation_state=conversation_state,
            channel=channel,
            retrieval_snapshot=retrieval_snapshot,
            idempotency_key=idempotency_key,
            has_tool_errors=has_tool_errors,
            is_handoff=is_handoff,
            product_models=list(product_models or []),
            ticket_id=ticket_id,
        )
        self.db.add(history)
        await self.db.flush()
        return history

    async def create_blocked(
        self,
        *,
        session_id: UUID,
        query_origin: str,
        answer: str,
        latency_ms: int | None,
        channel: str = "website",
        history_id: UUID | None = None,
        idempotency_key: UUID | None = None,
    ) -> ChatHistory:
        """Persist a policy block outside the provider request transaction."""
        return await self.create_audit(
            status="blocked",
            session_id=session_id,
            query_origin=query_origin,
            answer=answer,
            model=None,
            latency_ms=latency_ms,
            channel=channel,
            history_id=history_id,
            idempotency_key=idempotency_key,
        )

    async def create_audit(
        self,
        *,
        status: str,
        session_id: UUID,
        query_origin: str,
        answer: str | None,
        model: str | None,
        latency_ms: int | None,
        channel: str = "website",
        history_id: UUID | None = None,
        idempotency_key: UUID | None = None,
        normalized_query: str | None = None,
        retrieval_snapshot: dict | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float | None = None,
        has_tool_errors: bool = False,
        is_handoff: bool = False,
        product_models: list[str] | None = None,
        ticket_id: str | None = None,
    ) -> ChatHistory:
        """Ghi và commit ngay bằng session riêng: dùng khi transaction của request
        sẽ không commit (lượt bị chặn, client ngắt kết nối)."""
        from app.db.session import AsyncSessionFactory

        async with AsyncSessionFactory() as audit_session:
            history = ChatHistory(
                **_id_kwargs(history_id),
                session_id=session_id,
                query_origin=query_origin,
                normalized_query=normalized_query,
                answer=answer,
                status=status,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                channel=channel,
                retrieval_snapshot=retrieval_snapshot,
                idempotency_key=idempotency_key,
                has_tool_errors=has_tool_errors,
                is_handoff=is_handoff,
                product_models=list(product_models or []),
                ticket_id=ticket_id,
            )
            audit_session.add(history)
            await audit_session.commit()
            await audit_session.refresh(history)
            return history

    async def list_conversations(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
    ) -> list[ConversationRow]:
        """One row per session; search/status apply to the latest turn."""
        session = ChatHistory.session_id
        ranked = select(
            ChatHistory,
            func.row_number()
            .over(
                partition_by=session,
                order_by=(ChatHistory.created_at.desc(), ChatHistory.id.desc()),
            )
            .label("turn_rank"),
            func.min(ChatHistory.created_at).over(partition_by=session).label("started_at"),
            func.max(ChatHistory.updated_date).over(partition_by=session).label("last_message_at"),
            func.sum(ChatHistory.total_tokens).over(partition_by=session).label("session_tokens"),
            func.sum(func.coalesce(ChatHistory.cost_usd, 0))
            .over(partition_by=session)
            .label("session_cost"),
        ).subquery()
        latest = aliased(ChatHistory, ranked)
        query = select(
            latest,
            ranked.c.started_at,
            ranked.c.last_message_at,
            ranked.c.session_tokens,
            ranked.c.session_cost,
        ).where(ranked.c.turn_rank == 1)
        if search:
            pattern = f"%{search}%"
            query = query.where(or_(latest.query_origin.ilike(pattern), latest.model.ilike(pattern)))
        if status:
            query = query.where(latest.status == status)
        query = query.order_by(ranked.c.last_message_at.desc(), latest.id)
        result = await self.db.execute(query)
        return [
            ConversationRow(
                latest=row,
                started_at=started_at,
                last_message_at=last_message_at,
                total_tokens=int(tokens or 0),
                cost_usd=float(cost or 0),
            )
            for row, started_at, last_message_at, tokens, cost in result.all()
        ]

    async def aggregate_metrics(self) -> ConversationMetrics:
        totals = await self.db.execute(
            select(
                func.count(func.distinct(ChatHistory.session_id)),
                func.coalesce(func.sum(ChatHistory.total_tokens), 0),
                func.coalesce(func.sum(ChatHistory.cost_usd), 0),
            )
        )
        conversations, tokens, cost = totals.one()
        # Một session được tính một lần dù handoff kéo dài nhiều lượt.
        handoffs = await self.db.execute(
            select(func.count(func.distinct(ChatHistory.session_id))).where(
                ChatHistory.conversation_state["mode"].as_string() != "bot"
            )
        )
        return ConversationMetrics(
            conversation_count=int(conversations),
            handoff_count=int(handoffs.scalar_one()),
            total_tokens=int(tokens),
            cost_usd=float(cost),
        )
