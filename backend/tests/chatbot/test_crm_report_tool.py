"""Tool crm_report: gọi CRM bằng token nhân viên, tổng hợp bằng engine, lỗi thành mã cho agent."""

import asyncio
import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from app.modules.chatbot.providers.crm_api import CrmApiError, CrmListClient
from app.modules.chatbot.providers.openai import OPENAI_CAPABILITIES
from app.modules.chatbot.reporting.datasets import DATASETS
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.security.principal import RequestContext
from app.modules.chatbot.schemas.system import AgentRun, ToolCallRequest
from app.modules.chatbot.stages.execution_stage import SourceAllocator
from app.modules.chatbot.tools import ReportOutput, ToolContext, ToolRegistry, build_crm_report_tool
from tests.chatbot.agent_fakes import (
    FakeChunks,
    ScriptedToolProvider,
    agent_runner,
    answer,
    calls,
    crm_state,
    docs_registry,
)
from tests.chatbot.builders import make_service_principal
from tests.chatbot.report_fakes import NOW, TZ, sample_cases

BASE_URL = "https://crm.test"
SEP_OCT_BY_MONTH = {
    "dataset": "tickets",
    "metrics": ["ticket_count"],
    "date_range": {"field": "created_at", "start": "2026-09-01", "end": "2026-11-01"},
    "time_grain": "month",
}


class FakeCrm:
    """CRM giả: phân trang ?limit=&offset= và trả {items, limit, offset, total}."""

    def __init__(self, items=None, status=200, error=None):
        self.items = sample_cases() if items is None else items
        self.status = status
        self.error = error
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.status != 200:
            return httpx.Response(self.status, json={"error": "nope"})
        limit = int(request.url.params["limit"])
        offset = int(request.url.params["offset"])
        return httpx.Response(200, json={
            "items": self.items[offset:offset + limit],
            "limit": limit,
            "offset": offset,
            "total": len(self.items),
        })


def _client(crm: FakeCrm, *, max_items=100, page_size=100) -> CrmListClient:
    return CrmListClient(BASE_URL, timeout_s=5, max_items=max_items, page_size=page_size,
                         transport=httpx.MockTransport(crm))


def _registry(crm: FakeCrm, **client_options) -> ToolRegistry:
    return ToolRegistry([build_crm_report_tool(_client(crm, **client_options), DATASETS, tz=TZ)])


def _state(user_id: str | None = "employee-1", crm_token: str | None = None):
    state = crm_state("Báo cáo ticket")
    state.principal = make_service_principal(user_id=user_id)
    if crm_token is not None:
        state.principal = state.principal.acting_for(user_id, SecretStr(crm_token))
    state.request_context = RequestContext(
        request_id="req-report", channel=ChannelType.CRM, received_at=NOW,
    )
    state.agent = AgentRun()
    return state


def _invoke(registry: ToolRegistry, arguments, state=None):
    state = state or _state()
    context = ToolContext(parent_state=state, sources=SourceAllocator.for_state(state),
                          tool_call_id="r1")
    call = ToolCallRequest(id="r1", name="crm_report", arguments_raw=json.dumps(arguments))
    return asyncio.run(registry.invoke(call, context, allowed=registry.names, timeout_s=10))


def test_report_uses_employee_token_and_returns_aggregates():
    crm = FakeCrm()
    outcome = _invoke(_registry(crm), SEP_OCT_BY_MONTH)

    assert outcome.ok, outcome.error_detail
    [request] = crm.requests
    assert request.url.path == "/api/v1/support/cases"
    assert request.headers["Authorization"] == "Bearer employee-1"
    output = outcome.output
    assert isinstance(output, ReportOutput)
    assert output.rows[1]["change"] == {"ticket_count": {"delta": 3, "delta_pct": 300.0}}
    assert output.applied.date_range.start == "2026-09-01T00:00:00+07:00"
    assert output.applied.date_range.timezone == "Asia/Ho_Chi_Minh"
    assert output.applied.system_filters == ["delete_pending = false"]
    assert (output.fetched_count, output.matched_count, output.skipped_count) == (7, 5, 0)
    assert output.source_truncated is False


def test_crm_access_token_is_preferred_over_user_id(caplog):
    crm = FakeCrm()
    with caplog.at_level(logging.INFO):
        outcome = _invoke(_registry(crm), {"dataset": "tickets", "metrics": ["ticket_count"]},
                          state=_state(crm_token="eyJ.TOKEN-SECRET.sig"))

    assert outcome.ok
    assert crm.requests[0].headers["Authorization"] == "Bearer eyJ.TOKEN-SECRET.sig"
    assert "credential=token" in caplog.text
    assert "TOKEN-SECRET" not in caplog.text


def test_output_never_contains_ticket_content():
    outcome = _invoke(_registry(FakeCrm()), {
        "dataset": "tickets", "metrics": ["ticket_count"], "dimensions": ["customer", "status"],
    })

    text = outcome.message_content(3000, len)
    assert "SECRET" not in text
    assert "subject" not in text and "description" not in text


def test_pages_until_total_and_flags_truncation():
    crm = FakeCrm()
    outcome = _invoke(_registry(crm, page_size=3), {"dataset": "tickets", "metrics": ["ticket_count"]})
    assert [r.url.params["offset"] for r in crm.requests] == ["0", "3", "6"]
    assert outcome.output.fetched_count == 7 and not outcome.output.source_truncated

    crm = FakeCrm()
    truncated = _invoke(_registry(crm, page_size=3, max_items=5),
                        {"dataset": "tickets", "metrics": ["ticket_count"]})
    assert [r.url.params["limit"] for r in crm.requests] == ["3", "2"]
    assert truncated.output.fetched_count == 5 and truncated.output.source_truncated


@pytest.mark.parametrize(("crm", "code"), [
    (FakeCrm(status=401), "crm_auth_failed"),
    (FakeCrm(status=403), "crm_forbidden"),
    (FakeCrm(status=502), "crm_unavailable"),
    (FakeCrm(error=httpx.ReadTimeout("slow")), "crm_unavailable"),
    (FakeCrm(error=httpx.ConnectError("down")), "crm_unavailable"),
])
def test_crm_errors_become_codes(crm, code):
    outcome = _invoke(_registry(crm), {"dataset": "tickets", "metrics": ["ticket_count"]})
    assert outcome.error_code == code


def test_unexpected_body_is_unavailable():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="<html>ngrok</html>"))
    client = CrmListClient(BASE_URL, timeout_s=5, max_items=10, transport=transport)
    with pytest.raises(CrmApiError) as error:
        asyncio.run(client.fetch_all("/api/v1/support/cases", "t"))
    assert error.value.code == "crm_unavailable"


def test_invalid_query_is_rejected_before_calling_crm():
    crm = FakeCrm()
    outcome = _invoke(_registry(crm), {
        "dataset": "tickets", "metrics": ["ticket_count"],
        "filters": [{"field": "status", "operator": "eq", "value": "đang mở"}],
    })

    assert outcome.error_code == "tool_invalid_args"
    assert "allowed: new (mới tạo)" in outcome.error_detail
    assert crm.requests == []


def test_missing_crm_user_is_rejected():
    crm = FakeCrm()
    outcome = _invoke(_registry(crm), {"dataset": "tickets", "metrics": ["ticket_count"]},
                      state=_state(user_id=None))
    assert outcome.error_code == "crm_user_missing"
    assert crm.requests == []


def test_rows_are_cut_to_fit_budget():
    outcome = _invoke(_registry(FakeCrm()), {
        "dataset": "tickets", "metrics": ["ticket_count"], "dimensions": ["customer"],
    })
    full = outcome.output.to_llm(10_000, len)
    small = outcome.output.to_llm(len(json.dumps(full, ensure_ascii=False)) - 20, len)

    assert "truncated" not in full
    assert small["truncated"] is True and small["omitted_rows"] >= 1
    assert len(small["rows"]) + small["omitted_rows"] == len(full["rows"])


def test_schema_converts_for_openai_strict():
    registry = _registry(FakeCrm())
    registry.validate_for(OPENAI_CAPABILITIES)
    [tool] = registry.provider_tools(registry.allowed(make_service_principal()), "openai_strict")
    parameters = tool["function"]["parameters"]
    assert parameters["required"] == [
        "dataset", "metrics", "dimensions", "filters", "date_range", "time_grain", "sort", "limit",
    ]
    assert "status_group" in tool["function"]["description"]


def test_agent_answers_from_report_alongside_docs_tool():
    crm = FakeCrm()
    provider = ScriptedToolProvider(turns=[
        calls(("r1", "crm_report", SEP_OCT_BY_MONTH)),
        answer("Tháng 10 có 4 phiếu, tăng 3 so với tháng 9."),
    ])
    docs = docs_registry(provider, FakeChunks())
    registry = ToolRegistry([
        docs.get("product_docs_ask"), build_crm_report_tool(_client(crm), DATASETS, tz=TZ),
    ])
    runner = agent_runner(provider, registry)
    state = _state()

    async def collect():
        return [part async for part in runner.run(state)]

    assert asyncio.run(collect()) == ["Tháng 10 có 4 phiếu, tăng 3 so với tháng 9."]
    system_prompt = provider.calls[0].messages[0]["content"]
    assert '<tool_guide name="crm_report">' in system_prompt
    tool_message = provider.calls[1].messages[-1]
    assert tool_message["role"] == "tool" and '"delta_pct": 300.0' in tool_message["content"]
