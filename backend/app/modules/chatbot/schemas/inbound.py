
from enum import StrEnum
from typing import Annotated, Literal
 
from pydantic import HttpUrl, AwareDatetime, StringConstraints, model_validator
 
from .default import SCHEMA_VERSION, MessageText, Identifier, InboundModel, LanguageCode


class ChannelType(StrEnum):
    CRM = "crm"
    WEBSITE = "website"
 
 
class Branch(StrEnum):
    SUPPORT_TECHNICAL = "support-technical"
    SUPPORT_SALE = "support-sale"


class RequestInfo(InboundModel):
    request_id: Identifier
    ticket_id: str | None = None # Chỉ tin khi đến từ kết nối server-to-server đã xác thực.
    user_id: str | None = None 
    received_at: AwareDatetime | None = None

class MessageUser(InboundModel):
    message_id: Identifier
    text: MessageText

class SessionInfo(InboundModel):
    session_id: Identifier

class ChannelInfo(InboundModel):
    type: ChannelType
    branch: Branch

class InboundRequest(InboundModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    request: RequestInfo
    message: MessageUser
    session: SessionInfo
    channel: ChannelInfo
 
    @model_validator(mode="after")
    def crm_requires_ticket(self) -> "InboundRequest":
        if self.channel.type is ChannelType.CRM and not self.request.ticket_id:
            raise ValueError("request.ticket_id là bắt buộc khi channel.type = 'crm'")
        return self