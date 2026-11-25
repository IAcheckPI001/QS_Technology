"""LC-2 (LLM hết giờ: đo và thử lại) và LC-4 (lỗi cột: kiểm trước khi gửi CRM, bắt sửa một lần)."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.core.tracing import Trace, activate, span
from app.modules.chatbot.agent.prompts import REPAIR_NOTE
from app.modules.chatbot.providers.base import ProviderTransientError
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.reporting.raw.compile import unknown_column
from app.modules.chatbot.schemas.default import SystemModel
from app.modules.chatbot.tools import ToolArgumentError, ToolOutput, ToolRegistry, ToolSpec
from tests.chatbot.agent_fakes import ScriptedToolProvider, agent_runner, answer, calls, crm_state
from tests.chatbot.test_crm_query_tool import FakeCrmApi, _invoke, _ownerships_live, _tools

REQUEST = httpx.Request("POST", "https://api.openai.test/v1/chat/completions")


def _run(runner, state):
    async def collect():
        return [chunk async for chunk in runner.run(state)]

    return asyncio.run(collect())


# ---------------------------------------------------------------- LC-2: provider


class _RawCompletions:
    def __init__(self, outcome):
        self.outcome = outcome
        self.with_raw_response = self

    async def create(self, **request):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        message = SimpleNamespace(content="xin chào", tool_calls=[])
        parsed = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")],
                                 usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2,
                                                       prompt_tokens_details=None))
        return SimpleNamespace(headers={"x-request-id": "req_abc", "openai-processing-ms": "812"},
                               parse=lambda: parsed)


class _Client:
    def __init__(self, outcome):
        self.options = None
        self.chat = SimpleNamespace(completions=_RawCompletions(outcome))

    def with_options(self, **options):
        self.options = options
        return self


def _call_provider(outcome):
    provider = OpenAIProvider(api_key="test", model="gpt-4.1-mini", tool_call_timeout_s=19.0)
    client = _Client(outcome)
    provider._client = client
    trace = Trace("req-lc2-0001")

    async def call():
        with activate(trace), span("llm.chat_tools", "llm"):
            return await provider.chat_complete_tools([{"role": "user", "content": "hi"}], [])

    try:
        result = asyncio.run(call())
    except BaseException as error:              # noqa: BLE001 - test ghi lại lỗi
        result = error
    attributes = next(item for item in trace.spans if item.name == "llm.chat_tools").attributes
    return result, attributes, client


def _timeout(cause: BaseException) -> openai.APITimeoutError:
    try:
        raise openai.APITimeoutError(request=REQUEST) from cause
    except openai.APITimeoutError as error:
        return error


def test_provider_uses_own_timeout_without_sdk_retries_and_records_request_id():
    result, attributes, client = _call_provider(None)

    assert result.content == "xin chào"
    assert client.options == {"timeout": 19.0, "max_retries": 0}
    assert attributes["provider_request_id"] == "req_abc" and attributes["provider_processing_ms"] == 812


@pytest.mark.parametrize(("cause", "phase"), [
    (httpx.ReadTimeout("slow"), "read"),
    (httpx.ConnectTimeout("dns"), "connect"),
])
def test_provider_timeout_becomes_timeout_error_with_phase(cause, phase):
    result, attributes, _ = _call_provider(_timeout(cause))

    assert isinstance(result, TimeoutError)
    assert attributes["timeout_phase"] == phase


def test_provider_rate_limit_and_server_errors_are_transient_but_bad_requests_are_not():
    limited = openai.RateLimitError("slow down", response=httpx.Response(429, request=REQUEST), body=None)
    result, _, _ = _call_provider(limited)
    assert isinstance(result, ProviderTransientError) and result.status_code == 429

    bad = openai.BadRequestError("bad", response=httpx.Response(400, request=REQUEST), body=None)
    result, _, _ = _call_provider(bad)
    assert isinstance(result, openai.BadRequestError)


# ---------------------------------------------------------------- LC-2: runner thử lại


def test_runner_retries_a_timed_out_step_once():
    provider = ScriptedToolProvider([TimeoutError(), answer("Có 7 tin")])
    state = crm_state()

    assert _run(agent_runner(provider, ToolRegistry([_column_tool()])), state) == ["Có 7 tin"]
    statuses = [step.status for step in state.agent.steps if step.kind == "llm"]
    assert statuses == ["llm_timeout", "ok"] and state.agent.final_reason == "answered"


def test_two_failures_end_the_loop_and_the_final_step_is_retried_too():
    provider = ScriptedToolProvider([
        ProviderTransientError("http_503", status_code=503), TimeoutError(),   # bước 1: hai lần
        TimeoutError(), answer("Chưa lấy được số liệu"),                       # bước chốt: thử lại
    ])
    state = crm_state()

    assert _run(agent_runner(provider, ToolRegistry([_column_tool()])), state) == ["Chưa lấy được số liệu"]
    assert [call.tool_choice for call in provider.calls] == ["auto", "auto", "none", "none"]
    assert state.agent.final_reason == "limit"
    assert [step.status for step in state.agent.steps][:2] == ["llm_http_503", "llm_timeout"]


def test_final_step_failing_twice_keeps_the_original_provider_error():
    original = RuntimeError("upstream 503")
    transient = ProviderTransientError("http_503", status_code=503)
    transient.__cause__ = original
    provider = ScriptedToolProvider([TimeoutError(), TimeoutError(), transient, transient])

    with pytest.raises(RuntimeError, match="upstream 503"):
        _run(agent_runner(provider, ToolRegistry([_column_tool()])), crm_state())


# ---------------------------------------------------------------- LC-4: bắt sửa một lần


class _In(SystemModel):
    column: str


class _Out(ToolOutput):
    column: str


def _column_tool():
    async def run(arguments: _In, context) -> _Out:
        if arguments.column != "full_name":
            raise ToolArgumentError(f"customers has no column {arguments.column}; closest: full_name")
        return _Out(column=arguments.column)

    return ToolSpec(name="query", description="q", input_model=_In, output_model=_Out, run=run)


def _q(call_id, column):
    return call_id, "query", {"column": column}


def test_answer_right_after_a_repairable_error_is_replaced_by_one_forced_fix():
    provider = ScriptedToolProvider([
        calls(_q("c1", "name")),
        answer("Lỗi truy vấn, anh/chị muốn lấy cột nào?"),   # bỏ qua lỗi: bị bỏ
        calls(_q("c2", "full_name")),
        answer("5 khách mới nhất: ..."),
    ])
    state = crm_state()

    assert _run(agent_runner(provider, ToolRegistry([_column_tool()])), state) == ["5 khách mới nhất: ..."]
    assert provider.calls[2].tool_choice == "required"
    notes = [m["content"] for m in provider.calls[2].messages if m["role"] == "system"][1:]
    assert notes == [REPAIR_NOTE.format(tools="query")]


def test_repair_is_forced_only_once():
    provider = ScriptedToolProvider([
        calls(_q("c1", "name")),
        answer("Lỗi"),
        calls(_q("c2", "title")),
        answer("Chưa lấy được tên khách: cột không đúng"),
    ])

    state = crm_state()
    assert _run(agent_runner(provider, ToolRegistry([_column_tool()])), state) == [
        "Chưa lấy được tên khách: cột không đúng"
    ]
    # Lần sửa vẫn lỗi: hai bước lỗi liên tiếp → dừng (plateau), bước chốt không gọi tool, không ép lần nữa.
    assert [call.tool_choice for call in provider.calls] == ["auto", "auto", "required", "none"]
    assert state.agent.final_reason == "plateau"


def test_non_repairable_errors_and_repaired_tools_are_not_forced():
    failing = replace(_column_tool(), repairable_errors=frozenset())
    provider = ScriptedToolProvider([calls(_q("c1", "name")), answer("Không lấy được")])
    assert _run(agent_runner(provider, ToolRegistry([failing])), crm_state()) == ["Không lấy được"]

    provider = ScriptedToolProvider([
        calls(_q("c1", "name")), calls(_q("c2", "full_name")), answer("xong"),
    ])
    assert _run(agent_runner(provider, ToolRegistry([_column_tool()])), crm_state()) == ["xong"]


# ---------------------------------------------------------------- LC-4: kiểm cột trước khi gửi CRM


_CUSTOMERS = {"id", "code", "full_name", "company_name", "created_at", "assigned_sales_id"}
_OWNERSHIPS = {"id", "owner_customer_id", "product_item_id", "is_current"}
_RELATIONS = {("customers", "assigned_sales_id"): "auth_users"}


def _unknown(dataset, path, known=None):
    tables = {"customers": _CUSTOMERS, "product_ownerships": _OWNERSHIPS, **(known or {})}
    return unknown_column(
        dataset, path,
        relation_target=lambda table, column: _RELATIONS.get((table, column)),
        column_type=lambda table, column: "timestamp" if column == "created_at" else None,
        known_columns=tables.get,
    )


def test_unknown_columns_get_close_suggestions():
    error = _unknown("customers", "name")
    assert "customers has no column name; closest: full_name, company_name" in error
    assert "columns of customers:" in error

    assert "closest: owner_customer_id" in _unknown("product_ownerships", "customer_id")


def test_valid_columns_date_parts_and_unknown_tables_pass():
    assert _unknown("customers", "full_name") is None
    assert _unknown("customers", "created_at_month") is None             # cột ảo chia kỳ
    assert _unknown("customers", "assigned_sales_id.username") is None   # auth_users chưa biết: không kiểm
    assert _unknown("leads", "anything") is None
    error = _unknown("customers", "assigned_sales_id.nick", {"auth_users": {"id", "username"}})
    assert "auth_users has no column nick" in error


def test_crm_query_fetches_schema_and_rejects_unknown_column_before_querying_crm():
    api = FakeCrmApi(tables={"product_ownerships": _ownerships_live()})
    registry, _ = _tools(api)

    outcome = _invoke(registry, "crm_query", {
        "dataset": "product_ownerships", "mode": "aggregate", "metrics": ["count"],
        "filters": [{"field": "customer_id", "op": "eq", "value": "8d9b29fc-993b-4ab0-9c26-1f047b080a58"}],
    })

    assert outcome.error_code == "tool_invalid_args"
    assert "closest: owner_customer_id" in outcome.error_detail
    assert api.gets() == ["/api/v1/reports/tables/product_ownerships"] and api.bodies() == []
