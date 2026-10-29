from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ServiceIntegration(Base):
    """Hệ thống tích hợp (CRM backend) gọi Chatbot bằng service key (backend/sql/service_keys.sql)."""

    __tablename__ = "service_integrations"
    __table_args__ = {"schema": "public"}

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # Kênh (endpoint) mà key của integration được phép gọi: crm | website.
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ServiceKey(Base):
    """Credential của một integration; chỉ lưu SHA-256 của secret."""

    __tablename__ = "service_keys"
    __table_args__ = {"schema": "public"}

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # key_id công khai
    integration_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("public.service_integrations.id"),
        nullable=False,
    )
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
