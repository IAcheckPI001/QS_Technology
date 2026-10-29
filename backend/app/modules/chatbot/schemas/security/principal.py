"""Danh tính người gọi và ngữ cảnh request, do auth dependency dựng.

Dịch vụ AI chỉ có một loại người gọi: hệ thống tích hợp (website backend, CRM
backend) xác thực bằng service key. Không bao giờ lấy principal từ body; ngoại
lệ duy nhất là `acting_user_id` (CRM khẳng định nhân viên nào đang chat, dịch vụ
tin vì tin key). Khách website ẩn danh do website backend tự quản lý.
"""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.modules.chatbot.schemas.default import Branch, ChannelType, Identifier, SystemModel

PrincipalType = Literal["service"]
AuthnMethod = Literal["service_key"]


class PrincipalContext(SystemModel):
    subject_id: Identifier                # integration_id
    principal_type: PrincipalType
    tenant_id: Identifier | None = None

    roles: frozenset[str] = Field(default_factory=frozenset)
    scopes: frozenset[str] = Field(default_factory=frozenset)

    authn_method: AuthnMethod
    credential_id: Identifier | None = None   # key_id của service key (audit, thu hồi)
    acting_user_id: Identifier | None = None  # nhân viên mà service đang chat thay

    @model_validator(mode="after")
    def _consistent_with_type(self) -> "PrincipalContext":
        if self.tenant_id is None or self.credential_id is None:
            raise ValueError("service principal requires tenant_id and credential_id")
        if self.roles:
            raise ValueError("service principal cannot carry roles")
        return self

    def acting_for(self, user_id: str) -> "PrincipalContext":
        """Principal thay mặt `user_id`; dựng lại để validator chạy lại."""
        return PrincipalContext(**{**self.model_dump(), "acting_user_id": user_id})


class RequestContext(SystemModel):
    request_id: Identifier
    channel: ChannelType
    branch: Branch | None = None
    received_at: AwareDatetime
