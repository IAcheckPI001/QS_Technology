from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, or_, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import ChatSession

# Lease không bao giờ được treo tới statement_timeout: dòng bị khóa quá lâu nghĩa là
# có lỗi, trả lỗi ngay (acquire -> 503, release -> log, lease tự hết hạn).
_LEASE_LOCK_TIMEOUT = text("SET LOCAL lock_timeout = '3s'")


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


class ChatTurnLeaseRepository:
    """Lease "đang có lượt chạy" của phiên.

    Mỗi thao tác mở session DB riêng và commit ngay: request khác phải thấy lease
    trước khi request hiện tại kết thúc (transaction của request chỉ commit ở cuối).
    Vì vậy transaction của request không được UPDATE dòng chat_sessions của phiên
    đã có: khóa dòng đó giữ tới cuối stream sẽ chặn chính lease của request.
    `last_activity_at` được cập nhật ở đây, cùng câu chiếm lease.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None) -> None:
        self._session_factory = session_factory

    def _session(self) -> AsyncSession:
        if self._session_factory is None:
            from app.db.session import AsyncSessionFactory

            self._session_factory = AsyncSessionFactory
        return self._session_factory()

    async def acquire(self, session_id: UUID, ttl_s: int) -> bool:
        """Chiếm lease nếu phiên rảnh hoặc lease cũ đã hết hạn (một câu UPDATE nguyên tử)."""
        async with self._session() as db:
            await db.execute(_LEASE_LOCK_TIMEOUT)
            result = await db.execute(
                update(ChatSession)
                .where(
                    ChatSession.id == session_id,
                    or_(
                        ChatSession.turn_lease_until.is_(None),
                        ChatSession.turn_lease_until < func.now(),
                    ),
                )
                .values(
                    turn_lease_until=func.now() + timedelta(seconds=ttl_s),
                    last_activity_at=func.now(),
                )
                .returning(ChatSession.id)
            )
            acquired = result.scalar_one_or_none() is not None
            await db.commit()
            return acquired

    async def release(self, session_id: UUID) -> None:
        async with self._session() as db:
            await db.execute(_LEASE_LOCK_TIMEOUT)
            await db.execute(
                update(ChatSession)
                .where(ChatSession.id == session_id)
                .values(turn_lease_until=None)
            )
            await db.commit()
