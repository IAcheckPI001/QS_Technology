"""Orchestrator trung lập với tool: luật, state và giới hạn theo khai báo của từng tool."""

import asyncio
from typing import Literal
from uuid import UUID

import pytest

from app.modules.chatbot.schemas.default import ChannelType, SystemModel
from app.modules.chatbot.services import ChatbotService
from app.modules.chatbot.tools import ToolConfigurationError, ToolOutput, ToolRegistry, ToolSpec
from app.modules.chatbot.tools.product_docs import PRODUCT_DOCS_GUIDE, build_product_docs_tool
from tests.chatbot.agent_fakes import (
    FakeChunks,
    ScriptedToolProvider,
    agent_runner,
    analysis_output,
    answer,
    ask,
    calls,
    chunk,
    crm_state,
    docs_pipeline,
    echo_tool,
    sub_query,
    tool_messages,
)
from tests.chatbot.builders import make_inbound, make_request_context, make_service_principal
from tests.chatbot.test_clarification import StoringHistoryRepository


class ReportTicketsIn(SystemModel):
    period: Literal["this_month", "last_month"]


class ReportTicketsOut(ToolOutput):
    period: str
    total: int


def report_tool(*, required_scope=None, guide="total là số ticket trong kỳ; nêu rõ kỳ báo cáo.",
                read_only=True, max_calls_per_turn=None, runs=None) -> ToolSpec:
    async def run(arguments: ReportTicketsIn, context) -> ReportTicketsOut:
        if runs is not None:
            runs.append(arguments.period)
        return ReportTicketsOut(period=arguments.period, total=42)

    return ToolSpec(
        name="report_tickets",
        description="Đếm số ticket hỗ trợ theo kỳ.",
        input_model=ReportTicketsIn,
        output_model=ReportTicketsOut,
        run=run,
        guide=guide,
        read_only=read_only,
        max_calls_per_turn=max_calls_per_turn,
        required_scope=required_scope,
    )


def _run(runner, state):
    async def collect():
        return [part async for part in runner.run(state)]

    return asyncio.run(collect())


def _system_prompt(registry):
    provider = ScriptedToolProvider([answer("ok")])
    _run(agent_runner(provider, registry), crm_state())
    return provider.calls[0].messages[0]["content"]


def _report(call_id, period="this_month"):
    return call_id, "report_tickets", {"period": period}


def _tool_statuses(state):
    return [(s.tool_call_id, s.status) for s in state.agent.steps if s.kind == "tool"]


# --- Luật theo tool ----------------------------------------------------------------------

def test_prompt_has_only_guides_of_allowed_tools():
    prompt = _system_prompt(ToolRegistry([echo_tool(), report_tool()]))

    assert '<tool_guide name="report_tickets">' in prompt
    assert "nêu rõ kỳ báo cáo" in prompt
    # Không có tool tra cứu tài liệu: không có luật về model/catalog.
    for product_rule in ("catalog_match", "model_not_evidenced", "has_technical_docs", "product_models"):
        assert product_rule not in prompt
    assert "echo" not in prompt     # tool không có guide thì không có mục riêng


def test_guide_of_tool_outside_principal_scope_is_not_sent():
    prompt = _system_prompt(ToolRegistry([echo_tool(), report_tool(required_scope="reports:read")]))

    assert "report_tickets" not in prompt


def test_product_docs_rules_come_with_the_tool():
    provider = ScriptedToolProvider([answer("ok")])
    registry = ToolRegistry([build_product_docs_tool(docs_pipeline(provider, FakeChunks()))])

    prompt = _system_prompt(registry)

    assert '<tool_guide name="product_docs_ask">' in prompt
    assert PRODUCT_DOCS_GUIDE.splitlines()[0] in prompt and "catalog_match.next_action" in prompt


# --- Hành vi theo khai báo của tool -------------------------------------------------------

def test_write_tool_is_never_deduplicated():
    runs = []
    provider = ScriptedToolProvider([
        calls(_report("c1"), _report("c2")),
        calls(_report("c3")),
        answer("Đã ghi"),
    ])
    state = crm_state()

    _run(agent_runner(provider, ToolRegistry([report_tool(read_only=False, runs=runs)])), state)

    assert runs == ["this_month"] * 3
    assert _tool_statuses(state) == [("c1", "ok"), ("c2", "ok"), ("c3", "ok")]


def test_per_tool_call_limit_blocks_only_that_tool():
    runs = []
    provider = ScriptedToolProvider([
        calls(_report("c1", "this_month"), _report("c2", "last_month"),
              ("c3", "echo", {"text": "hi"})),
        answer("Xong"),
    ])
    state = crm_state()
    registry = ToolRegistry([report_tool(max_calls_per_turn=1, runs=runs), echo_tool()])

    _run(agent_runner(provider, registry), state)

    assert runs == ["this_month"]
    assert _tool_statuses(state) == [("c1", "ok"), ("c3", "ok"), ("c2", "tool_call_limit")]
    by_id = {m["tool_call_id"]: m["content"] for m in tool_messages(provider.calls[1].messages)}
    assert '"error": "tool_call_limit"' in by_id["c2"]
    # Mỗi tool_call_id vẫn có đúng một message, theo thứ tự call.
    assert list(by_id) == ["c1", "c2", "c3"]


def test_invalid_per_tool_limit_is_rejected_at_registration():
    with pytest.raises(ToolConfigurationError, match="max_calls_per_turn"):
        ToolRegistry([report_tool(max_calls_per_turn=0)])


# --- Tool không dùng model chạy cùng tool tra cứu tài liệu --------------------------------

def test_report_tool_and_docs_tool_in_one_turn():
    provider = ScriptedToolProvider(
        turns=[
            calls(_report("c1"), ask("c2", "Hướng dẫn lắp đặt F86")),
            answer("Tháng này có 42 ticket. Lắp F86: cấp nguồn 24V [S1]."),
        ],
        analysis_outputs=[analysis_output(
            sub_query("Hướng dẫn lắp đặt F86", "guide.installation", ["F86"]),
        )],
    )
    chunks = FakeChunks({("technical_docs", ("F86",)): [chunk(1)]})
    registry = ToolRegistry([report_tool(), build_product_docs_tool(docs_pipeline(provider, chunks))])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository, agent_runner=agent_runner(provider, registry))
    inbound = make_inbound("Tháng này bao nhiêu ticket? Hướng dẫn lắp đặt F86",
                           session_id=UUID("00000000-0000-0000-0000-0000000000c3"),
                           channel=ChannelType.CRM)

    async def collect():
        return [part async for part in service.stream_reply(
            inbound, make_service_principal(), make_request_context(ChannelType.CRM),
        )]

    reply = asyncio.run(collect())

    assert reply == ["Tháng này có 42 ticket. Lắp F86: cấp nguồn 24V [S1]."]
    row = repository.rows[-1]
    assert [(s["name"], s["status"]) for s in row.retrieval_snapshot["agent_steps"]
            if s["kind"] == "tool"] == [("report_tickets", "ok"), ("product_docs_ask", "ok")]
    assert row.normalized_query == "Hướng dẫn lắp đặt F86"
    # Ngữ cảnh model chỉ đổi theo tool có khái niệm model.
    assert row.conversation_state["last_models"] == ["F86"]
    payloads = tool_messages(provider.calls[1].messages)
    assert payloads[0]["content"] == '{"period": "this_month", "total": 42}'


def test_turn_with_only_report_tool_keeps_model_context():
    provider = ScriptedToolProvider(turns=[calls(_report("c1")), answer("Tháng này có 42 ticket.")])
    repository = StoringHistoryRepository()
    service = ChatbotService(
        provider, repository, agent_runner=agent_runner(provider, ToolRegistry([report_tool()])),
    )
    inbound = make_inbound("Tháng này bao nhiêu ticket?",
                           session_id=UUID("00000000-0000-0000-0000-0000000000c4"),
                           channel=ChannelType.CRM)

    async def collect():
        return [part async for part in service.stream_reply(
            inbound, make_service_principal(), make_request_context(ChannelType.CRM),
        )]

    asyncio.run(collect())

    row = repository.rows[-1]
    assert row.conversation_state["last_models"] == []
    assert row.normalized_query is None
    assert row.retrieval_snapshot["retrieval_status"] == "not_applicable"
