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
    HistoryRepository,
)
from app.modules.chatbot.routers import router


def _client(repository) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_history_repository] = lambda: repository
    return TestClient(app)


async def _history(repository_rows, *, session_id):
    return repository_rows


class _TurnRepo:
    """Repository giả cho /history và /retrieval: dùng logic chọn lượt thật của HistoryRepository."""

    def __init__(self, rows, session_id=None):
        self.rows = rows
        self.session_id = session_id

    async def list_for_history(self, *, session_id):
        return self.rows

    latest_retrieval_turn = HistoryRepository.latest_retrieval_turn

    async def get_turn(self, *, session_id, history_id):
        if self.session_id is not None and session_id != self.session_id:
            return None
        return next((row for row in self.rows if row.id == history_id), None)


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
    response = _client(_TurnRepo(rows)).get(f"/chatbot/sessions/{session_id}/retrieval")

    assert response.status_code == 200
    body = response.json()
    assert body["history_id"] == str(history_id)
    assert body["highest_score"] == 0.92
    assert body["latency_ms"] == 124
    assert body["chunks"][0]["scopes"] == ["installation", "maintenance"]
    # Bản ghi cũ: chưa có nguồn của đoạn.
    assert body["chunks"][0]["doc_id"] is None
    assert body["sources"]["answer_source"] == "documents"


def test_retrieval_endpoint_returns_404_without_snapshot():
    rows = [SimpleNamespace(id=uuid4(), retrieval_snapshot=None)]

    response = _client(_TurnRepo(rows)).get(f"/chatbot/sessions/{uuid4()}/retrieval")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "retrieval_not_found"


def _turn(session_id, *, status="completed", snapshot=None, query="Câu hỏi"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(), session_id=session_id, query_origin=query, answer="Đáp", status=status,
        created_at=now, updated_date=now, channel="crm", model="gpt-4.1-mini",
        total_tokens=10, retrieval_snapshot=snapshot,
    )


_AGENT_SNAPSHOT = {
    "query": "Khách TK-1048 dùng model nào, cách cài home?",
    "retrieval_status": "ok",
    "retrieval_tasks": [{"task_id": "call_1:task-retrieve-q1", "status": "completed",
                         "error_code": None, "no_hits": False, "fallback": False}],
    "chunks": [{
        "rank": 1, "score": 0.83, "content": "How to configure…", "scopes": ["configuration"],
        "chunk_id": "c-1", "doc_id": "f54_operation_v02", "section_title": "How to configure",
        "section_path": ["2.3.2.4 Homing switch wiring diagram"], "source_id": "S1",
    }],
    "agent_steps": [
        {"step": 1, "kind": "llm", "name": "auto", "status": "ok", "latency_ms": 900},
        {"step": 1, "kind": "tool", "name": "crm_query", "tool_call_id": "call_0", "status": "ok"},
        {"step": 2, "kind": "tool", "name": "product_docs_ask", "tool_call_id": "call_1", "status": "ok"},
        {"step": 2, "kind": "tool", "name": "crm_schema", "tool_call_id": "call_2", "status": "crm_query_invalid"},
    ],
    "answered_without_tools": False,
    "invalid_citations": [],
}


def test_retrieval_by_history_id_returns_that_turn_with_sources():
    session_id = uuid4()
    first = _turn(session_id, snapshot=_AGENT_SNAPSHOT)
    latest = _turn(session_id, snapshot={"query": "Cảm ơn", "chunks": [], "retrieval_status": "not_applicable"})
    repo = _TurnRepo([first, latest], session_id)

    body = _client(repo).get(
        f"/chatbot/sessions/{session_id}/retrieval", params={"history_id": str(first.id)}
    ).json()

    assert body["history_id"] == str(first.id)
    assert body["turn_status"] == "completed"
    assert body["chunks"][0]["doc_id"] == "f54_operation_v02"
    assert body["chunks"][0]["source_id"] == "S1"
    assert body["sources"]["answer_source"] == "documents_and_crm"
    assert body["sources"]["has_tool_errors"] is True
    # Công cụ tra tài liệu không nằm trong tools (thể hiện qua chunk).
    assert [(t["name"], t["calls"], t["failed"]) for t in body["sources"]["tools"]] == [
        ("crm_query", 1, 0), ("crm_schema", 1, 1),
    ]
    assert body["sources"]["tools"][1]["errors"] == {"crm_query_invalid": 1}
    assert len(body["agent_steps"]) == 4
    assert body["retrieval_tasks"][0]["task_id"] == "call_1:task-retrieve-q1"

    direct = _client(repo).get(
        f"/chatbot/sessions/{session_id}/retrieval", params={"history_id": str(latest.id)}
    ).json()
    assert direct["chunks"] == []
    assert direct["sources"]["answer_source"] == "direct"


def test_retrieval_by_history_id_of_blocked_turn_is_empty_not_404():
    session_id = uuid4()
    blocked = _turn(session_id, status="blocked", snapshot=None)

    response = _client(_TurnRepo([blocked], session_id)).get(
        f"/chatbot/sessions/{session_id}/retrieval", params={"history_id": str(blocked.id)}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["turn_status"] == "blocked"
    assert body["chunks"] == []
    assert body["sources"]["answer_source"] == "none"


def test_retrieval_history_id_of_another_session_is_404():
    session_id = uuid4()
    turn = _turn(session_id, snapshot=_AGENT_SNAPSHOT)

    response = _client(_TurnRepo([turn], session_id)).get(
        f"/chatbot/sessions/{uuid4()}/retrieval", params={"history_id": str(turn.id)}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "history_not_found"


def test_history_items_carry_turn_sources():
    session_id = uuid4()
    rows = [
        _turn(session_id, snapshot=_AGENT_SNAPSHOT),
        _turn(session_id, snapshot={"chunks": [], "retrieval_status": "no_hits"}),
        _turn(session_id, status="blocked", snapshot=None),
    ]

    messages = _client(_TurnRepo(rows, session_id)).get(f"/chatbot/sessions/{session_id}/history").json()["messages"]

    assert [m["sources"]["answer_source"] for m in messages] == ["documents_and_crm", "documents", "none"]
    assert messages[0]["sources"]["chunk_count"] == 1
    assert messages[1]["sources"]["retrieval_status"] == "no_hits"
