import logging

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from app.api.middleware.request_context import RequestContextMiddleware
from app.core.request_context import get_request_id, is_valid_request_id

LOGGER = "app.api.middleware.request_context"


def _client(*, trust: bool = False) -> TestClient:
    app = FastAPI()

    @app.get("/ok")
    async def ok(request: Request):
        request.state.outcome = "ok"
        return {"request_id": get_request_id(), "state_id": request.state.request_id}

    @app.get("/stream")
    async def stream():
        async def body():
            # Context var phải còn hiệu lực bên trong generator SSE.
            yield f"data: {get_request_id()}\n\n"

        return StreamingResponse(body(), media_type="text/event-stream")

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    return TestClient(
        RequestContextMiddleware(app, trust_incoming_request_id=trust),
        raise_server_exceptions=False,
    )


def test_server_generates_request_id_shared_by_header_state_and_context():
    response = _client().get("/ok")

    request_id = response.headers["X-Request-ID"]
    assert is_valid_request_id(request_id)
    assert response.json() == {"request_id": request_id, "state_id": request_id}


def test_request_id_is_available_inside_streaming_body():
    response = _client().get("/stream")

    assert response.text == f"data: {response.headers['X-Request-ID']}\n\n"


def test_incoming_request_id_is_ignored_unless_proxy_is_trusted():
    incoming = "proxy-request-0001"

    assert _client().get("/ok", headers={"X-Request-ID": incoming}).headers["X-Request-ID"] != incoming
    trusted = _client(trust=True).get("/ok", headers={"X-Request-ID": incoming})
    assert trusted.headers["X-Request-ID"] == incoming


def test_trusted_proxy_id_with_invalid_format_is_replaced():
    response = _client(trust=True).get("/ok", headers={"X-Request-ID": "bad id\r\ninjected"})

    assert response.headers["X-Request-ID"] != "bad id\r\ninjected"
    assert is_valid_request_id(response.headers["X-Request-ID"])


def test_unhandled_error_returns_500_with_request_id_and_error_log(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        response = _client().get("/boom")

    assert response.status_code == 500
    request_id = response.headers["X-Request-ID"]
    record = next(r for r in caplog.records if r.name == LOGGER)
    assert record.levelno == logging.ERROR
    assert f"request_id={request_id}" in record.getMessage()
    assert "status=500" in record.getMessage()


def test_access_log_includes_outcome_set_by_route(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        _client().get("/ok")

    message = next(r for r in caplog.records if r.name == LOGGER).getMessage()
    assert "status=200 outcome=ok" in message
    assert "stream_completed=True" in message
