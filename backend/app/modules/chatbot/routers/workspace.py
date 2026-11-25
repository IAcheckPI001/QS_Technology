"""Endpoint đọc cho Support Workspace (chưa có xác thực/ownership)."""

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.modules.chatbot.dependencies import (
    get_asset_signer,
    get_conversation_repository,
    get_history_repository,
    get_trace_reader,
    request_id_of,
)
from app.modules.chatbot.repositories.conversation_repository import ConversationRepository
from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.repositories.trace_repository import TraceRepository
from app.modules.chatbot.routers.sse import error_response
from app.modules.chatbot.schemas.history import (
    ChatChannel,
    ChatHistoryResponse,
    ChatTraceResponse,
    ConversationDetail,
    ConversationListResponse,
    ConversationMetricsResponse,
    ConversationStatusFilter,
    ConversationSummary,
    RetrievalSnapshotResponse,
    TraceSpan,
    TraceSummary,
)
from app.modules.chatbot.services.conversation_filters import (
    ConversationFilters,
    ConversationQueryError,
    build_filters,
    decode_cursor,
    encode_cursor,
)
from app.modules.chatbot.services.conversation_views import (
    conversation_detail,
    conversation_metrics,
    conversation_summary,
)
from app.modules.chatbot.services.turn_sources import history_item, retrieval_view
from app.modules.chatbot.sources import attach_chunk_images, attach_history_sources

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


def _invalid_query(request: Request, error: ConversationQueryError) -> JSONResponse:
    return error_response(request, 422, error.code, error.message, request_id_of(request))


def _session_not_found() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "detail": {
                "code": "session_not_found",
                "message": "No chat history found for this session.",
            }
        },
    )


@router.get("/chatbot/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    request: Request,
    session_id: UUID,
    limit: int | None = Query(default=None, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=200),
    repository: HistoryRepository = Depends(get_history_repository),
    signer=Depends(get_asset_signer),
) -> ChatHistoryResponse | JSONResponse:
    """Không có `limit`: mọi lượt như cũ. Có `limit`: trang `limit` lượt mới nhất, `cursor` tới lượt cũ hơn (19.7)."""
    try:
        before = decode_cursor(cursor) if cursor else None
    except ConversationQueryError as error:
        return _invalid_query(request, error)
    try:
        if limit is None:
            history = await repository.list_for_history(session_id=session_id)
            first_number, next_cursor = 1, None
        else:
            page = await repository.history_page(session_id=session_id, limit=limit, before=before)
            history, first_number = page.rows, page.first_turn_number
            next_cursor = encode_cursor(history[0].created_at, history[0].id) if page.has_more else None
        traced = await repository.traced_history_ids([item.id for item in history]) if history else set()
    except SQLAlchemyError:
        return _database_unavailable(
            request,
            "Chat history could not be loaded. Please try again.",
            "Chat history load failed (session_id=%s)",
            session_id,
        )

    if not history and before is None:
        return _session_not_found()

    messages = [
        history_item(item, settings.usd_to_vnd_rate, turn_number=first_number + index, has_trace=item.id in traced)
        for index, item in enumerate(history)
    ]
    # Nguồn được trích dẫn kèm ảnh: URL ký mới mỗi lần đọc (WU-17 đợt 2).
    messages = await attach_history_sources(messages, history, signer, max_images=settings.source_images_max)
    return ChatHistoryResponse(session_id=session_id, messages=messages, next_cursor=next_cursor)


def _filters(
    *,
    q: str | None,
    status: str | None,
    channel: str | None,
    product_model: list[str] | None,
    from_date: date | None,
    to_date: date | None,
) -> ConversationFilters:
    return build_filters(
        q=q, status=status, channel=channel, product_models=product_model, from_date=from_date, to_date=to_date,
    )


@router.get("/chatbot/conversations", response_model=ConversationListResponse)
async def list_conversations(
    request: Request,
    search: str | None = Query(default=None, max_length=200),
    q: str | None = Query(default=None, max_length=200),
    status: ConversationStatusFilter | None = None,
    channel: ChatChannel | None = None,
    product_model: list[str] | None = Query(default=None, max_length=20),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int | None = Query(default=None, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=300),
    repository: HistoryRepository = Depends(get_history_repository),
    conversations: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationListResponse | JSONResponse:
    """Có tham số B2 (q, channel, product_model, from/to, limit, cursor, status=handoff): đọc bảng
    tóm tắt (19.4). Không có: hành vi cũ cho /legacy (search/status trên lượt cuối, trả hết)."""
    b2 = (
        limit is not None or cursor is not None or q is not None or channel is not None
        or bool(product_model) or from_date is not None or to_date is not None or status == "handoff"
    )
    if b2:
        try:
            filters = _filters(
                q=q if q is not None else search, status=status, channel=channel,
                product_model=product_model, from_date=from_date, to_date=to_date,
            )
            after = decode_cursor(cursor, filters) if cursor else None
        except ConversationQueryError as error:
            return _invalid_query(request, error)
        try:
            # Lấy thêm một dòng để biết còn trang sau.
            rows = await conversations.search(filters, limit=None if limit is None else limit + 1, after=after)
        except SQLAlchemyError:
            return _database_unavailable(
                request,
                "Conversations could not be loaded. Please try again.",
                "Conversation list load failed",
            )
        has_more = limit is not None and len(rows) > limit
        rows = rows[:limit] if limit is not None else rows
        last = rows[-1].summary if has_more else None
        return ConversationListResponse(
            conversations=[conversation_summary(row, settings.usd_to_vnd_rate) for row in rows],
            next_cursor=encode_cursor(last.last_message_at, last.session_id, filters) if last else None,
        )

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


# B2: chưa có xác thực nên chỉ đăng ký khi WORKSPACE_CONVERSATION_API_ENABLED (TR-16, api/v1/router.py).
# /metrics khai báo trước /{session_id}.
conversation_router = APIRouter(tags=["chatbot-workspace"])


@conversation_router.get("/chatbot/conversations/metrics", response_model=ConversationMetricsResponse)
async def conversation_metrics_view(
    request: Request,
    q: str | None = Query(default=None, max_length=200),
    status: ConversationStatusFilter | None = None,
    channel: ChatChannel | None = None,
    product_model: list[str] | None = Query(default=None, max_length=20),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    conversations: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationMetricsResponse | JSONResponse:
    """19.5: số liệu của đúng tập hội thoại khớp bộ lọc (cùng tham số với danh sách)."""
    try:
        filters = _filters(
            q=q, status=status, channel=channel, product_model=product_model, from_date=from_date, to_date=to_date,
        )
    except ConversationQueryError as error:
        return _invalid_query(request, error)
    try:
        totals = await conversations.totals(filters)
    except SQLAlchemyError:
        return _database_unavailable(
            request,
            "Conversation metrics could not be loaded. Please try again.",
            "Conversation metrics load failed",
        )
    return conversation_metrics(totals, settings.usd_to_vnd_rate)


@conversation_router.get("/chatbot/conversations/{session_id}", response_model=ConversationDetail)
async def get_conversation(
    request: Request,
    session_id: UUID,
    conversations: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationDetail | JSONResponse:
    """19.6: đầu màn Chi tiết hội thoại khi mở bằng link."""
    try:
        row = await conversations.get(session_id)
    except SQLAlchemyError:
        return _database_unavailable(
            request,
            "Conversation could not be loaded. Please try again.",
            "Conversation load failed (session_id=%s)",
            session_id,
        )
    if row is None:
        return _session_not_found()
    return conversation_detail(row, settings.usd_to_vnd_rate)


@router.get(
    "/chatbot/sessions/{session_id}/retrieval",
    response_model=RetrievalSnapshotResponse,
)
async def get_retrieval_snapshot(
    request: Request,
    session_id: UUID,
    history_id: UUID | None = Query(default=None),
    repository: HistoryRepository = Depends(get_history_repository),
    signer=Depends(get_asset_signer),
) -> RetrievalSnapshotResponse | JSONResponse:
    """Nguồn câu trả lời của lượt `history_id`; không gửi thì lượt mới nhất có chunk (hành vi cũ)."""
    try:
        if history_id is not None:
            row = await repository.get_turn(session_id=session_id, history_id=history_id)
        else:
            row = await repository.latest_retrieval_turn(session_id=session_id)
    except SQLAlchemyError:
        return _database_unavailable(
            request,
            "Retrieval result could not be loaded. Please try again.",
            "Retrieval snapshot load failed (session_id=%s)",
            session_id,
        )
    if row is None and history_id is not None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": {
                    "code": "history_not_found",
                    "message": "No conversation turn found for this session.",
                }
            },
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
    return await attach_chunk_images(
        retrieval_view(session_id, row), row, signer, max_images=settings.source_images_max)


@router.get("/chatbot/sessions/{session_id}/trace", response_model=ChatTraceResponse)
async def get_chat_trace(
    request: Request,
    session_id: UUID,
    history_id: UUID | None = Query(default=None),
    repository: TraceRepository = Depends(get_trace_reader),
) -> ChatTraceResponse | JSONResponse:
    """Trace của lượt mới nhất trong phiên, hoặc của lượt `history_id`."""
    try:
        row = await repository.latest_for_session(session_id, history_id)
    except SQLAlchemyError:
        return _database_unavailable(
            request,
            "Chat trace could not be loaded. Please try again.",
            "Chat trace load failed (session_id=%s)",
            session_id,
        )
    if row is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": {
                    "code": "trace_not_found",
                    "message": "No trace found for this conversation turn.",
                }
            },
        )
    payload = row.trace
    return ChatTraceResponse(
        session_id=session_id,
        history_id=row.history_id,
        trace_id=row.trace_id,
        request_id=row.request_id,
        channel=row.channel,
        outcome=row.outcome,
        duration_ms=row.duration_ms,
        created_at=row.created_at,
        summary=TraceSummary.model_validate(payload["summary"]),
        spans=[TraceSpan.model_validate(item) for item in payload["spans"]],
    )
