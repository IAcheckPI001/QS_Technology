"""Đợt 0 trên nền B3: sổ usage của trace, lời gọi ước tính, cached tokens của bước agent,
model của agent trong chat_history, luật username của guide crm_query."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError, APITimeoutError

from app.core.pricing import cost_usd, price_for
from app.core.tracing import Trace, UsageEntry, activate, record_usage, span
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.services import ChatbotService
from app.modules.chatbot.services.turn_sources import usage_info
from app.modules.chatbot.services.turn_usage import usage_from_trace
from app.modules.chatbot.tools import ToolRegistry
from tests.chatbot.agent_fakes import ScriptedToolProvider, agent_runner, answer, echo_tool
from tests.chatbot.builders import make_inbound, make_request_context, make_service_principal
from tests.chatbot.test_clarification import StoringHistoryRepository
from tests.chatbot.test_tracing import _FakeOpenAI, _Usage

MESSAGES = [{"role": "user", "content": "câu hỏi khá dài về bộ điều khiển"}]


def _provider(client) -> OpenAIProvider:
    provider = OpenAIProvider(api_key="test", model="gpt-4.1-mini")
    provider._client = client
    return provider


def _client(create):
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


# ---------------------------------------------------------------------------
# Sổ usage: không chịu trần span
# ---------------------------------------------------------------------------

def test_usage_is_complete_when_spans_are_dropped():
    provider = _provider(_FakeOpenAI())
    trace = Trace("req-12345678", max_spans=1)          # chỉ còn chỗ cho root

    async def main():
        with activate(trace):
            await provider.chat_complete_json(MESSAGES)
            await provider.embed(["x"])
            return [part async for part in provider.stream_chat(MESSAGES)]

    asyncio.run(main())
    usage = usage_from_trace(trace)

    assert trace.dropped_spans == 3
    assert (usage.llm_calls, usage.input_tokens, usage.output_tokens, usage.embedding_tokens) == (2, 70, 11, 6)
    assert usage.estimated_calls == 0


def test_spans_are_still_read_when_no_provider_wrote_the_ledger():
    trace = Trace("req-12345678")
    with activate(trace), span("llm.chat_tools", "llm", model="gpt-4.1-mini") as call:
        call.set(input_tokens=100, output_tokens=5)
    assert usage_from_trace(trace).input_tokens == 100


# ---------------------------------------------------------------------------
# Lời gọi không trả usage: ước tính khi có thể đã bị tính tiền
# ---------------------------------------------------------------------------

def test_interrupted_stream_is_estimated():
    provider = _provider(_FakeOpenAI())
    trace = Trace("req-12345678")

    async def main():
        with activate(trace):
            stream = provider.stream_chat(MESSAGES)
            first = await stream.__anext__()
            await stream.aclose()                       # client ngắt trước chunk usage cuối
            return first

    assert asyncio.run(main()) == "Xin "
    [entry] = trace.usage
    assert entry.estimated and entry.input_tokens > 0 and entry.output_tokens > 0
    usage = usage_from_trace(trace)
    assert usage.estimated_calls == 1 and usage.detail()["estimated_calls"] == 1


def test_timeout_is_estimated_but_rejected_request_is_not():
    request = httpx.Request("POST", "https://api.openai.test/v1/chat/completions")
    rejected = APIStatusError("bad request", response=httpx.Response(400, request=request), body=None)
    for error, expected in ((APITimeoutError(request=request), 1), (rejected, 0)):
        async def create(**kwargs):
            raise error

        trace = Trace("req-12345678")

        async def main():
            with activate(trace), pytest.raises(type(error)):
                await _provider(_client(create)).chat_complete_json(MESSAGES)

        asyncio.run(main())
        assert len(trace.usage) == expected
        assert all(entry.estimated for entry in trace.usage)


# ---------------------------------------------------------------------------
# Bước agent: cached tokens trên span của runner, trong TokenUsage và sổ usage
# ---------------------------------------------------------------------------

def test_tool_step_records_cached_input_tokens():
    usage = _Usage(500, 20)
    usage.prompt_tokens_details = SimpleNamespace(cached_tokens=384)

    async def create(**kwargs):
        message = SimpleNamespace(content="Xong", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=usage)

    trace = Trace("req-12345678")

    async def main():
        with activate(trace), span("llm.chat_tools", "llm", model="gpt-4.1-mini") as llm_span:
            turn = await _provider(_client(create)).chat_complete_tools(MESSAGES, [])
        return turn, llm_span

    turn, llm_span = asyncio.run(main())
    assert turn.usage.cached_input_tokens == 384
    assert llm_span.attributes["cached_input_tokens"] == 384
    assert usage_from_trace(trace).cached_input_tokens == 384


# ---------------------------------------------------------------------------
# chat_history: model của vòng lặp agent
# ---------------------------------------------------------------------------

class _AgentModelProvider(ScriptedToolProvider):
    model = "gpt-4.1-mini"

    async def chat_complete_tools(self, *args, **kwargs):
        turn = await super().chat_complete_tools(*args, **kwargs)
        record_usage(UsageEntry(kind="llm", model=self.model, input_tokens=1000,
                                cached_input_tokens=400, output_tokens=100))
        return turn


def _crm_turn(service, trace=None):
    async def collect():
        with activate(trace):
            return [part async for part in service.stream_reply(
                make_inbound("Có bao nhiêu khách?", channel=ChannelType.CRM),
                make_service_principal(),
                make_request_context(ChannelType.CRM),
            )]
    return asyncio.run(collect())


def test_agent_turn_records_agent_model_and_ledger_usage():
    shared = ScriptedToolProvider()                     # OPENAI_MODEL của dịch vụ: "test-model"
    loop = _AgentModelProvider(turns=[answer("Có 3 khách.")])
    repository = StoringHistoryRepository()
    service = ChatbotService(shared, repository, agent_runner=agent_runner(loop, ToolRegistry([echo_tool()])))

    _crm_turn(service, Trace("req-12345678"))

    row = repository.rows[-1]
    assert row.model == "gpt-4.1-mini"
    assert row.retrieval_snapshot["model"] == "gpt-4.1-mini"
    assert (row.input_tokens, row.output_tokens) == (1000, 100)
    expected = cost_usd(price_for("gpt-4.1-mini"), input_tokens=1000, cached_input_tokens=400, output_tokens=100)
    assert row.cost_usd == pytest.approx(expected)
    info = usage_info(row)
    assert (info.source, info.llm_calls, info.estimated_calls, info.cached_input_tokens) == ("trace", 1, 0, 400)


def test_website_turn_keeps_service_model():
    repository = StoringHistoryRepository()
    loop = _AgentModelProvider(turns=[])
    service = ChatbotService(ScriptedToolProvider(), repository,
                             agent_runner=agent_runner(loop, ToolRegistry([echo_tool()])))
    state = SimpleNamespace(request_context=make_request_context(ChannelType.WEBSITE))
    assert service._turn_model(state) == "test-model"
    assert service._turn_model(None) == "test-model"


# ---------------------------------------------------------------------------
# Guide crm_query
# ---------------------------------------------------------------------------

def test_guide_requires_identifiers_verbatim_from_tool_results():
    """LLM từng tự suy username thiếu @qstcnc.com, query rỗng tới hết lượt (LOG 2026-11-12)."""
    from app.modules.chatbot.tools.crm_query import CRM_QUERY_GUIDE

    assert "chỉ dùng NGUYÊN VĂN từ kết quả tool" in CRM_QUERY_GUIDE
    assert "không tự thêm/bỏ phần sau @" in CRM_QUERY_GUIDE
