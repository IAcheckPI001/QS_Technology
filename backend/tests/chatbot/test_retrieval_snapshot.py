from types import SimpleNamespace

import pytest

from app.modules.chatbot.schemas.system import TaskKind, TaskStatus
from app.modules.chatbot.services import ChatbotService
from app.modules.chatbot.services.chat_service import retrieval_status


def _hit(score, content, page_start=None, page_end=None):
    return SimpleNamespace(
        score=score,
        content=content,
        domain="technical_docs",
        scopes=["installation"],
        control_interface=[],
        spec_attributes=[],
        page_start=page_start,
        page_end=page_end,
    )


def _trace(latency_ms, product_models):
    filters = SimpleNamespace(product_models=product_models)
    return SimpleNamespace(latency_ms=latency_ms, params=SimpleNamespace(filters=filters))


def _task(*hits, task_id="task-retrieve-q1", status=TaskStatus.COMPLETED, metadata=None, error=None):
    retrieval = SimpleNamespace(results=[SimpleNamespace(hits=list(hits))])
    return SimpleNamespace(
        task_id=task_id,
        kind=TaskKind.RETRIEVE,
        status=status,
        result=SimpleNamespace(retrieval=retrieval, metadata=metadata or {}, error=error),
    )


def _failed(task_id="task-retrieve-q2"):
    return SimpleNamespace(
        task_id=task_id,
        kind=TaskKind.RETRIEVE,
        status=TaskStatus.FAILED,
        result=SimpleNamespace(
            retrieval=None,
            metadata={"kind": "retrieve"},
            error=SimpleNamespace(code="retrieval_error"),
        ),
    )


def _chitchat():
    return SimpleNamespace(task_id="task-q9", kind=TaskKind.CHITCHAT,
                           status=TaskStatus.COMPLETED, result=None)


def test_snapshot_ranks_hits_across_tasks_by_score():
    state = SimpleNamespace(
        input=SimpleNamespace(message=SimpleNamespace(text="Máy F86 chạy xung bị lệch")),
        plan=SimpleNamespace(tasks=[
            _task(_hit(0.81, "c", 3, 17)),
            _chitchat(),
            _task(_hit(0.92, "a", 2, 2), _hit(0.87, "b")),
        ]),
        retrieval_traces=[_trace(90, ["F86"]), _trace(124, ["F86", "F10T"])],
    )
    service = SimpleNamespace(_provider=SimpleNamespace(model="gpt-4o-mini"))

    snapshot = ChatbotService._retrieval_snapshot(service, state)

    assert snapshot["latency_ms"] == 124
    assert snapshot["retrieval_status"] == "ok"
    assert [task["status"] for task in snapshot["retrieval_tasks"]] == ["completed", "completed"]
    assert snapshot["product_models"] == ["F86", "F10T"]
    assert [(c["rank"], c["content"]) for c in snapshot["chunks"]] == [
        (1, "a"), (2, "b"), (3, "c"),
    ]
    assert [c["page_label"] for c in snapshot["chunks"]] == ["page 2", None, "page 3 - 17"]


def test_snapshot_without_plan_has_no_chunks():
    state = SimpleNamespace(
        input=SimpleNamespace(message=SimpleNamespace(text="Xin chào")),
        plan=None,
        retrieval_traces=[],
    )
    service = SimpleNamespace(_provider=SimpleNamespace(model="gpt-4o-mini"))

    snapshot = ChatbotService._retrieval_snapshot(service, state)
    assert snapshot["chunks"] == []
    assert snapshot["retrieval_status"] == "not_applicable"
    assert snapshot["retrieval_tasks"] == []


@pytest.mark.parametrize("tasks, expected", [
    ([_chitchat()], "not_applicable"),
    ([_task(_hit(0.9, "a"))], "ok"),
    ([_task(metadata={"no_hits": "true"})], "no_hits"),
    ([_task(_hit(0.9, "a")), _failed()], "partial_error"),
    ([_failed("t1"), _failed("t2")], "error"),
    ([_task(status=TaskStatus.PENDING)], "incomplete"),
])
def test_retrieval_status_summarises_retrieve_tasks(tasks, expected):
    assert retrieval_status(tasks)[0] == expected


def test_retrieval_tasks_record_error_code_without_content():
    _, rows = retrieval_status([_failed(), _task(metadata={"fallback": "true"})])

    assert rows == [
        {"task_id": "task-retrieve-q2", "status": "failed", "error_code": "retrieval_error",
         "no_hits": False, "fallback": False},
        {"task_id": "task-retrieve-q1", "status": "completed", "error_code": None,
         "no_hits": False, "fallback": True},
    ]


def test_failed_retrieval_is_logged_with_session(caplog):
    state = SimpleNamespace(
        input=SimpleNamespace(message=SimpleNamespace(text="q"),
                              session=SimpleNamespace(session_id="s-1")),
        plan=SimpleNamespace(tasks=[_failed()]),
        retrieval_traces=[],
    )
    service = SimpleNamespace(_provider=SimpleNamespace(model="gpt-4o-mini"))

    with caplog.at_level("WARNING"):
        assert ChatbotService._retrieval_snapshot(service, state)["retrieval_status"] == "error"

    assert "retrieval failed status=error session_id=s-1 failed_tasks=1" in caplog.text


def _sourced_hit(score, chunk_id, source_id=None):
    hit = _hit(score, f"content {chunk_id}")
    hit.chunk_id = chunk_id
    hit.doc_id = "f54_operation_v02"
    hit.section_title = "Note"
    hit.section_path = ["2.3.2.4 Homing switch wiring diagram", "Note"]
    hit.source_id = source_id
    return hit


def test_snapshot_records_chunk_source_and_drops_duplicates_keeping_best_score():
    state = SimpleNamespace(
        input=SimpleNamespace(message=SimpleNamespace(text="q")),
        # Hai lần tra cứu cùng trả đoạn c-1: giữ một lần, điểm cao nhất.
        plan=SimpleNamespace(tasks=[
            _task(_sourced_hit(0.70, "c-1"), _sourced_hit(0.80, "c-2", "S2")),
            _task(_sourced_hit(0.90, "c-1", "S1")),
        ]),
        retrieval_traces=[],
    )
    service = SimpleNamespace(_provider=SimpleNamespace(model="gpt-4o-mini"))

    chunks = ChatbotService._retrieval_snapshot(service, state)["chunks"]

    assert [(c["rank"], c["chunk_id"], c["score"]) for c in chunks] == [(1, "c-1", 0.90), (2, "c-2", 0.80)]
    assert chunks[0]["doc_id"] == "f54_operation_v02"
    assert chunks[0]["section_path"] == ["2.3.2.4 Homing switch wiring diagram", "Note"]
    assert chunks[0]["source_id"] == "S1"


def test_snapshot_keeps_hits_without_chunk_id():
    state = SimpleNamespace(
        input=SimpleNamespace(message=SimpleNamespace(text="q")),
        plan=SimpleNamespace(tasks=[_task(_hit(0.9, "a"), _hit(0.8, "a"))]),
        retrieval_traces=[],
    )
    service = SimpleNamespace(_provider=SimpleNamespace(model="gpt-4o-mini"))

    chunks = ChatbotService._retrieval_snapshot(service, state)["chunks"]

    assert len(chunks) == 2
    assert chunks[0]["chunk_id"] is None and chunks[0]["section_path"] == []
