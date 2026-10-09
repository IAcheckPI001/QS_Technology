

# app/api/dependencies.py

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.service import ChatbotService


def get_history_repository(
    db: AsyncSession = Depends(get_db_session),
) -> HistoryRepository:
    return HistoryRepository(db)


def get_chatbot_service(
    request: Request,
    history_repository: HistoryRepository = Depends(get_history_repository),
) -> ChatbotService | None:
    provider = getattr(request.app.state, "chatbot_provider", None)
    if provider is None:
        return None
    return ChatbotService(provider, history_repository)