import logging
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.request_context import is_valid_request_id, request_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware:
    """Pure ASGI middleware: request ID + thời gian xử lý (kể cả SSE).

    Đặt ở ranh giới NGOÀI CÙNG (bọc cả FastAPI app) để response 500 do
    ServerErrorMiddleware tạo ra cũng có X-Request-ID.

    trust_incoming_request_id=True chỉ nên bật khi reverse proxy (Nginx)
    luôn ghi đè X-Request-ID bằng $request_id; nếu không, client có thể
    tự đặt ID.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        trust_incoming_request_id: bool = False,
    ) -> None:
        self.app = app
        self.trust_incoming_request_id = trust_incoming_request_id

    def _resolve_request_id(self, scope: Scope) -> str:
        if self.trust_incoming_request_id:
            incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
            if is_valid_request_id(incoming):
                return incoming  # type: ignore[return-value]
        return str(uuid4())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # lifespan, websocket: đi thẳng
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        request_id = self._resolve_request_id(scope)

        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["request_started_at"] = started_at

        status_code: int | None = None
        ttfb_ms = None
        stream_completed = False
        failed = False
        token = request_id_var.set(request_id)

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, ttfb_ms, stream_completed
            if message["type"] == "http.response.start":
                status_code = message["status"]
                if ttfb_ms is None:
                    ttfb_ms = round(
                        (perf_counter() - started_at) * 1000, 2
                    )
                # Ghi đè: ID luôn là giá trị server đã chốt.
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            elif message["type"] == "http.response.body":
                if not message.get("more_body", False):
                    stream_completed = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            failed = True  # vẫn raise để server/Starlette xử lý
            raise
        finally:
            # CancelledError (BaseException) không vào except nhưng vẫn vào finally.
            duration_ms = round((perf_counter() - started_at) * 1000)
            if failed and status_code is None:
                status_code = 500  # server sẽ trả 500 cho client

            # Route ghi request.state.outcome (SSE luôn 200 nên status không đủ).
            outcome = state.get("outcome")
            if failed or (status_code is not None and status_code >= 500):
                level = logging.ERROR
            elif status_code is None or not stream_completed:
                level = logging.WARNING  # bị huỷ/ngắt trước khi gửi xong response
                outcome = outcome or "client_disconnected"
            else:
                level = logging.INFO

            logger.log(
                level,
                "http_request_finished request_id=%s method=%s path=%s "
                "status=%s outcome=%s ttfb_ms=%s duration_ms=%d stream_completed=%s",
                request_id,
                scope.get("method"),
                scope.get("path"),  # không log query string
                status_code,
                outcome or "-",
                ttfb_ms,
                duration_ms,
                stream_completed,
            )
            request_id_var.reset(token)