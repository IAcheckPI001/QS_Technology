from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.v1.dependencies import get_history_repository
from app.modules.chatbot.router import router


def _client(repository) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_history_repository] = lambda: repository
    return TestClient(app)


async def _history(repository_rows, *, session_id):
    return repository_rows


def test_history_endpoint_returns_ordered_history():
    session_id = uuid4()
    history_id = uuid4()
    rows = [
        SimpleNamespace(
            id=history_id,
            session_id=session_id,
            query_origin="Xin chào",
            answer="Chào bạn",
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
    ]
    repository = SimpleNamespace(
        list_for_history=lambda *, session_id: _history(rows, session_id=session_id)
    )

    response = _client(repository).get(f"/chatbot/sessions/{session_id}/history")

    assert response.status_code == 200
    assert response.json()["session_id"] == str(session_id)
    assert response.json()["messages"][0]["answer"] == "Chào bạn"


def test_history_endpoint_returns_404_for_unknown_session():
    session_id = uuid4()
    repository = SimpleNamespace(
        list_for_history=lambda *, session_id: _history([], session_id=session_id)
    )

    response = _client(repository).get(f"/chatbot/sessions/{session_id}/history")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "session_not_found"


def test_history_endpoint_maps_database_failure():
    async def fail(*, session_id):
        raise OperationalError("select", {}, Exception("connection refused"))

    response = _client(SimpleNamespace(list_for_history=fail)).get(
        f"/chatbot/sessions/{uuid4()}/history"
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"
