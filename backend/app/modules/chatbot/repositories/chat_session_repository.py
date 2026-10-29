from uuid import UUID

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import ChatSession


class ChatSessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, session_id: UUID) -> ChatSession | None:
        return await self.db.get(ChatSession, session_id)

    async def create(
        self,
        *,
        session_id: UUID,
        principal_type: str,
        subject_id: str,
        tenant_id: str | None,
        acting_user_id: str | None,
        channel: str,
    ) -> ChatSession:
        session = ChatSession(
            id=session_id,
            principal_type=principal_type,
            subject_id=subject_id,
            tenant_id=tenant_id,
            acting_user_id=acting_user_id,
            channel=channel,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def touch(self, session_id: UUID) -> None:
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(last_activity_at=func.now())
        )
