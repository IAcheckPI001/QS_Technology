"""Preflight CORS chạy qua app thật (app.main.app), giống trình duyệt của widget."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

ORIGIN = settings.cors_origins[0]


def _preflight(path: str, headers: str):
    return TestClient(app).options(path, headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": headers,
    })


@pytest.mark.parametrize("path, headers", [
    # Đúng bộ header src/services/chatbot.service.js gửi.
    ("/chat/website", "content-type, accept, authorization, idempotency-key"),
    ("/chat/website/visitor", "content-type, authorization"),
])
def test_frontend_preflight_is_allowed(path, headers):
    response = _preflight(path, headers)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_unlisted_header_is_still_rejected():
    response = _preflight("/chat/website", "content-type, x-unknown")

    assert response.status_code == 400
