

# app/api/dependencies.py

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.learning_ai.ingestion.service import LearningIngestionService
from app.modules.learning_ai.repositories.support_chat_repository import SupportChatRepository


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
