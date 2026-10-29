from datetime import UTC, datetime
from typing import Protocol

from app.core.security.service_key import (
    InvalidServiceKey,
    ServiceKeyChannelMismatch,
    parse_service_key,
    secret_matches,
)
from app.modules.chatbot.repositories.service_key_repository import ServiceKeyRecord
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.security.principal import PrincipalContext


class ServiceKeyStore(Protocol):
    async def get_by_key_id(self, key_id: str) -> ServiceKeyRecord | None: ...


class ServiceAuthService:
    """Xác minh service key của hệ thống tích hợp và quyền gọi kênh của endpoint."""

    def __init__(self, repository: ServiceKeyStore) -> None:
        self._repository = repository

    async def authenticate(self, token: str | None, channel: ChannelType) -> PrincipalContext:
        """Raise InvalidServiceKey nếu key thiếu/sai/thu hồi/hết hạn, và
        ServiceKeyChannelMismatch nếu key không được cấp cho `channel`.

        `channel` do endpoint quyết định; kênh của key chỉ để đối chiếu quyền.
        Lỗi đọc DB được để nguyên cho caller: không được quy thành 401.
        """
        parsed = parse_service_key(token)
        record = await self._repository.get_by_key_id(parsed.key_id)
        if record is None:
            raise InvalidServiceKey("unknown_key", parsed.key_id)
        if not secret_matches(parsed.secret, record.secret_hash):
            raise InvalidServiceKey("secret_mismatch", parsed.key_id)
        now = datetime.now(UTC)
        if record.revoked_at is not None:
            raise InvalidServiceKey("revoked", parsed.key_id)
        if record.expires_at is not None and record.expires_at <= now:
            raise InvalidServiceKey("expired", parsed.key_id)
        if record.integration_disabled_at is not None:
            raise InvalidServiceKey("integration_disabled", parsed.key_id)
        if record.channel != channel.value:
            raise ServiceKeyChannelMismatch(parsed.key_id, record.channel, channel.value)
        return PrincipalContext(
            subject_id=record.integration_id,
            principal_type="service",
            tenant_id=record.tenant_id,
            authn_method="service_key",
            credential_id=record.key_id,
        )
