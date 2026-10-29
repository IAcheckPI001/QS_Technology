"""Hợp đồng public của POST /chat/crm (CRM backend gọi bằng service key)."""

from typing import Literal
from uuid import UUID

from ..default import SCHEMA_VERSION, Identifier, InboundModel
from .website import ChatMessageIn


class CRMChatIn(InboundModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    # Nhân viên CRM đã xác thực ở phía CRM backend; Chatbot tin vì tin service key.
    user_id: Identifier
    # Lấy từ event `done`; null/bỏ trống = hội thoại mới.
    session_id: UUID | None = None
    message: ChatMessageIn
