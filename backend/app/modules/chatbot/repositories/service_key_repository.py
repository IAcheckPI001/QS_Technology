from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.service_key import ServiceIntegration, ServiceKey


@dataclass(frozen=True)
class ServiceKeyRecord:
    key_id: str
    secret_hash: str
    expires_at: datetime | None
    revoked_at: datetime | None
    integration_id: str
    tenant_id: str
    integration_disabled_at: datetime | None


class ServiceKeyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_key_id(self, key_id: str) -> ServiceKeyRecord | None:
        row = (
            await self.db.execute(
                select(ServiceKey, ServiceIntegration)
                .join(ServiceIntegration, ServiceIntegration.id == ServiceKey.integration_id)
                .where(ServiceKey.id == key_id)
            )
        ).first()
        if row is None:
            return None
        key, integration = row
        return ServiceKeyRecord(
            key_id=key.id,
            secret_hash=key.secret_hash,
            expires_at=key.expires_at,
            revoked_at=key.revoked_at,
            integration_id=integration.id,
            tenant_id=integration.tenant_id,
            integration_disabled_at=integration.disabled_at,
        )
