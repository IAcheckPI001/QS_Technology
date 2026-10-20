"""HTTP transport cho luồng học tri thức. Chỉ được include khi LEARNING_API_ENABLED=true.

Hiện chạy tới bước nạp hội thoại CRM → lọc → privacy; Segmenter/Extractor và lưu job
chưa được nối. Response chỉ chứa text đã che.
"""
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.dependencies import get_learning_service, get_support_chat_repository
from app.modules.learning_ai.repositories.support_chat_repository import SupportChatRepository
from app.modules.learning_ai.ingestion.service import IngestionStatus, LearningIngestionService
from app.modules.learning_ai.schemas.api import (
    LearnRequest,
    LearnResponse,
    SupportChatMessage,
    SupportChatMessagesResponse,
    SupportChatSession,
    SupportChatSessionCreate,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["learning_ai"])


def _error(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message, "request_id": request_id}},
        headers={"X-Request-ID": request_id},
    )


@router.get("/support-chat/sessions", response_model=list[SupportChatSession])
async def list_support_chat_sessions(
    repository: SupportChatRepository = Depends(get_support_chat_repository),
) -> list[SupportChatSession] | JSONResponse:
    try:
        sessions = await repository.list_sessions()
        print(f"Retrieved {len(sessions)} support chat sessions")
    except SQLAlchemyError:
        request_id = str(uuid4())
        logger.exception("support chat session list failed request_id=%s", request_id)
        return _error(503, "database_unavailable", "Conversations could not be loaded.", request_id)
    return [
        SupportChatSession(
            session_id=session.session_id,
            product_models=session.product_models,
            created_at=session.created_at,
        )
        for session in sessions
    ]



@router.post("/support-chat/sessions", response_model=SupportChatSession, status_code=201)
async def create_support_chat_session(
    payload: SupportChatSessionCreate,
    repository: SupportChatRepository = Depends(get_support_chat_repository),
) -> SupportChatSession | JSONResponse:
    try:
        session = await repository.create_session(product_models=list(payload.product_models))
    except SQLAlchemyError:
        request_id = str(uuid4())
        logger.exception("support chat session creation failed request_id=%s", request_id)
        return _error(503, "database_unavailable", "Conversation could not be created.", request_id)
    return SupportChatSession(
        session_id=session.session_id,
        product_models=session.product_models,
        created_at=session.created_at,
    )


@router.get("/support-chat/sessions/{session_id}/messages", response_model=SupportChatMessagesResponse)
async def list_support_chat_messages(
    session_id: UUID,
    repository: SupportChatRepository = Depends(get_support_chat_repository),
) -> SupportChatMessagesResponse | JSONResponse:
    request_id = str(uuid4())
    try:
        messages = await repository.list_for_session(session_id=session_id)
        session = await repository.get_session(session_id=session_id)
        print(f"Retrieved {len(messages)} messages for session {session_id}")
    except SQLAlchemyError:
        logger.exception("support chat message list failed request_id=%s session_id=%s", request_id, session_id)
        return _error(503, "database_unavailable", "Conversation messages could not be loaded.", request_id)
    if session is None:
        return _error(404, "session_not_found", "No support conversation found for this session.", request_id)
    return SupportChatMessagesResponse(
        session_id=session_id,
        messages=[
            SupportChatMessage(
                id=message.id,
                session_id=message.session_id,
                message_no=message.message_no,
                sender_role=message.sender_role,
                message_text=message.message_text,
                created_at=message.created_at,
            )
            for message in messages
        ],
    )


@router.post("/learning-knowledge", response_model=LearnResponse)
async def submit_learning(
    payload: LearnRequest,
    service: LearningIngestionService | None = Depends(get_learning_service),
) -> LearnResponse | JSONResponse:
    request_id = str(uuid4())
    if service is None:
        return _error(503, "privacy_provider_not_configured",
                      "Learning service is not configured. Set OLLAMA_BASE_URL and OLLAMA_MODEL.", request_id)

    logger.info("learning request request_id=%s session_id=%s retry_failed=%s",
                request_id, payload.session_id, payload.retry_failed)
    try:
        result = await service.prepare(payload.session_id)
    except (SQLAlchemyError, OSError):
        logger.exception("learning request request_id=%s failed to read conversation", request_id)
        return _error(503, "database_unavailable", "Conversation could not be loaded. Please try again.",
                      request_id)
    except Exception:
        logger.exception("learning request request_id=%s failed", request_id)
        return _error(500, "internal_error", "Learning request failed.", request_id)

    if result.status == IngestionStatus.NOT_FOUND:
        return _error(404, "session_not_found", "No support conversation found for this session.", request_id)
    if result.status == IngestionStatus.PRIVACY_UNAVAILABLE:
        return _error(503, "privacy_check_unavailable",
                      "Privacy check could not be completed. The conversation was not processed.", request_id)

    response = LearnResponse.from_result(result, request_id)
    print(response.model_dump(mode="json"))
    return JSONResponse(content=response.model_dump(mode="json"), headers={"X-Request-ID": request_id})
