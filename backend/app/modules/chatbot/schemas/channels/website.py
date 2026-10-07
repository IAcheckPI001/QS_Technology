

from typing import Literal
from pydantic import HttpUrl
 
from ..default import SCHEMA_VERSION, Identifier, InboundModel, LanguageCode
from ..inbound import MessageUser

class ClientContext(InboundModel):
    locale: LanguageCode | None = None
    timezone: str | None = None
    page_url: HttpUrl | None = None

class WebsiteChatIn(InboundModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    session_id: Identifier | None = None
    message: MessageUser
    client_context: ClientContext | None = None