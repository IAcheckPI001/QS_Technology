import asyncio
import json
import time

import pytest

from app.modules.chatbot.agent import AgentError, AgentLimits, AgentRunner
from app.modules.chatbot.schemas.system import ConversationMessage, LLMCapabilities, LLMStage
from app.modules.chatbot.tools import ToolRegistry
from tests.chatbot.agent_fakes import (
    ScriptedToolProvider,
    ToolProbe,
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


def _echo(call_id, text, name="echo"):
    return call_id, name, {"text": text}


# --- giao thức tool-call -----------------------------------------------------------

def test_tool_call_then_answer_returns_single_final_chunk():
    provider = ScriptedToolProvider([calls(_echo("c1", "hi")), answer("Kết quả: hi")])
    state = crm_state("Xin chào")

    chunks = _run(agent_runner(provider, ToolRegistry([echo_tool()])), state)

    assert chunks == ["Kết quả: hi"]
    assert [call.tool_choice for call in provider.calls] == ["auto", "auto"]
    second = provider.calls[1].messages
    assert second[-2]["role"] == "assistant"
    assert second[-2]["tool_calls"][0]["id"] == "c1"
    assert second[-1] == {"role": "tool", "tool_call_id": "c1", "content": '{"text": "hi"}'}
    assert [(step.kind, step.name, step.status) for step in state.agent.steps] == [
        ("llm", "auto", "ok"), ("tool", "echo", "ok"), ("llm", "auto", "ok"),
    ]
    assert [call.stage for call in state.stats.llm_calls] == [LLMStage.THINK, LLMStage.THINK]


def test_tools_are_sent_via_tools_parameter_not_prompt():
    provider = ScriptedToolProvider([answer("ok")])

    _run(agent_runner(provider, ToolRegistry([echo_tool()])), crm_state())

    call = provider.calls[0]
    assert [tool["function"]["name"] for tool in call.tools] == ["echo"]
    assert "echo" not in call.messages[0]["content"]


def test_content_alongside_tool_calls_is_not_yielded_but_kept_for_protocol():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "hi"), content="Để tôi tra cứu..."),
        answer("Câu trả lời"),
    ])

    chunks = _run(agent_runner(provider, ToolRegistry([echo_tool()])), crm_state())

    assert chunks == ["Câu trả lời"]
    assert provider.calls[1].messages[-2]["content"] == "Để tôi tra cứu..."


def test_every_tool_call_id_gets_exactly_one_tool_message_in_call_order():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "a"), ("c2", "missing", {}), ("c3", "echo", "{bad"), _echo("c4", "d")),
        answer("xong"),
    ])

    _run(agent_runner(provider, ToolRegistry([echo_tool()])), crm_state())

    messages = tool_messages(provider.calls[1].messages)
    assert [message["tool_call_id"] for message in messages] == ["c1", "c2", "c3", "c4"]
    assert [json.loads(message["content"]).get("error") for message in messages] == [
        None, "tool_not_found", "tool_invalid_args", None,
    ]


def test_failed_tool_does_not_abort_the_turn():
    provider = ScriptedToolProvider([
        calls(("c1", "broken", {"text": "a"}), _echo("c2", "b")),
        answer("Một phần chưa tra cứu được"),
    ])
    registry = ToolRegistry([echo_tool(name="broken", fail=True), echo_tool()])

    assert _run(agent_runner(provider, registry), crm_state()) == ["Một phần chưa tra cứu được"]
    contents = [json.loads(m["content"]) for m in tool_messages(provider.calls[1].messages)]
    assert contents == [{"error": "tool_failed"}, {"text": "b"}]


def test_empty_answer_is_retried_once_with_tool_choice_none():
    provider = ScriptedToolProvider([answer(""), answer("Trả lời")])

    assert _run(agent_runner(provider, ToolRegistry([echo_tool()])), crm_state()) == ["Trả lời"]
    assert [call.tool_choice for call in provider.calls] == ["auto", "none"]


def test_empty_answer_twice_is_an_agent_error():
    provider = ScriptedToolProvider([answer(" "), answer("")])

    with pytest.raises(AgentError) as error:
        _run(agent_runner(provider, ToolRegistry([echo_tool()])), crm_state())
    assert error.value.code == "agent_empty_answer"


def test_answer_cut_by_max_tokens_is_still_returned(caplog):
    provider = ScriptedToolProvider([answer("Câu trả lời bị cắt", finish_reason="length")])

    assert _run(agent_runner(provider, ToolRegistry([echo_tool()])), crm_state()) == [
        "Câu trả lời bị cắt",
    ]
    assert "agent answer truncated" in caplog.text


def test_history_and_current_message_are_sent_after_system_prompt():
    history = [
        ConversationMessage(role="user", content="Lắp đặt Astro 6A?", message_id="h1:user"),
        ConversationMessage(role="assistant", content="Astro 6AH hay Astro 6AV?", message_id="h1:a"),
    ]
    provider = ScriptedToolProvider([answer("ok")])

    _run(agent_runner(provider, ToolRegistry([echo_tool()])), crm_state("6AV", history=history))

    messages = provider.calls[0].messages
    assert messages[0]["role"] == "system" and "<now>" in messages[0]["content"]
    # <now> trước guide của tool: đặt cuối prompt thì model hay bỏ qua và tự điền năm sai.
    system = messages[0]["content"]
    assert "<tool_guides>" not in system or system.index("<now>") < system.index("<tool_guides>")
    assert [m["content"] for m in messages[1:]] == [
        "Lắp đặt Astro 6A?", "Astro 6AH hay Astro 6AV?", "6AV",
    ]


# --- giới hạn bước / tool call -----------------------------------------------------

def test_step_limit_forces_final_answer_without_tools():
    provider = ScriptedToolProvider([
        calls(_echo("c1", "a")),
        calls(_echo("c2", "b")),
        answer("Trả lời với dữ liệu đang có"),
    ])

    chunks = _run(agent_runner(provider, ToolRegistry([echo_tool()]), max_steps=2), crm_state())

    assert chunks == ["Trả lời với dữ liệu đang có"]
    assert [call.tool_choice for call in provider.calls] == ["auto", "auto", "none"]


def test_tool_call_budget_answers_skipped_calls_and_stops():
    probe = ToolProbe()
    provider = ScriptedToolProvider([
        calls(_echo("c1", "a"), _echo("c2", "b"), _echo("c3", "c")),
        answer("xong"),
    ])
    registry = ToolRegistry([echo_tool(probe=probe)])
    state = crm_state()

    _run(agent_runner(provider, registry, max_tool_calls=2), state)

    contents = [json.loads(m["content"]) for m in tool_messages(provider.calls[1].messages)]
    assert contents == [{"text": "a"}, {"text": "b"}, {"error": "tool_budget_exhausted"}]
    assert provider.calls[1].tool_choice == "none"
    assert [s.status for s in state.agent.steps if s.kind == "tool"] == [
        "ok", "ok", "tool_budget_exhausted",
    ]


# --- deadline chung ----------------------------------------------------------------

def test_slow_tool_is_bounded_by_turn_deadline_and_final_answer_still_runs():
    provider = ScriptedToolProvider([calls(_echo("c1", "slow")), answer("Chưa tra cứu kịp")])
    registry = ToolRegistry([echo_tool(delay=5.0)])
    state = crm_state()
    started = time.monotonic()

    chunks = _run(agent_runner(
        provider, registry,
        turn_timeout_s=0.6, final_reserve_s=0.3, tool_timeout_s=20, llm_timeout_s=20,
    ), state)

    assert chunks == ["Chưa tra cứu kịp"]
    assert time.monotonic() - started < 1.0
    assert [s.status for s in state.agent.steps if s.kind == "tool"] == ["tool_timeout"]
    assert provider.calls[-1].tool_choice == "none"


def test_turn_without_time_for_final_answer_is_agent_timeout():
    async def slow_turn():
        await asyncio.sleep(5)

    provider = ScriptedToolProvider([slow_turn, slow_turn])
    started = time.monotonic()

    with pytest.raises(AgentError) as error:
        _run(agent_runner(
            provider, ToolRegistry([echo_tool()]),
            turn_timeout_s=0.4, final_reserve_s=0.1, llm_timeout_s=20,
        ), crm_state())

    assert error.value.code == "agent_timeout"
    assert time.monotonic() - started < 0.8


# --- song song ---------------------------------------------------------------------

def test_concurrency_safe_read_only_tools_run_in_parallel():
    probe = ToolProbe()
    provider = ScriptedToolProvider([
        calls(_echo("c1", "a"), _echo("c2", "b"), _echo("c3", "c")),
        answer("xong"),
    ])

    _run(agent_runner(provider, ToolRegistry([echo_tool(delay=0.05, probe=probe)])), crm_state())

    assert probe.max_running == 3


def test_parallel_tools_are_capped():
    probe = ToolProbe()
    provider = ScriptedToolProvider([
        calls(*[_echo(f"c{i}", str(i)) for i in range(5)]),
        answer("xong"),
    ])

    _run(agent_runner(provider, ToolRegistry([echo_tool(delay=0.05, probe=probe)]),
                      parallel_tools=2), crm_state())

    assert probe.max_running == 2


def test_batch_with_unsafe_tool_runs_sequentially():
    probe = ToolProbe()
    provider = ScriptedToolProvider([
        calls(_echo("c1", "a"), ("c2", "unsafe", {"text": "b"})),
        answer("xong"),
    ])
    registry = ToolRegistry([
        echo_tool(delay=0.05, probe=probe),
        echo_tool(name="unsafe", delay=0.05, probe=probe, concurrency_safe=False),
    ])

    _run(agent_runner(provider, registry), crm_state())

    assert probe.max_running == 1


def test_provider_without_parallel_tool_calls_runs_sequentially():
    probe = ToolProbe()
    capabilities = LLMCapabilities(tool_calling=True, tool_choice_none=True,
                                   schema_dialect="openai_strict")
    provider = ScriptedToolProvider(
        [calls(_echo("c1", "a"), _echo("c2", "b")), answer("xong")],
        capabilities=capabilities,
    )

    _run(agent_runner(provider, ToolRegistry([echo_tool(delay=0.05, probe=probe)])), crm_state())

    assert probe.max_running == 1
    assert provider.calls[0].parallel_tool_calls is False


def test_concurrent_runs_are_limited_per_process():
    gate = asyncio.Event()
    started = []

    async def blocked_answer():
        started.append(1)
        await gate.wait()
        return answer("ok")

    provider = ScriptedToolProvider([blocked_answer, blocked_answer])
    runner = agent_runner(provider, ToolRegistry([echo_tool()]), max_concurrent_runs=1)

    async def scenario():
        async def collect():
            return [chunk async for chunk in runner.run(crm_state())]

        first = asyncio.create_task(collect())
        second = asyncio.create_task(collect())
        await asyncio.sleep(0.05)
        assert len(started) == 1
        gate.set()
        return await first, await second

    assert asyncio.run(scenario()) == (["ok"], ["ok"])


def test_calls_skipped_for_lack_of_time_are_reported_as_timeout():
    probe = ToolProbe()
    clock = {"now": 0.0}

    def slow_calls():
        clock["now"] += 0.29          # bước LLM dùng gần hết thời gian ngoài phần dự phòng
        return calls(_echo("c1", "a"))

    provider = ScriptedToolProvider([slow_calls, answer("Hết giờ, trả lời phần đã có")])
    runner = AgentRunner(
        provider,
        ToolRegistry([echo_tool(probe=probe)]),
        AgentLimits(turn_timeout_s=0.6, final_reserve_s=0.3, llm_timeout_s=20),
        clock=lambda: clock["now"],
    )

    chunks = _run(runner, crm_state())

    assert chunks == ["Hết giờ, trả lời phần đã có"]
    assert probe.max_running == 0
    [message] = tool_messages(provider.calls[1].messages)
    assert json.loads(message["content"]) == {"error": "tool_timeout"}
    assert provider.calls[1].tool_choice == "none"
