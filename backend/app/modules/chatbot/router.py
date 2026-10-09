import json
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.modules.chatbot.schemas.channels import WebsiteChatIn
from app.modules.chatbot.service import ChatbotService
from app.modules.chatbot.stages.security import (
    SecurityBlockedError,
    get_response_message,
    normalize_locale,
)
from app.api.v1.dependencies import get_chatbot_service


logger = logging.getLogger(__name__)
router = APIRouter(tags=["chatbot"])


def _sse_event(name: str, payload: dict[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chatbot", response_model=None)
async def chat(
    payload: WebsiteChatIn,
    service: ChatbotService | None = Depends(get_chatbot_service),
) -> StreamingResponse | JSONResponse:
    request_id = str(uuid4())
    if service is None:
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "provider_not_configured",
                    "message": "Chat service is not configured yet. Set OPENAI_API_KEY on the backend.",
                    "request_id": request_id,
                }
            },
            headers={"X-Request-ID": request_id},
        )

    try:
        session_id = await service.resolve_session_id(payload.session_id)
    except Exception:
        logger.exception("Failed to resolve chat session (request_id=%s)", request_id)
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "database_unavailable",
                    "message": "Chat session could not be initialized. Please try again.",
                    "request_id": request_id,
                }
            },
            headers={"X-Request-ID": request_id},
        )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for chunk in service.stream_reply(
                payload.message.text,
                session_id,
                payload.client_context.locale if payload.client_context else None,
            ):
                yield _sse_event("delta", {"text": chunk})
            yield _sse_event(
                "done",
                {"request_id": request_id, "session_id": str(session_id)},
            )
        except SecurityBlockedError as error:
            logger.info(
                "Chat security event status=blocked request_id=%s session_id=%s "
                "policy_version=%s highest_severity=%s finding_count=%d",
                request_id,
                session_id,
                error.decision.policy_version,
                error.decision.highest_severity,
                len(error.decision.findings),
            )
            yield _sse_event(
                "error",
                {
                    "code": "request_blocked",
                    "message": get_response_message(
                        "request_blocked",
                        normalize_locale(error.locale),
                    ),
                    "request_id": request_id,
                },
            )
        except Exception:
            logger.exception("Chat provider failed (request_id=%s)", request_id)
            yield _sse_event(
                "error",
                {
                    "code": "provider_error",
                    "message": "AI provider request failed. Please try again.",
                    "request_id": request_id,
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )
