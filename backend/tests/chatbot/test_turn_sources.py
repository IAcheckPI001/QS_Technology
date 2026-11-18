import pytest

from app.modules.chatbot.services.turn_sources import summarize_turn, tool_usage


def _tool(name, status="ok"):
    return {"step": 1, "kind": "tool", "name": name, "status": status}


@pytest.mark.parametrize(
    "snapshot, source, status",
    [
        (None, "none", None),
        ({"chunks": [], "retrieval_status": "not_applicable"}, "direct", "not_applicable"),
        ({"chunks": [{"rank": 1}], "retrieval_status": "ok"}, "documents", "ok"),
        ({"chunks": [], "retrieval_status": "no_hits"}, "documents", "no_hits"),
        ({"chunks": [], "retrieval_status": "error"}, "documents", "error"),
        # Bản ghi cũ: chưa có retrieval_status nhưng có chunk.
        ({"chunks": [{"rank": 1}]}, "documents", None),
        ({"chunks": [], "retrieval_status": "not_applicable", "agent_steps": [_tool("crm_query")]}, "crm_data", "not_applicable"),
        ({"chunks": [{"rank": 1}], "retrieval_status": "ok", "agent_steps": [_tool("crm_schema")]}, "documents_and_crm", "ok"),
    ],
)
def test_answer_source_by_turn_kind(snapshot, source, status):
    summary = summarize_turn(snapshot)
    assert summary.answer_source == source
    assert summary.retrieval_status == status


def test_tool_usage_groups_by_name_and_counts_failures():
    steps = [
        {"step": 1, "kind": "llm", "name": "auto", "status": "ok"},
        _tool("crm_schema", "crm_query_invalid"),
        _tool("crm_schema", "deduplicated"),
        _tool("crm_schema", "tool_call_limit"),
        _tool("product_docs_ask"),
        _tool("crm_query"),
        "không phải dict",
        {"kind": "tool", "name": "", "status": "ok"},
    ]

    usage = tool_usage(steps)

    assert [(u.name, u.calls, u.failed) for u in usage] == [("crm_schema", 3, 2), ("crm_query", 1, 0)]
    assert usage[0].errors == {"crm_query_invalid": 1, "tool_call_limit": 1}
    assert summarize_turn({"chunks": [], "agent_steps": steps}).has_tool_errors is True


def test_malformed_snapshot_fields_are_ignored():
    summary = summarize_turn({"chunks": "x", "retrieval_status": 5, "agent_steps": {"a": 1}})
    assert summary.answer_source == "direct"
    assert summary.chunk_count == 0
    assert summary.tools == []
