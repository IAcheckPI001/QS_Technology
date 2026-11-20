"""Kiểm soát bằng code trong AgentRunner: tool call trùng và citation không hợp lệ."""

import asyncio
import json

from app.modules.chatbot.schemas.default import SourceMetadata
from app.modules.chatbot.schemas.system import (
    Candidate,
    RetrievalFilters,
    RetrievalParams,
    RetrievalTrace,
    Scores,
)
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


def _echo(call_id, arguments):
    return call_id, "echo", arguments


def _statuses(state):
    return [(step.tool_call_id, step.status) for step in state.agent.steps if step.kind == "tool"]


def test_identical_call_in_later_step_reuses_result():
    probe = ToolProbe()
    provider = ScriptedToolProvider([
        calls(_echo("c1", {"text": "hi"})),
        # Cùng argument, khác thứ tự key/khoảng trắng: vẫn là call trùng.
        calls(_echo("c2", '{ "text" :  "hi" }')),
        answer("Xong"),
    ])
    state = crm_state()
    registry = ToolRegistry([echo_tool(probe=probe)])

    assert _run(agent_runner(provider, registry), state) == ["Xong"]

    assert probe.max_running == 1 and _statuses(state) == [("c1", "ok"), ("c2", "deduplicated")]
    [message] = tool_messages(provider.calls[2].messages)[1:]
    assert message == {"role": "tool", "tool_call_id": "c2", "content": '{"text": "hi"}'}


def test_identical_calls_in_one_response_run_once():
    runs = []

    async def counted(arguments, context):
        runs.append(arguments.text)
        return await base.run(arguments, context)

    base = echo_tool()
    spec = type(base)(**{**base.__dict__, "run": counted})
    provider = ScriptedToolProvider([
        calls(_echo("c1", {"text": "a"}), _echo("c2", {"text": "b"}), _echo("c3", {"text": "a"})),
        answer("Xong"),
    ])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([spec])), state)

    assert sorted(runs) == ["a", "b"]
    assert _statuses(state) == [("c1", "ok"), ("c2", "ok"), ("c3", "deduplicated")]
    messages = tool_messages(provider.calls[1].messages)
    # Mỗi tool_call_id vẫn có đúng một message, theo thứ tự call.
    assert [(m["tool_call_id"], m["content"]) for m in messages] == [
        ("c1", '{"text": "a"}'), ("c2", '{"text": "b"}'), ("c3", '{"text": "a"}'),
    ]


def test_failed_call_may_be_retried():
    attempts = []

    async def flaky(arguments, context):
        attempts.append(arguments.text)
        if len(attempts) == 1:
            raise RuntimeError("boom")
        return await base.run(arguments, context)

    base = echo_tool()
    spec = type(base)(**{**base.__dict__, "run": flaky})
    provider = ScriptedToolProvider([
        calls(_echo("c1", {"text": "hi"})),
        calls(_echo("c2", {"text": "hi"})),
        answer("Xong"),
    ])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([spec])), state)

    assert attempts == ["hi", "hi"]
    assert _statuses(state) == [("c1", "tool_failed"), ("c2", "ok")]


def _trace_with_source(source_id):
    return RetrievalTrace(
        retrieval_id="r1",
        iteration=0,
        query="q",
        params=RetrievalParams(filters=RetrievalFilters()),
        candidates=[Candidate(
            chunk_id="1",
            source_id=source_id,
            selected=True,
            scores=Scores(),
            metadata=SourceMetadata(doc_id="doc", version=1, section="s"),
        )],
        latency_ms=1,
    )


def test_unknown_citations_are_removed_and_recorded():
    async def with_source(arguments, context):
        context.parent_state.add_trace(_trace_with_source("S1"))
        return await base.run(arguments, context)

    base = echo_tool()
    spec = type(base)(**{**base.__dict__, "run": with_source})
    provider = ScriptedToolProvider([
        calls(_echo("c1", {"text": "hi"})),
        answer("Lắp theo bước 1 [S1]. Bước 2 [S7]. Bước 3 [S7]."),
    ])
    state = crm_state()

    assert _run(agent_runner(provider, ToolRegistry([spec])), state) == [
        "Lắp theo bước 1 [S1]. Bước 2. Bước 3.",
    ]
    assert state.agent.invalid_citations == ["S7"]
    assert not state.agent.answered_without_tools


def test_answer_without_tools_is_flagged_and_citations_dropped():
    """Đợt 1 gói D: trích nguồn không có trong lượt nên câu trả lời bị bỏ và runner ép gọi tool một
    bước; câu trả lời cuối vẫn được lọc citation."""
    provider = ScriptedToolProvider([
        answer("F86 có 4 trục [S1]."),
        calls(_echo("c1", {"text": "F86"})),
        answer("F86 có 6 trục [S9]."),
    ])
    state = crm_state("F86 có mấy trục?")

    assert _run(agent_runner(provider, ToolRegistry([echo_tool()])), state) == ["F86 có 6 trục."]
    assert [call.tool_choice for call in provider.calls] == ["auto", "required", "auto"]
    assert provider.calls[1].messages[-1]["role"] == "system"
    assert not state.agent.answered_without_tools
    assert state.agent.invalid_citations == ["S9"]


def test_answer_without_tools_is_kept_when_no_source_is_needed():
    provider = ScriptedToolProvider([answer("Chào bạn, tôi có thể giúp gì?")])
    state = crm_state("Xin chào")

    assert _run(agent_runner(provider, ToolRegistry([echo_tool()])), state) == ["Chào bạn, tôi có thể giúp gì?"]
    assert state.agent.answered_without_tools
    assert len(provider.calls) == 1


def test_tool_requiring_message_forces_one_tool_call_only():
    """`requires_call` khớp tin nhắn: ép một lần; bước ép vẫn không gọi tool thì giữ câu trả lời."""
    from dataclasses import replace

    spec = replace(echo_tool(), requires_call=lambda message: "F54" in message)
    provider = ScriptedToolProvider([answer("F54 có 4 trục."), answer("F54 có 4 trục.")])
    state = crm_state("F54 có bao nhiêu trục")

    assert _run(agent_runner(provider, ToolRegistry([spec])), state) == ["F54 có 4 trục."]
    assert [call.tool_choice for call in provider.calls] == ["auto", "required"]


def test_product_docs_requires_a_call_when_a_registry_model_is_mentioned():
    from app.modules.chatbot.tools import build_product_docs_tool

    spec = build_product_docs_tool(pipeline=None)  # type: ignore[arg-type]
    assert spec.requires_call("F54 có bao nhiêu trục")
    assert not spec.requires_call("Xin chào, bạn là ai?")

    from app.modules.chatbot.tools.product_docs import PRODUCT_DOCS_DESCRIPTION, PRODUCT_DOCS_GUIDE
    assert "MỘT lần gọi" in PRODUCT_DOCS_DESCRIPTION
    assert "Chỉ nói \"khác\" khi CẢ HAI giá trị có trong nguồn" in PRODUCT_DOCS_GUIDE


def test_final_step_answer_is_also_checked():
    provider = ScriptedToolProvider([
        calls(_echo("c1", {"text": "hi"})),
        answer(""),                       # rỗng: thử lại ở bước cuối với tool_choice="none"
        answer("Kết quả [S3]"),
    ])
    state = crm_state()

    assert _run(agent_runner(provider, ToolRegistry([echo_tool()])), state) == ["Kết quả"]
    assert provider.calls[-1].tool_choice == "none"
    assert json.loads(tool_messages(provider.calls[-1].messages)[0]["content"]) == {"text": "hi"}
