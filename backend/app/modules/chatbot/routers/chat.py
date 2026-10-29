"""Endpoint chat theo kênh: channel do endpoint quyết định, không lấy từ body.

Người gọi luôn là hệ thống tích hợp (website backend, CRM backend) xác thực bằng
service key được cấp cho đúng kênh của endpoint.

Luồng: auth dependency → schema kênh → SessionAccessService → adapter →
InboundRequest → ChatbotService (SSE).
"""

import logging
from collections.abc import Callable
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.modules.chatbot.adapters.crm import crm_to_inbound
from app.modules.chatbot.adapters.website import website_to_inbound
from app.modules.chatbot.dependencies import (
    get_chatbot_service,
    get_crm_principal,
    get_idempotency_key,
    get_request_context,
    get_session_access_service,
    get_website_principal,
)
from app.modules.chatbot.routers.sse import error_response, stream_chat
from app.modules.chatbot.schemas.channels import CRMChatIn, WebsiteChatIn
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.inbound import InboundRequest
from app.modules.chatbot.schemas.security.principal import PrincipalContext, RequestContext
from app.modules.chatbot.services import (
    ChatbotService,
    SessionAccessService,
    SessionNotFound,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chatbot"])


@router.post("/chat/website", response_model=None)
async def chat_website(
    request: Request,
    payload: WebsiteChatIn,
    principal: PrincipalContext = Depends(get_website_principal),
    request_context: RequestContext = Depends(get_request_context(ChannelType.WEBSITE)),
    idempotency_key: UUID | None = Depends(get_idempotency_key),
    sessions: SessionAccessService = Depends(get_session_access_service),
    service: ChatbotService | None = Depends(get_chatbot_service),
) -> StreamingResponse | JSONResponse:
    return await _chat(
        request,
        service,
        sessions,
        principal,
        request_context,
        payload.session_id,
        lambda session_id, message_id: website_to_inbound(
            payload,
            session_id=session_id,
            message_id=message_id,
            idempotency_key=idempotency_key,
            request_context=request_context,
        ),
    )


@router.post("/chat/crm", response_model=None)
async def chat_crm(
    request: Request,
    payload: CRMChatIn,
    principal: PrincipalContext = Depends(get_crm_principal),
    request_context: RequestContext = Depends(get_request_context(ChannelType.CRM)),
    idempotency_key: UUID | None = Depends(get_idempotency_key),
    sessions: SessionAccessService = Depends(get_session_access_service),
    service: ChatbotService | None = Depends(get_chatbot_service),
) -> StreamingResponse | JSONResponse:
    return await _chat(
        request,
        service,
        sessions,
        principal.acting_for(payload.user_id),
        request_context,
        payload.session_id,
        lambda session_id, message_id: crm_to_inbound(
            payload,
            session_id=session_id,
            message_id=message_id,
            idempotency_key=idempotency_key,
            request_context=request_context,
        ),
    )


async def _chat(
    request: Request,
    service: ChatbotService | None,
    sessions: SessionAccessService,
    principal: PrincipalContext,
    request_context: RequestContext,
    requested_session_id: UUID | None,
    to_inbound: Callable[[UUID, str], InboundRequest],
) -> StreamingResponse | JSONResponse:
    request_id = request_context.request_id
    if service is None:
        return error_response(
            request,
            503,
            "provider_not_configured",
            "Chat service is not configured yet. Set OPENAI_API_KEY on the backend.",
            request_id,
        )

    try:
        session_id = await sessions.resolve_or_create(
            requested_session_id,
            principal,
            request_context.channel,
        )
    except SessionNotFound:
        return error_response(
            request,
            404,
            "session_not_found",
            "Chat session was not found. Start a new conversation.",
            request_id,
        )
    except Exception:
        logger.exception("Failed to resolve chat session (request_id=%s)", request_id)
        return error_response(
            request,
            503,
            "database_unavailable",
            "Chat session could not be initialized. Please try again.",
            request_id,
        )

    inbound = to_inbound(session_id, str(uuid4()))
    # Chỉ metadata: không log nội dung tin nhắn, page_url hay timezone (có thể chứa PII).
    logger.debug(
        "chat request channel=%s principal_type=%s subject_id=%s acting_user_id=%s "
        "credential_id=%s session_id=%s new_session=%s text_chars=%d locale=%s "
        "idempotency_key=%s",
        request_context.channel.value,
        principal.principal_type,
        principal.subject_id,
        principal.acting_user_id,
        principal.credential_id,
        session_id,
        requested_session_id is None,
        len(inbound.message.text),
        inbound.client_context.locale if inbound.client_context else None,
        inbound.message.idempotency_key is not None,
    )
    return stream_chat(request, service, inbound, principal, request_context)
