import json
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.modules.chatbot.schemas import ChatRequest
from app.modules.chatbot.service import ChatbotService


logger = logging.getLogger(__name__)
router = APIRouter(tags=["chatbot"])


def _sse_event(name: str, payload: dict[str, str]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chatbot", response_model=None)
async def chat(payload: ChatRequest, request: Request) -> StreamingResponse | JSONResponse:
    request_id = str(uuid4())
    service: ChatbotService | None = request.app.state.chatbot_service
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

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for chunk in service.stream_reply(payload.message):
                yield _sse_event("delta", {"text": chunk})
            yield _sse_event("done", {"request_id": request_id})
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
