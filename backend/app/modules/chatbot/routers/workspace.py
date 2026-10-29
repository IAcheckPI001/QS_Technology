"""Endpoint đọc cho Support Workspace (chưa có xác thực/ownership)."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.modules.chatbot.dependencies import get_history_repository, request_id_of
from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.routers.sse import error_response
from app.modules.chatbot.schemas.history import (
    ChatHistoryItem,
    ChatHistoryResponse,
    ChatStatus,
    ChunkResult,
    ConversationListResponse,
    ConversationSummary,
    RetrievalSnapshotResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chatbot-workspace"])


def _database_unavailable(
    request: Request,
    message: str,
    log_message: str,
    *args: object,
) -> JSONResponse:
    request_id = request_id_of(request)
    logger.exception(f"{log_message} (request_id=%s)", *args, request_id)
    return error_response(request, 503, "database_unavailable", message, request_id)


@router.get("/chatbot/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    request: Request,
    session_id: UUID,
    repository: HistoryRepository = Depends(get_history_repository),
) -> ChatHistoryResponse | JSONResponse:
    try:
        history = await repository.list_for_history(session_id=session_id)
    except SQLAlchemyError:
        return _database_unavailable(
            request,
            "Chat history could not be loaded. Please try again.",
            "Chat history load failed (session_id=%s)",
            session_id,
        )

    if not history:
        return JSONResponse(
            status_code=404,
            content={
                "detail": {
                    "code": "session_not_found",
                    "message": "No chat history found for this session.",
                }
            },
        )

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[ChatHistoryItem.model_validate(item) for item in history],
    )


@router.get("/chatbot/conversations", response_model=ConversationListResponse)
async def list_conversations(
    request: Request,
    search: str | None = Query(default=None, max_length=200),
    status: ChatStatus | None = None,
    repository: HistoryRepository = Depends(get_history_repository),
) -> ConversationListResponse | JSONResponse:
    try:
        rows = await repository.list_conversations(search=search or None, status=status)
        metrics = await repository.aggregate_metrics()
    except SQLAlchemyError:
        return _database_unavailable(
            request,
            "Conversations could not be loaded. Please try again.",
            "Conversation list load failed",
        )
    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                session_id=row.latest.session_id,
                model=row.latest.model,
                product_models=(row.latest.conversation_state or {}).get("last_models", []),
                ticket_id=(row.latest.conversation_state or {}).get("ticket_id"),
                last_query=row.latest.query_origin,
                channel=row.latest.channel,
                created_at=row.started_at,
                updated_date=row.last_message_at,
                status=row.latest.status,
                total_tokens=row.total_tokens,
                cost_usd=row.cost_usd,
            )
            for row in rows
        ],
        total=len(rows),
        conversation_count=metrics.conversation_count,
        handoff_count=metrics.handoff_count,
        total_tokens=metrics.total_tokens,
        total_cost_vnd=round(metrics.cost_usd * settings.usd_to_vnd_rate, 2),
    )


@router.get(
    "/chatbot/sessions/{session_id}/retrieval",
    response_model=RetrievalSnapshotResponse,
)
async def get_retrieval_snapshot(
    request: Request,
    session_id: UUID,
    repository: HistoryRepository = Depends(get_history_repository),
) -> RetrievalSnapshotResponse | JSONResponse:
    try:
        rows = await repository.list_for_history(session_id=session_id)
    except SQLAlchemyError:
        return _database_unavailable(
            request,
            "Retrieval result could not be loaded. Please try again.",
            "Retrieval snapshot load failed (session_id=%s)",
            session_id,
        )
    # Lượt mới nhất có chunk; lượt direct-response/handoff không có snapshot.
    row = next(
        (item for item in reversed(rows) if (item.retrieval_snapshot or {}).get("chunks")),
        None,
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": {
                    "code": "retrieval_not_found",
                    "message": "No retrieval result found for this session.",
                }
            },
        )
    snapshot = row.retrieval_snapshot
    chunks = [ChunkResult.model_validate(chunk) for chunk in snapshot["chunks"]]
    return RetrievalSnapshotResponse(
        session_id=session_id,
        history_id=row.id,
        query=snapshot.get("query") or row.query_origin,
        model=snapshot.get("model") or row.model,
        product_models=snapshot.get("product_models", []),
        highest_score=max((chunk.score for chunk in chunks), default=None),
        latency_ms=snapshot.get("latency_ms"),
        total_tokens=row.total_tokens or 0,
        retrieval_status=snapshot.get("retrieval_status"),
        chunks=chunks,
    )
