"""Preflight CORS chạy qua app thật (app.main.app).

Widget chat không gọi dịch vụ AI từ trình duyệt nữa (đi qua widget-backend);
Support Workspace vẫn gọi thẳng các GET /chatbot/... nên còn cần CORS.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

ORIGIN = settings.cors_origins[0]


def _preflight(path: str, headers: str):
    return TestClient(app).options(path, headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": headers,
    })


@pytest.mark.parametrize("path, headers", [
    # Header axios (src/services/api.service.js) gửi cho Support Workspace.
    ("/chatbot/conversations", "content-type"),
    ("/chatbot/sessions/00000000-0000-0000-0000-000000000001/history", "content-type"),
])
def test_frontend_preflight_is_allowed(path, headers):
    response = _preflight(path, headers)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_unlisted_header_is_still_rejected():
    response = _preflight("/chatbot/conversations", "content-type, x-unknown")

    assert response.status_code == 400
