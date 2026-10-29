"""Hợp đồng public của POST /chat/website."""

from typing import Literal
from uuid import UUID

from ..default import SCHEMA_VERSION, ClientContext, InboundModel, MessageText


class ChatMessageIn(InboundModel):
    # message_id do server sinh; client chống gửi trùng bằng header Idempotency-Key.
    text: MessageText


class WebsiteChatIn(InboundModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    session_id: UUID | None = None
    message: ChatMessageIn
    client_context: ClientContext | None = None
