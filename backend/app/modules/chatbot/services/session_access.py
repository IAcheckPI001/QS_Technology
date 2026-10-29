from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.security.principal import PrincipalContext


class SessionNotFound(Exception):
    """Session không tồn tại, không thuộc principal, khác kênh, bị thu hồi hoặc hết hạn."""


class SessionRecord(Protocol):
    principal_type: str
    subject_id: str
    tenant_id: str | None
    acting_user_id: str | None
    channel: str
    expires_at: datetime | None
    revoked_at: datetime | None


class SessionStore(Protocol):
    async def get_by_id(self, session_id: UUID) -> SessionRecord | None: ...

    async def create(
        self,
        *,
        session_id: UUID,
        principal_type: str,
        subject_id: str,
        tenant_id: str | None,
        acting_user_id: str | None,
        channel: str,
    ) -> object: ...

    async def touch(self, session_id: UUID) -> None: ...


class SessionAccessService:
    def __init__(self, repository: SessionStore) -> None:
        self._repository = repository

    async def resolve_or_create(
        self,
        requested_session_id: UUID | None,
        principal: PrincipalContext,
        channel: ChannelType,
    ) -> UUID:
        if requested_session_id is None:
            session_id = uuid4()
            await self._repository.create(
                session_id=session_id,
                principal_type=principal.principal_type,
                subject_id=principal.subject_id,
                tenant_id=principal.tenant_id,
                acting_user_id=principal.acting_user_id,
                channel=channel.value,
            )
            return session_id

        session = await self._repository.get_by_id(requested_session_id)
        # Không biến UUID client gửi thành session mới, và không tiết lộ session
        # tồn tại nhưng thuộc người khác: mọi trường hợp đều là SessionNotFound.
        if session is None or not _accessible(session, principal, channel):
            raise SessionNotFound()

        await self._repository.touch(requested_session_id)
        return requested_session_id


def _accessible(
    session: SessionRecord,
    principal: PrincipalContext,
    channel: ChannelType,
) -> bool:
    same_owner = (
        session.principal_type == principal.principal_type
        and session.subject_id == principal.subject_id
        and session.tenant_id == principal.tenant_id
        # Service (CRM) chat thay nhiều nhân viên: mỗi nhân viên chỉ thấy session của mình.
        and session.acting_user_id == principal.acting_user_id
    )
    expired = session.expires_at is not None and session.expires_at <= datetime.now(UTC)
    return (
        same_owner
        and session.channel == channel.value
        and session.revoked_at is None
        and not expired
    )
