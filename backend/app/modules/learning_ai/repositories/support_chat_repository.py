from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.support_chat import SupportChatHistory, SupportChatTestSession


class SupportChatRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_session(
        self,
        *,
        session_id: UUID,
    ) -> list[SupportChatHistory]:
        """Return all messages of one CRM conversation in message order."""
        result = await self.db.execute(
            select(SupportChatHistory)
            .where(SupportChatHistory.session_id == session_id)
            .order_by(SupportChatHistory.message_no)
        )
        return list(result.scalars().all())

    async def list_sessions(self) -> list[SupportChatTestSession]:
        result = await self.db.execute(
            select(SupportChatTestSession).order_by(
                SupportChatTestSession.created_at.desc(),
                SupportChatTestSession.session_id,
            )
        )
        return list(result.scalars().all())

    async def get_session(self, *, session_id: UUID) -> SupportChatTestSession | None:
        return await self.db.get(SupportChatTestSession, session_id)

    async def create_session(
        self,
        *,
        product_models: list[str],
    ) -> SupportChatTestSession:
        session = SupportChatTestSession(product_models=product_models)
        self.db.add(session)
        await self.db.flush()
        return session
