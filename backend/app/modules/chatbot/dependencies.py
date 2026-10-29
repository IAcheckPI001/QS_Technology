"""Dependency wiring cho chatbot: service/repository, request context và auth theo kênh.

Lỗi auth trả `{"detail": {"code", "message", "request_id"}}` qua HTTPException,
cùng dạng với các lỗi JSON khác của router.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.request_context import current_request_id
from app.core.security.service_key import InvalidServiceKey
from app.core.security.visitor_token import InvalidVisitorToken
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
    VisitorIdentityService,
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


def get_visitor_identity_service() -> VisitorIdentityService | None:
    if not settings.visitor_token_secret:
        return None
    return VisitorIdentityService(
        secret=settings.visitor_token_secret,
        issuer=settings.visitor_token_issuer,
        ttl=timedelta(seconds=settings.visitor_token_ttl_seconds),
    )


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


def get_website_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    identity: VisitorIdentityService | None = Depends(get_visitor_identity_service),
) -> PrincipalContext:
    if identity is None:
        raise api_error(
            503,
            "visitor_auth_not_configured",
            "Website chat is not configured yet. Set VISITOR_TOKEN_SECRET on the backend.",
            request_id_of(request),
        )
    token = bearer_token(authorization)
    try:
        if token is None:
            raise InvalidVisitorToken("missing")
        return identity.authenticate(token)
    except InvalidVisitorToken:
        raise api_error(
            401,
            "unauthorized",
            "Visitor token is missing or invalid. Request a new token and try again.",
            request_id_of(request),
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


async def get_crm_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    auth: ServiceAuthService = Depends(get_service_auth_service),
) -> PrincipalContext:
    """Principal service của CRM backend; `acting_user_id` do router gắn từ body."""
    request_id = request_id_of(request)
    try:
        principal = await auth.authenticate(bearer_token(authorization))
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
        "Service key accepted integration_id=%s key_id=%s request_id=%s",
        principal.subject_id,
        principal.credential_id,
        request_id,
    )
    return principal


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
