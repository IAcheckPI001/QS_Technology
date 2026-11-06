"""Hợp đồng public của POST /chat/crm (CRM backend gọi bằng service key)."""

from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr

from ..default import SCHEMA_VERSION, Identifier, InboundModel
from .website import ChatMessageIn


class CRMChatIn(InboundModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    # Nhân viên CRM đã xác thực ở phía CRM backend; Chatbot tin vì tin service key.
    user_id: Identifier
    # Token của nhân viên để tool gọi API CRM (Bearer). Tùy chọn; không log, không lưu.
    # Không có thì tool CRM dùng user_id làm Bearer (hành vi cũ).
    crm_access_token: SecretStr | None = Field(
        default=None, min_length=1, max_length=4096, exclude=True, repr=False,
    )
    # Lấy từ event `done`; null/bỏ trống = hội thoại mới.
    session_id: UUID | None = None
    message: ChatMessageIn
