

# app/api/dependencies.py

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.service import ChatbotService
from app.core.config import settings
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from app.modules.chatbot.stages.prune_stage import Prune
from app.modules.learning_ai.ingestion.service import LearningIngestionService
from app.modules.learning_ai.repositories.support_chat_repository import SupportChatRepository


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
    retriever = getattr(request.app.state, "chatbot_retriever", None)
    return ChatbotService(
        provider,
        history_repository,
        prune=Prune(settings.context_token_budget),
        execution_stage=ExecutionStage(retriever=retriever),
    )

def get_learning_service(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> LearningIngestionService | None:
    pipeline = getattr(request.app.state, "learning_privacy_pipeline", None)
    if pipeline is None:
        return None
    return LearningIngestionService(SupportChatRepository(db), pipeline)


def get_support_chat_repository(
    db: AsyncSession = Depends(get_db_session),
) -> SupportChatRepository:
    return SupportChatRepository(db)
