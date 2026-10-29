"""Danh tính người gọi và ngữ cảnh request, do auth dependency dựng.

Không bao giờ lấy từ body: client không tự khai principal. Ngoại lệ duy nhất là
`acting_user_id` của principal service: hệ thống tích hợp (đã xác thực bằng
service key) khẳng định nhân viên nào đang chat, Chatbot tin vì tin key.
"""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.modules.chatbot.schemas.default import Branch, ChannelType, Identifier, SystemModel

PrincipalType = Literal["guest", "service"]
AuthnMethod = Literal["guest_token", "service_key"]


class PrincipalContext(SystemModel):
    subject_id: Identifier                # guest_id hoặc integration_id
    principal_type: PrincipalType
    tenant_id: Identifier | None = None

    roles: frozenset[str] = Field(default_factory=frozenset)
    scopes: frozenset[str] = Field(default_factory=frozenset)

    authn_method: AuthnMethod
    credential_id: Identifier | None = None   # key_id của service key (audit, thu hồi)
    acting_user_id: Identifier | None = None  # nhân viên mà service đang chat thay

    @model_validator(mode="after")
    def _consistent_with_type(self) -> "PrincipalContext":
        if self.principal_type == "guest":
            if (
                self.tenant_id is not None
                or self.roles
                or self.scopes
                or self.credential_id is not None
                or self.acting_user_id is not None
            ):
                raise ValueError("guest principal cannot carry tenant, roles, scopes or service fields")
        else:
            if self.tenant_id is None or self.credential_id is None:
                raise ValueError("service principal requires tenant_id and credential_id")
            if self.roles:
                raise ValueError("service principal cannot carry roles")
        return self

    def acting_for(self, user_id: str) -> "PrincipalContext":
        """Principal service thay mặt `user_id`; dựng lại để validator chạy lại."""
        if self.principal_type != "service":
            raise ValueError("only service principals can act for a user")
        return PrincipalContext(**{**self.model_dump(), "acting_user_id": user_id})


class RequestContext(SystemModel):
    request_id: Identifier
    channel: ChannelType
    branch: Branch | None = None
    received_at: AwareDatetime
