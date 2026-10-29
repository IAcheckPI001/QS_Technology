from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.modules.chatbot.dependencies import get_history_repository
from app.modules.chatbot.repositories.history_repository import (
    ConversationMetrics,
    ConversationRow,
)
from app.modules.chatbot.routers import router


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
            updated_date=datetime.now(timezone.utc),
            channel="website",
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


def test_conversations_endpoint_returns_session_summaries_and_metrics():
    session_id = uuid4()
    started = datetime(2026, 10, 19, 9, 5, tzinfo=timezone.utc)
    last = datetime(2026, 10, 22, 9, 27, tzinfo=timezone.utc)
    latest = SimpleNamespace(
        session_id=session_id,
        model="gpt-4o-mini",
        query_origin="Máy F86 chạy xung bị lệch",
        channel="crm",
        status="completed",
        conversation_state={"mode": "awaiting_agent", "last_models": ["F86"], "ticket_id": "TK-1048"},
    )
    calls = []

    async def list_conversations(*, search, status):
        calls.append((search, status))
        return [ConversationRow(latest, started, last, 120, 0.001)]

    async def aggregate_metrics():
        return ConversationMetrics(
            conversation_count=1, handoff_count=1, total_tokens=120, cost_usd=0.001
        )

    repository = SimpleNamespace(
        list_conversations=list_conversations,
        aggregate_metrics=aggregate_metrics,
    )

    response = _client(repository).get(
        "/chatbot/conversations", params={"search": "F86", "status": "completed"}
    )

    assert response.status_code == 200
    body = response.json()
    assert calls == [("F86", "completed")]
    assert body["conversations"][0]["channel"] == "crm"
    assert body["conversations"][0]["product_models"] == ["F86"]
    assert body["conversations"][0]["ticket_id"] == "TK-1048"
    assert body["conversations"][0]["created_at"].startswith("2026-10-19T09:05")
    assert body["conversations"][0]["updated_date"].startswith("2026-10-22T09:27")
    assert body["handoff_count"] == 1
    assert body["total_cost_vnd"] > 0


def test_conversations_endpoint_rejects_unknown_status():
    response = _client(SimpleNamespace()).get(
        "/chatbot/conversations", params={"status": "unknown"}
    )

    assert response.status_code == 422


def test_retrieval_endpoint_returns_latest_snapshot_with_chunks():
    session_id = uuid4()
    history_id = uuid4()
    snapshot = {
        "query": "Máy F86 chạy xung bị lệch",
        "model": "gpt-4o-mini",
        "latency_ms": 124,
        "chunks": [
            {
                "rank": 1,
                "score": 0.92,
                "content": "Hướng dẫn cấu hình xung",
                "domain": "technical_docs",
                "scopes": ["installation", "maintenance"],
                "control_interface": ["pulse_train"],
                "spec_attributes": ["io"],
                "page_start": 4,
                "page_end": 26,
                "page_label": "page 4 - 26",
            }
        ],
    }
    rows = [
        SimpleNamespace(
            id=history_id,
            query_origin=snapshot["query"],
            model="gpt-4o-mini",
            total_tokens=50,
            retrieval_snapshot=snapshot,
        ),
        # Lượt sau không có chunk (direct response) không che snapshot trước đó.
        SimpleNamespace(
            id=uuid4(),
            query_origin="Cảm ơn",
            model=None,
            total_tokens=0,
            retrieval_snapshot={"query": "Cảm ơn", "chunks": []},
        ),
    ]
    repository = SimpleNamespace(
        list_for_history=lambda *, session_id: _history(rows, session_id=session_id)
    )

    response = _client(repository).get(f"/chatbot/sessions/{session_id}/retrieval")

    assert response.status_code == 200
    body = response.json()
    assert body["history_id"] == str(history_id)
    assert body["highest_score"] == 0.92
    assert body["latency_ms"] == 124
    assert body["chunks"][0]["scopes"] == ["installation", "maintenance"]


def test_retrieval_endpoint_returns_404_without_snapshot():
    rows = [SimpleNamespace(id=uuid4(), retrieval_snapshot=None)]
    repository = SimpleNamespace(
        list_for_history=lambda *, session_id: _history(rows, session_id=session_id)
    )

    response = _client(repository).get(f"/chatbot/sessions/{uuid4()}/retrieval")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "retrieval_not_found"
