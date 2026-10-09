from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.history import ChatHistory


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
        created_at: datetime | None = None,
    ) -> ChatHistory:
        history = ChatHistory(
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
            created_at=created_at,
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
    ) -> ChatHistory:
        """Persist a policy block outside the provider request transaction."""
        from app.db.session import AsyncSessionFactory

        async with AsyncSessionFactory() as audit_session:
            history = ChatHistory(
                session_id=session_id,
                query_origin=query_origin,
                answer=answer,
                status="blocked",
                model=None,
                latency_ms=latency_ms,
            )
            audit_session.add(history)
            await audit_session.commit()
            await audit_session.refresh(history)
            return history
