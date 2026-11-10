"""SSE transport và ánh xạ lỗi dùng chung cho các route chat."""

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from uuid import UUID

import anyio
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.tracing import STATUS_OK, Trace, activate, span
from app.modules.chatbot.agent import AgentError
from app.modules.chatbot.analysis.analyzer import AnalysisError
from app.modules.chatbot.repositories.trace_repository import TraceRepository
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


def log_trace_summary(trace: Trace, outcome: str) -> None:
    """Một dòng tóm tắt mỗi lượt (luôn có, kể cả khi không lưu trace vào DB)."""
    summary = trace.summary()
    logger.info(
        "chat_trace trace_id=%s outcome=%s duration_ms=%d first_delta_ms=%s spans=%d "
        "llm_calls=%d tool_calls=%d input_tokens=%d output_tokens=%d embedding_tokens=%d "
        "error_spans=%d root_error_spans=%d failed_tool_calls=%d tool_errors=%s dropped_spans=%d",
        trace.trace_id,
        outcome,
        round(trace.duration_ms),
        trace.root.attributes.get("first_delta_ms", "-"),
        summary["span_count"],
        summary["llm_calls"],
        summary["tool_calls"],
        summary["input_tokens"],
        summary["output_tokens"],
        summary["embedding_tokens"],
        summary["error_spans"],
        summary["root_error_spans"],
        summary["failed_tool_calls"],
        ",".join(trace.root.attributes.get("tool_errors") or []) or "-",  # type: ignore[arg-type]
        summary["dropped_spans"],
    )


def sse_event(name: str, payload: dict[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def stream_chat(
    request: Request,
    service: ChatbotService,
    inbound: InboundRequest,
    principal: PrincipalContext,
    request_context: RequestContext,
    on_finish: Callable[[], Awaitable[None]] | None = None,
    trace: Trace | None = None,
    trace_store: TraceRepository | None = None,
) -> StreamingResponse:
    """on_finish chạy khi stream kết thúc vì bất kỳ lý do gì (xong, lỗi, client ngắt).

    trace (nếu có) được kích hoạt trong suốt stream, đóng khi stream kết thúc, log
    một dòng tóm tắt và lưu qua trace_store (nếu có).
    """
    request_id = request_context.request_id
    session_id = inbound.session.session_id

    def error_event(code: str, message: str) -> str:
        set_outcome(request, code)
        return sse_event("error", {"code": code, "message": message, "request_id": request_id})

    async def event_stream() -> AsyncIterator[str]:
        with activate(trace):
            try:
                async with aclosing(_events()) as events:
                    async for event in events:
                        yield event
            finally:
                if on_finish is not None:
                    with span("session.lease_release", "db"):
                        await on_finish()
                if trace is not None:
                    await _finish_trace(trace)

    async def _finish_trace(finished: Trace) -> None:
        # Không có outcome: stream bị đóng trước khi có done/error (client ngắt).
        outcome = getattr(request.state, "outcome", None) or "client_disconnected"
        finished.finish(STATUS_OK if outcome == "ok" else outcome)
        log_trace_summary(finished, outcome)
        if trace_store is None:
            return
        try:
            # Shield: vẫn ghi khi stream kết thúc vì client ngắt (task đang bị huỷ).
            with anyio.CancelScope(shield=True):
                await trace_store.save(
                    finished,
                    history_id=UUID(inbound.message.message_id),
                    session_id=UUID(session_id),
                    channel=request_context.channel.value,
                    outcome=outcome,
                )
        except Exception:
            logger.exception("failed to save chat trace trace_id=%s", finished.trace_id)

    async def _events() -> AsyncIterator[str]:
        try:
            # aclosing: khi client ngắt và generator này bị đóng, stream_reply cũng
            # được đóng ngay (không chờ GC) để kịp ghi lượt status='cancelled'.
            deltas = 0
            async with aclosing(service.stream_reply(inbound, principal, request_context)) as replies:
                async for chunk in replies:
                    deltas += 1
                    if trace is not None:
                        if deltas == 1:
                            trace.root.set(first_delta_ms=round(trace.duration_ms))
                        trace.root.set(deltas=deltas)
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
        except AgentError as error:
            logger.exception(
                "Chat agent failed code=%s (request_id=%s session_id=%s)",
                error.code,
                request_id,
                session_id,
            )
            yield error_event(
                "agent_error",
                "The assistant could not complete the request. Please try again.",
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
