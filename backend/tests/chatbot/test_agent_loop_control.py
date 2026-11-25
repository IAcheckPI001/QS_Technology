"""Đợt 1 gói C1–C3: tín hiệu tool, dừng sớm, báo ngân sách và bước chốt có cấu trúc."""

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.modules.chatbot.agent.prompts import final_step_note
from app.modules.chatbot.services.turn_sources import retrieval_view
from app.modules.chatbot.tools import ToolOutcome, ToolOutput, ToolRegistry
from app.modules.chatbot.tools.crm_query import AppliedRawQuery, QueryOutput, query_progress
from app.modules.chatbot.tools.product_docs import ProductDocsAskOutput, docs_progress
from tests.chatbot.agent_fakes import (
    ScriptedToolProvider,
    agent_runner,
    answer,
    calls,
    crm_state,
    echo_tool,
    tool_messages,
)


def _run(runner, state):
    async def collect():
        return [chunk async for chunk in runner.run(state)]

    return asyncio.run(collect())


def _signal(output) -> str:
    """echo: "empty" → rỗng, "pick" → mơ hồ, còn lại → ok."""
    return {"empty": "empty", "pick": "ambiguous"}.get(output.text, "ok")


def _tool(name="echo", **kwargs):
    return replace(echo_tool(name, **kwargs), progress=_signal)


def _echo(call_id, text, name="echo"):
    return call_id, name, {"text": text}


def _system_notes(messages):
    return [message["content"] for message in messages[1:] if message["role"] == "system"]


# ---------------------------------------------------------------- báo ngân sách (C2)


def test_each_tool_message_carries_remaining_budget():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "a"), _echo("c2", "b")),
        answer("xong"),
    ])

    _run(agent_runner(provider, ToolRegistry([_tool()]), max_steps=4, max_tool_calls=5), crm_state())

    budgets = [json.loads(m["content"])["turn_budget"]
               for m in tool_messages(provider.calls[1].messages, keep_budget=True)]
    assert budgets == [{"steps_left": 3, "tool_calls_left": 3}] * 2


def test_budget_key_does_not_push_output_over_the_token_budget():
    seen = []

    class Sized(ToolOutput):
        def to_llm(self, budget_tokens, count):
            seen.append(budget_tokens)
            return {"text": "x"}

    outcome = ToolOutcome(tool_call_id="c1", name="t", output=Sized())
    extra = {"turn_budget": {"steps_left": 1, "tool_calls_left": 2}}
    content = outcome.message_content(100, len, extra)

    assert seen == [100 - len(json.dumps(extra, ensure_ascii=False))]
    assert json.loads(content) == {"text": "x", **extra}
    error = ToolOutcome(tool_call_id="c2", name="t", error_code="tool_failed")
    assert json.loads(error.message_content(100, len, extra)) == {"error": "tool_failed", **extra}


# ---------------------------------------------------------------- dừng sớm (C1) và bước chốt (C3)


def test_answer_without_early_stop_is_answered():
    provider = ScriptedToolProvider([calls(_echo("c1", "a")), answer("xong")])
    state = crm_state()

    assert _run(agent_runner(provider, ToolRegistry([_tool()])), state) == ["xong"]
    assert state.agent.final_reason == "answered"
    assert _system_notes(provider.calls[-1].messages) == []


def test_ambiguous_signal_stops_and_asks_for_clarification():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "pick")),
        answer("Có 2 người tên Hùng, anh/chị chọn ai?"),
    ])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([_tool()])), state)

    assert state.agent.final_reason == "ambiguous"
    assert provider.calls[1].tool_choice == "none"       # bước chốt, không gọi tool thêm
    [note] = _system_notes(provider.calls[1].messages)
    assert "mơ hồ" in note and "mục 3 là bắt buộc" in note


def test_two_failed_steps_of_the_same_tool_is_a_plateau():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "empty")),
        calls(_echo("c2", "empty")),
        answer("Chưa tìm thấy dữ liệu"),
    ])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([_tool()]), max_tool_calls=8), state)

    assert state.agent.final_reason == "plateau"
    assert [call.tool_choice for call in provider.calls] == ["auto", "auto", "none"]
    assert "rỗng hoặc lỗi" in _system_notes(provider.calls[2].messages)[0]


def test_parallel_empty_calls_in_one_step_are_not_a_plateau():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "empty"), _echo("c2", "empty 2")),
        answer("xong"),
    ])
    registry = ToolRegistry([replace(echo_tool(), progress=lambda output: "empty")])
    state = crm_state()

    _run(agent_runner(provider, registry, max_tool_calls=8), state)

    assert state.agent.final_reason == "answered"


def test_success_resets_the_failed_streak():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "empty")),
        calls(_echo("c2", "a")),
        calls(_echo("c3", "empty")),
        answer("xong"),
    ])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([_tool()]), max_tool_calls=8), state)

    assert state.agent.final_reason == "answered"


def test_half_of_tool_calls_used_without_result_stops_on_budget():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "x", name="broken")),
        calls(_echo("c2", "empty")),
        answer("Chưa lấy được"),
    ])
    registry = ToolRegistry([_tool("broken", fail=True), _tool()])
    state = crm_state()

    _run(agent_runner(provider, registry, max_tool_calls=4), state)

    assert state.agent.final_reason == "budget"
    assert provider.calls[2].tool_choice == "none"


def test_turn_input_token_budget_stops_the_loop():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "a")),          # mỗi bước giả 10 token vào
        calls(_echo("c2", "b")),
        answer("Phần đã có"),
    ])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([_tool()]), turn_input_budget=15), state)

    assert state.agent.final_reason == "budget"
    assert [call.tool_choice for call in provider.calls] == ["auto", "auto", "none"]


def test_zero_turn_input_budget_disables_the_token_stop():
    provider = ScriptedToolProvider([calls(_echo("c1", "a")), calls(_echo("c2", "b")), answer("xong")])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([_tool()]), turn_input_budget=0), state)

    assert state.agent.final_reason == "answered"


def test_running_out_of_steps_ends_with_limit_and_structured_note():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "a")),
        calls(_echo("c2", "b")),
        answer("Phần đã xác minh: a, b"),
    ])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([_tool()]), max_steps=2), state)

    assert state.agent.final_reason == "limit"
    [note] = _system_notes(provider.calls[-1].messages)
    assert "Phần đã xác minh" in note and "thử lại sau" in note   # cấm nói "thử lại sau"


def test_empty_answer_retry_has_no_structured_note():
    provider = ScriptedToolProvider([calls(_echo("c1", "a")), answer(""), answer("xong")])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([_tool()])), state)

    assert state.agent.final_reason == "no_answer"
    assert _system_notes(provider.calls[-1].messages) == []
    assert final_step_note("answered") is None and final_step_note("no_answer") is None


# ---------------------------------------------------------------- tín hiệu của từng tool


def _query_output(rows, *, dataset="user_profiles", filters=("first_name contains Hùng",), mode="list"):
    return QueryOutput(
        applied=AppliedRawQuery(dataset=dataset, mode=mode, filters=list(filters), date_range=None,
                                order_by=[], limit=20, offset=0),
        columns=["user_id", "user_id.is_active", "first_name"],
        rows=rows, returned=len(rows), total=len(rows), has_more=False, next_offset=None,
    )


def test_crm_query_progress():
    active, inactive = {"user_id.is_active": True}, {"user_id.is_active": False}

    assert query_progress(_query_output([])) == "empty"
    assert query_progress(_query_output([active, dict(active)])) == "ambiguous"
    assert query_progress(_query_output([active, inactive])) == "ok"
    assert query_progress(_query_output([{}, {}])) == "ambiguous"      # không chọn cột trạng thái
    assert query_progress(_query_output([active, active], filters=["first_name eq Hùng"])) == "ok"
    assert query_progress(_query_output([active, active], dataset="tickets")) == "ok"
    assert query_progress(_query_output([active, active], mode="aggregate")) == "ok"


def test_product_docs_progress():
    assert docs_progress(ProductDocsAskOutput(status="needs_clarification")) == "ambiguous"
    assert docs_progress(ProductDocsAskOutput(status="no_docs")) == "empty"
    assert docs_progress(ProductDocsAskOutput(status="answered")) == "ok"


# ---------------------------------------------------------------- lưu vết và cấu hình


def test_retrieval_view_exposes_final_reason():
    row = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001", query_origin="q", status="completed",
        retrieval_snapshot={"chunks": [], "final_reason": "plateau"},
    )
    view = retrieval_view("00000000-0000-0000-0000-000000000002", row)
    assert view.final_reason == "plateau"
    row.retrieval_snapshot = {"chunks": []}
    assert retrieval_view("00000000-0000-0000-0000-000000000002", row).final_reason is None


def test_turn_input_budget_setting(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host/db")
    monkeypatch.delenv("AGENT_TURN_INPUT_BUDGET", raising=False)
    assert Settings(_env_file=None).agent_turn_input_budget == 40000
    monkeypatch.setenv("AGENT_TURN_INPUT_BUDGET", "-1")
    with pytest.raises(ValueError):
        Settings(_env_file=None)

def test_budget_and_limit_notes_put_enough_results_first_and_do_not_claim_missing_data():
    # LC-7 (2026-11-20): "… mà chưa đủ kết quả" làm LLM nói sai "chưa lấy được" dù dữ liệu đã đủ.
    for reason in ("budget", "limit"):
        note = final_step_note(reason)
        assert "chưa đủ kết quả" not in note
        assert note.index("đã đủ trả lời thì trả lời bình thường") < note.index("1. Phần đã xác minh")
        assert "KHÔNG nói thiếu dữ liệu" in note
    for reason in ("ambiguous", "plateau"):
        assert "Trả lời ngay theo khung" in final_step_note(reason)
