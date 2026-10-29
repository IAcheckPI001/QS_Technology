"""SSE transport và ánh xạ lỗi dùng chung cho các route chat."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.modules.chatbot.analysis.analyzer import AnalysisError
from app.modules.chatbot.schemas.inbound import InboundRequest
from app.modules.chatbot.schemas.security.principal import PrincipalContext, RequestContext
from app.modules.chatbot.services import ChatbotService
from app.modules.chatbot.stages.answer_composer import AnswerCompositionError
from app.modules.chatbot.stages.context_loader import ContextBudgetError, ContextConfigurationError
from app.modules.chatbot.stages.execution_stage import ExecutionError
from app.modules.chatbot.stages.security import (
    SecurityBlockedError,
    get_response_message,
    normalize_locale,
)

logger = logging.getLogger(__name__)


def set_outcome(request: Request, outcome: str) -> None:
    """Middleware đọc giá trị này để log kết quả thật của request (SSE luôn 200)."""
    request.state.outcome = outcome


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
) -> JSONResponse:
    set_outcome(request, code)
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message, "request_id": request_id}},
        headers={"X-Request-ID": request_id},
    )


def sse_event(name: str, payload: dict[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def stream_chat(
    request: Request,
    service: ChatbotService,
    inbound: InboundRequest,
    principal: PrincipalContext,
    request_context: RequestContext,
) -> StreamingResponse:
    request_id = request_context.request_id
    session_id = inbound.session.session_id

    def error_event(code: str, message: str) -> str:
        set_outcome(request, code)
        return sse_event("error", {"code": code, "message": message, "request_id": request_id})

    async def event_stream() -> AsyncIterator[str]:
        try:
            # aclosing: khi client ngắt và generator này bị đóng, stream_reply cũng
            # được đóng ngay (không chờ GC) để kịp ghi lượt status='cancelled'.
            async with aclosing(service.stream_reply(inbound, principal, request_context)) as replies:
                async for chunk in replies:
                    yield sse_event("delta", {"text": chunk})
            set_outcome(request, "ok")
            yield sse_event("done", {"request_id": request_id, "session_id": session_id})
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
            yield error_event(
                "request_blocked",
                get_response_message("request_blocked", normalize_locale(error.locale)),
            )
        except (ContextBudgetError, ContextConfigurationError):
            logger.exception(
                "Chat context preparation failed (request_id=%s session_id=%s)",
                request_id,
                session_id,
            )
            yield error_event(
                "context_error",
                "Chat context could not be prepared. Please try again.",
            )
        except (AnalysisError, ExecutionError, AnswerCompositionError) as error:
            logger.exception(
                "Chat request analysis failed code=%s (request_id=%s session_id=%s)",
                error.code,
                request_id,
                session_id,
            )
            yield error_event(
                "analysis_error",
                "The request could not be analyzed. Please rephrase and try again.",
            )
        except Exception:
            logger.exception("Chat provider failed (request_id=%s)", request_id)
            yield error_event(
                "provider_error",
                "AI provider request failed. Please try again.",
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        # X-Request-ID: cùng giá trị RequestContextMiddleware ghi đè; vẫn đặt cho app
        # không có middleware. X-Session-ID: session đã resolve trước khi stream, để
        # bên tích hợp lưu (ví dụ đặt cookie) trước khi nhận body.
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
            "X-Session-ID": session_id,
        },
    )
