"""Dependency wiring cho chatbot: service/repository, request context và auth theo kênh.

Lỗi auth trả `{"detail": {"code", "message", "request_id"}}` qua HTTPException,
cùng dạng với các lỗi JSON khác của router.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.request_context import current_request_id
from app.core.security.service_key import InvalidServiceKey, ServiceKeyChannelMismatch
from app.db.session import get_db_session
from app.modules.chatbot.repositories.chat_session_repository import ChatSessionRepository
from app.modules.chatbot.repositories.history_repository import HistoryRepository
from app.modules.chatbot.repositories.service_key_repository import ServiceKeyRepository
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.security.principal import PrincipalContext, RequestContext
from app.modules.chatbot.services import (
    ChatbotService,
    ServiceAuthService,
    SessionAccessService,
)
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from app.modules.chatbot.stages.prune_stage import Prune

logger = logging.getLogger(__name__)


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


def get_session_access_service(
    db: AsyncSession = Depends(get_db_session),
) -> SessionAccessService:
    return SessionAccessService(ChatSessionRepository(db))


def get_service_auth_service(
    db: AsyncSession = Depends(get_db_session),
) -> ServiceAuthService:
    return ServiceAuthService(ServiceKeyRepository(db))


def api_error(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "request_id": request_id},
        headers=headers,
    )


def request_id_of(request: Request) -> str:
    """ID middleware đã gắn vào scope state; không có middleware thì sinh và giữ lại."""
    request_id = getattr(request.state, "request_id", None) or current_request_id()
    request.state.request_id = request_id
    return request_id


def get_request_context(channel: ChannelType) -> Callable[[Request], RequestContext]:
    """Channel do endpoint quyết định, không lấy từ body."""

    def dependency(request: Request) -> RequestContext:
        return RequestContext(
            request_id=request_id_of(request),
            channel=channel,
            branch=None,  # chưa dùng
            received_at=datetime.now(UTC),
        )

    return dependency


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def _authenticate_service(
    request: Request,
    auth: ServiceAuthService,
    authorization: str | None,
    channel: ChannelType,
) -> PrincipalContext:
    """Xác thực service key cho kênh của endpoint; mọi lỗi auth thành HTTPException."""
    request_id = request_id_of(request)
    try:
        principal = await auth.authenticate(bearer_token(authorization), channel)
    except InvalidServiceKey as error:
        # Lý do chỉ ghi log; client luôn nhận cùng một 401 để không lộ key nào tồn tại.
        # key_id là phần công khai của key, được phép log; secret thì không.
        logger.warning(
            "Service key rejected reason=%s key_id=%s request_id=%s",
            error.reason,
            error.key_id,
            request_id,
        )
        request.state.outcome = "invalid_service_key"
        raise api_error(
            401,
            "invalid_service_key",
            "Service key is missing or invalid.",
            request_id,
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except ServiceKeyChannelMismatch as error:
        logger.warning(
            "Service key channel mismatch key_id=%s key_channel=%s expected=%s request_id=%s",
            error.key_id,
            error.key_channel,
            error.expected,
            request_id,
        )
        request.state.outcome = "service_key_channel_mismatch"
        raise api_error(
            403,
            "service_key_channel_mismatch",
            "This service key is not allowed to call this endpoint.",
            request_id,
        ) from None
    except Exception:
        logger.exception("Service key lookup failed (request_id=%s)", request_id)
        request.state.outcome = "database_unavailable"
        raise api_error(
            503,
            "database_unavailable",
            "Service authentication is temporarily unavailable. Please try again.",
            request_id,
        ) from None
    logger.debug(
        "Service key accepted integration_id=%s key_id=%s channel=%s request_id=%s",
        principal.subject_id,
        principal.credential_id,
        channel.value,
        request_id,
    )
    return principal


async def get_website_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    auth: ServiceAuthService = Depends(get_service_auth_service),
) -> PrincipalContext:
    """Principal của website backend; khách ẩn danh do website backend tự quản lý."""
    return await _authenticate_service(request, auth, authorization, ChannelType.WEBSITE)


async def get_crm_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    auth: ServiceAuthService = Depends(get_service_auth_service),
) -> PrincipalContext:
    """Principal của CRM backend; `acting_user_id` do router gắn từ body."""
    return await _authenticate_service(request, auth, authorization, ChannelType.CRM)


def get_idempotency_key(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> UUID | None:
    """Hiện chỉ nhận và lưu cùng lượt chat; chưa chống xử lý trùng."""
    if idempotency_key is None:
        return None
    try:
        return UUID(idempotency_key.strip())
    except ValueError:
        raise api_error(
            422,
            "invalid_idempotency_key",
            "Idempotency-Key must be a UUID.",
            request_id_of(request),
        ) from None
