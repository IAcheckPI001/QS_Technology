"""Payload chuẩn nội bộ: adapter của từng kênh dựng ra, pipeline chỉ đọc model này.

Không phải hợp đồng public (xem schemas/channels/), nên dùng SystemModel để lỗi
adapter (gõ sai tên trường) bị bắt ngay.
"""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .default import (
    SCHEMA_VERSION,
    Branch,
    ChannelType,
    ClientContext,
    Identifier,
    MessageText,
    SystemModel,
)


class ResourceRefs(SystemModel):
    ticket_id: Identifier | None = None
    customer_id: Identifier | None = None
    report_id: Identifier | None = None

    def is_empty(self) -> bool:
        return self.ticket_id is None and self.customer_id is None and self.report_id is None


class MessageUser(SystemModel):
    message_id: Identifier                 # server sinh, trùng chat_history.id
    text: MessageText
    idempotency_key: UUID | None = None    # header Idempotency-Key; hiện chỉ lưu, chưa chống trùng


class SessionInfo(SystemModel):
    session_id: Identifier


class ChannelInfo(SystemModel):
    type: ChannelType
    branch: Branch | None = None           # chưa dùng: để None


class InboundRequest(SystemModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    message: MessageUser
    session: SessionInfo
    channel: ChannelInfo

    resources: ResourceRefs = Field(default_factory=ResourceRefs)
    client_context: ClientContext | None = None

    @model_validator(mode="after")
    def _website_has_no_resources(self) -> "InboundRequest":
        if self.channel.type is ChannelType.WEBSITE and not self.resources.is_empty():
            raise ValueError("website requests cannot reference CRM resources")
        return self
