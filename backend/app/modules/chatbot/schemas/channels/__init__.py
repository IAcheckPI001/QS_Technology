"""Hợp đồng public theo kênh; adapter chuyển về InboundRequest nội bộ."""

from .crm import CRMChatIn
from .website import ChatMessageIn, WebsiteChatIn

__all__ = [
    "CRMChatIn",
    "ChatMessageIn",
    "WebsiteChatIn",
]
