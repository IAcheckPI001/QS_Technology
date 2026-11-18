import pytest

from app.modules.chatbot.services.turn_sources import summarize_turn, tool_usage, turn_flags


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


def test_turn_flags_from_snapshot_and_state():
    snapshot = {"agent_steps": [
        {"kind": "tool", "name": "crm_query", "status": "tool_invalid_args"},
        {"kind": "tool", "name": "crm_query", "status": "ok"},
    ]}
    state = {"mode": "bot", "last_intent": "handoff.request", "last_models": ["QS-1325"], "ticket_id": "T-9"}
    assert turn_flags(snapshot, state) == {
        "has_tool_errors": True,
        "is_handoff": True,
        "product_models": ["QS-1325"],
        "ticket_id": "T-9",
    }


@pytest.mark.parametrize("state, handoff", [
    ({"mode": "with_agent"}, True),
    ({"mode": "awaiting_agent"}, True),
    ({"mode": "bot", "last_intent": "product.spec"}, False),
    (None, False),
])
def test_turn_flags_handoff(state, handoff):
    assert turn_flags(None, state)["is_handoff"] is handoff


def test_turn_flags_defaults_for_missing_or_malformed_input():
    assert turn_flags(None, None) == {
        "has_tool_errors": False, "is_handoff": False, "product_models": [], "ticket_id": None,
    }
    flags = turn_flags({"agent_steps": "x"}, {"last_models": "QS", "ticket_id": ""})
    assert flags["product_models"] == [] and flags["ticket_id"] is None
