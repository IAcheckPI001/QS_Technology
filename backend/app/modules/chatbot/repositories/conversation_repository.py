"""Đọc danh sách, số liệu và đầu trang hội thoại từ bảng tóm tắt `chat_conversations` (B2).

Danh sách, phân trang, lọc kênh/trạng thái/model đọc bảng tóm tắt; từ khoá và khoảng thời gian
dùng `EXISTS` trên `chat_history` (index trigram và `(session_id, created_at, id)`), xem
FRONTEND_REQUIREMENTS 19.11. Chỉ đọc; bảng do trigger trong Postgres ghi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, exists, false, func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models.history import ChatConversation, ChatHistory
from app.db.models.session import ChatSession
from app.db.models.trace import ChatTrace
from app.modules.chatbot.services.conversation_filters import (
    LIKE_ESCAPE,
    ConversationFilters,
    like_escape,
)


@dataclass(frozen=True)
class TurnMatch:
    """Lượt khớp từ khoá để giao diện tô sáng và mở đúng lượt."""

    history_id: UUID
    turn_number: int
    query: str


@dataclass(frozen=True)
class ConversationListRow:
    summary: ChatConversation
    model: str | None = None
    total_tokens: int = 0
    match: TurnMatch | None = None
    acting_user_id: str | None = None


@dataclass(frozen=True)
class ConversationTotals:
    conversation_count: int
    handoff_count: int
    question_count: int
    cost_usd: float


def _folded(column):
    # Cùng biểu thức với index chat_history_query_trgm_idx.
    return func.public.immutable_unaccent(func.lower(column))


def question_match(column, tokens: tuple[str, ...]):
    """Mọi từ (đã bỏ dấu) có trong cùng một câu hỏi, không cần đúng thứ tự."""
    return and_(*(_folded(column).like(f"%{like_escape(token)}%", escape=LIKE_ESCAPE) for token in tokens))


def _in_range(history, filters: ConversationFilters):
    return and_(history.created_at >= filters.start, history.created_at < filters.end)


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _conditions(self, filters: ConversationFilters) -> list:
        c = ChatConversation
        conditions = []
        if filters.channel:
            conditions.append(c.channel == filters.channel)
        if filters.status == "handoff":
            conditions.append(c.has_handoff.is_(True))
        elif filters.status:
            conditions.append(c.last_status == filters.status)
        if filters.product_models:
            conditions.append(c.product_models.overlap(list(filters.product_models)))
        if filters.has_range:
            h = aliased(ChatHistory)
            conditions.append(exists().where(h.session_id == c.session_id, _in_range(h, filters)))
        terms = filters.terms
        if terms is not None:
            branches = []
            if terms.tokens:
                h = aliased(ChatHistory)
                branches.append(exists().where(h.session_id == c.session_id, question_match(h.query_origin, terms.tokens)))
            if terms.uuid is not None:
                h = aliased(ChatHistory)
                branches.append(c.session_id == terms.uuid)
                branches.append(exists().where(h.session_id == c.session_id, h.id == terms.uuid))
            if terms.exact and " " not in terms.exact:
                exact = terms.exact.lower()
                t = aliased(ChatTrace)
                branches.append(exists().where(t.session_id == c.session_id, t.request_id == terms.raw))
                branches.append(func.lower(c.ticket_id) == exact)
                models = literal(",") + func.lower(func.array_to_string(c.product_models, ",")) + literal(",")
                branches.append(models.like(f"%,{like_escape(exact)},%", escape=LIKE_ESCAPE))
            conditions.append(or_(*branches) if branches else false())
        return conditions

    async def search(
        self,
        filters: ConversationFilters,
        *,
        limit: int | None,
        after: tuple[datetime, UUID] | None = None,
    ) -> list[ConversationListRow]:
        """Hội thoại khớp bộ lọc, mới nhất trước; `after` là khoá của dòng cuối trang trước."""
        c = ChatConversation
        query = select(c).where(*self._conditions(filters))
        if after is not None:
            query = query.where(tuple_(c.last_message_at, c.session_id) < tuple_(*after))
        query = query.order_by(c.last_message_at.desc(), c.session_id.desc())
        if limit is not None:
            query = query.limit(limit)
        summaries = list((await self.db.execute(query)).scalars().all())
        return await self._enrich(summaries, filters)

    async def get(self, session_id: UUID) -> ConversationListRow | None:
        summary = await self.db.get(ChatConversation, session_id)
        if summary is None:
            return None
        rows = await self._enrich([summary], ConversationFilters())
        acting_user = await self.db.execute(select(ChatSession.acting_user_id).where(ChatSession.id == session_id))
        return ConversationListRow(
            summary=rows[0].summary,
            model=rows[0].model,
            total_tokens=rows[0].total_tokens,
            acting_user_id=acting_user.scalar_one_or_none(),
        )

    async def totals(self, filters: ConversationFilters) -> ConversationTotals:
        """19.5: đếm hội thoại khớp; câu hỏi và chi phí chỉ tính lượt trong khoảng thời gian (nếu có)."""
        c = ChatConversation
        matched = select(c.session_id, c.has_handoff, c.question_count, c.cost_usd).where(
            *self._conditions(filters)
        ).subquery()
        counts = (await self.db.execute(select(
            func.count(),
            func.count().filter(matched.c.has_handoff.is_(True)),
            func.coalesce(func.sum(matched.c.question_count), 0),
            func.coalesce(func.sum(matched.c.cost_usd), 0),
        ))).one()
        conversations, handoffs, questions, cost = counts
        if filters.has_range:
            h = ChatHistory
            questions, cost = (await self.db.execute(
                select(func.count(h.id), func.coalesce(func.sum(h.cost_usd), 0)).where(
                    h.session_id.in_(select(matched.c.session_id)), _in_range(h, filters),
                )
            )).one()
        return ConversationTotals(
            conversation_count=int(conversations),
            handoff_count=int(handoffs),
            question_count=int(questions),
            cost_usd=float(cost),
        )

    async def _enrich(self, summaries: list[ChatConversation], filters: ConversationFilters) -> list[ConversationListRow]:
        """Model của lượt cuối, tổng token và lượt khớp từ khoá cho các phiên của một trang."""
        if not summaries:
            return []
        h = ChatHistory
        session_ids = [summary.session_id for summary in summaries]
        models = dict((await self.db.execute(
            select(h.id, h.model).where(h.id.in_([summary.last_history_id for summary in summaries]))
        )).all())
        tokens = dict((await self.db.execute(
            select(h.session_id, func.coalesce(func.sum(h.total_tokens), 0))
            .where(h.session_id.in_(session_ids))
            .group_by(h.session_id)
        )).all())
        matches = await self._matches(session_ids, filters)
        return [
            ConversationListRow(
                summary=summary,
                model=models.get(summary.last_history_id),
                total_tokens=int(tokens.get(summary.session_id, 0)),
                match=matches.get(summary.session_id),
            )
            for summary in summaries
        ]

    async def _matches(self, session_ids: list[UUID], filters: ConversationFilters) -> dict[UUID, TurnMatch]:
        """Lượt khớp mới nhất của mỗi phiên (theo câu hỏi hoặc đúng mã lượt), kèm số thứ tự lượt."""
        terms = filters.terms
        if terms is None or (not terms.tokens and terms.uuid is None):
            return {}
        h = ChatHistory
        numbered = select(
            h.id, h.session_id, h.query_origin, h.created_at,
            func.row_number().over(partition_by=h.session_id, order_by=(h.created_at, h.id)).label("turn_number"),
        ).where(h.session_id.in_(session_ids)).subquery()
        branches = []
        if terms.tokens:
            branches.append(question_match(numbered.c.query_origin, terms.tokens))
        if terms.uuid is not None:
            branches.append(numbered.c.id == terms.uuid)
        query = select(numbered).where(or_(*branches))
        if filters.has_range:
            query = query.where(_in_range(numbered.c, filters))
        query = query.order_by(numbered.c.session_id, numbered.c.created_at.desc(), numbered.c.id.desc())
        matches: dict[UUID, TurnMatch] = {}
        for row in (await self.db.execute(query)).all():
            matches.setdefault(row.session_id, TurnMatch(row.id, int(row.turn_number), row.query_origin))
        return matches
