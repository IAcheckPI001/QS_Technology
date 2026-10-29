from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.v1.dependencies import get_learning_service
from app.api.v1.router import build_api_router
from app.core.config import settings
from app.modules.learning_ai.ingestion.service import LearningIngestionService
from app.modules.learning_ai.privacy.pipeline import PrivacyPipeline
from app.modules.learning_ai.privacy.sensitivity_checker import SensitivityChecker
from app.modules.learning_ai.router import router
from tests.learning_ai.builders import FakeProvider, FakeRepository, Row, finding, reviewing, word_count

CONVERSATION = [
    Row("Em là Minh, F86 lệch xung mỗi vòng, gọi em 0912345678", "Dạ anh Minh kiểm tra P01 giúp em"),
    Row("P01 đang là 5000", "Anh đặt P01 = 10000, phí hỗ trợ 500 ngàn nhé"),
]


def _client(service: LearningIngestionService | None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_learning_service] = lambda: service
    return TestClient(app)


def _service(rows, responder=None) -> LearningIngestionService:
    checker = SensitivityChecker(FakeProvider(responder or reviewing()), window_tokens=1000, token_counter=word_count)
    return LearningIngestionService(FakeRepository(rows), PrivacyPipeline(checker))


def _post(client: TestClient, body: dict):
    return client.post("/ai/learning", json=body)


def test_ready_returns_redacted_units_only():
    service = _service(CONVERSATION, reviewing(finding("m1", "pii", "person_name", "Minh")))

    res = _post(_client(service), {"session_id": str(uuid4())})

    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == res.json()["request_id"]
    body = res.json()
    assert body["status"] == "ready" and body["redaction_applied"] is True
    assert body["units"][0] == {"locator": "m1", "role": "customer",
                                "text": "Em là [PERSON_1], F86 lệch xung mỗi vòng, gọi em [PHONE_1]"}
    assert body["units"][3]["text"] == "Anh đặt P01 = 10000, phí hỗ trợ [PRICE_1] nhé"
    assert body["pii_types_detected"] == ["person_name", "phone"]
    assert body["flags_by_locator"] == {"m4": ["pricing"]}
    raw = res.text
    assert "Minh" not in raw and "0912345678" not in raw and "500 ngàn" not in raw


def test_skipped_conversation_returns_reason():
    res = _post(_client(_service([Row("xin chào", "dạ em chào anh")])), {"session_id": str(uuid4())})

    assert res.status_code == 200
    assert res.json()["status"] == "skipped"
    assert res.json()["reason"] == "greeting_only"
    assert res.json()["units"] == []


def test_unknown_session_returns_404():
    res = _post(_client(_service([])), {"session_id": str(uuid4())})

    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "session_not_found"


def test_missing_ollama_configuration_returns_503():
    res = _post(_client(None), {"session_id": str(uuid4())})

    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "privacy_provider_not_configured"


def test_privacy_failure_returns_generic_503():
    def broken(payload):
        raise TimeoutError("ollama timed out")

    res = _post(_client(_service(CONVERSATION, broken)), {"session_id": str(uuid4())})

    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "privacy_check_unavailable"
    assert "TimeoutError" not in res.text and "window" not in res.text


def test_database_error_returns_503():
    class BrokenRepository:
        async def list_for_session(self, *, session_id):
            raise OperationalError("select", {}, Exception("connection refused"))

    checker = SensitivityChecker(FakeProvider(reviewing()), window_tokens=1000, token_counter=word_count)
    service = LearningIngestionService(BrokenRepository(), PrivacyPipeline(checker))

    res = _post(_client(service), {"session_id": str(uuid4())})

    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "database_unavailable"


@pytest.mark.parametrize("body", [
    {"session_id": "not-a-uuid"},
    {"session_id": str(uuid4()), "schema_version": "2.0"},
    {"session_id": str(uuid4()), "unknown": True},
])
def test_invalid_request_returns_422(body):
    assert _post(_client(_service(CONVERSATION)), body).status_code == 422


@pytest.mark.parametrize("enabled, status_code", [(True, 503), (False, 404)])
def test_route_is_included_only_when_enabled(enabled, status_code):
    app = FastAPI()
    app.include_router(build_api_router(settings.model_copy(update={"learning_api_enabled": enabled})))
    app.dependency_overrides[get_learning_service] = lambda: None

    assert _post(TestClient(app), {"session_id": str(uuid4())}).status_code == status_code


def test_support_chat_routes_are_included_when_learning_api_is_enabled():
    app = FastAPI()
    app.include_router(build_api_router(settings.model_copy(update={"learning_api_enabled": True})))
    paths = set(app.openapi()["paths"])

    assert "/support-chat/sessions" in paths
    assert "/support-chat/sessions/{session_id}/messages" in paths
