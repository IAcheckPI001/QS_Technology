import logging
from types import SimpleNamespace

from app.modules.chatbot.schemas.system import Mode
from app.modules.chatbot.stages.context_loader import ContextLoader, load_conversation_state

PENDING = {"focus": "F20", "question_type": "choose", "candidates": ["F86", "F54"],
           "llm_raw": {"sub_queries": []}, "ttl": 2, "blocking": True}


def test_valid_state_is_loaded_unchanged():
    state, dropped = load_conversation_state({"mode": "with_agent", "last_models": ["F86"],
                                              "pending": PENDING, "ticket_id": "T-1"})

    assert dropped == []
    assert state.mode is Mode.WITH_AGENT and state.ticket_id == "T-1"
    assert state.pending.focus == "F20"


def test_unknown_fields_are_dropped_and_the_rest_kept():
    state, dropped = load_conversation_state({
        "mode": "awaiting_agent", "language": "vi", "removed_field": 1,
        "pending": {**PENDING, "old_pending_field": True},
    })

    assert dropped == ["removed_field", "pending.old_pending_field"]
    assert state.mode is Mode.AWAITING_AGENT and state.language == "vi"
    assert state.pending.candidates == ["F86", "F54"]


def test_invalid_field_is_dropped_without_resetting_mode():
    state, dropped = load_conversation_state({
        "mode": "with_agent",
        "ticket_id": "T-9",
        "last_models": ["A", "B", "C", "D", "E"],      # vượt MAX_LAST_MODELS
        "pending": {**PENDING, "ttl": -1},             # pending hỏng
        "active_model": "F86",
    })

    assert dropped == ["last_models", "pending"]
    assert state.mode is Mode.WITH_AGENT and state.ticket_id == "T-9"
    assert state.active_model == "F86"
    assert state.last_models == [] and state.pending is None


def test_empty_or_non_dict_state_falls_back_to_default():
    assert load_conversation_state(None) == (load_conversation_state({})[0], [])
    state, dropped = load_conversation_state(["not", "a", "dict"])
    assert dropped == ["<root>"] and state.mode is Mode.BOT


def test_loader_logs_session_and_field_names_only(caplog):
    histories = [SimpleNamespace(conversation_state={"mode": "with_agent", "secret_note": "PII"})]

    with caplog.at_level(logging.WARNING):
        state = ContextLoader._load_state(histories, "sess-1")

    assert state.mode is Mode.WITH_AGENT
    assert "session_id=sess-1 dropped_fields=secret_note" in caplog.text
    assert "PII" not in caplog.text
