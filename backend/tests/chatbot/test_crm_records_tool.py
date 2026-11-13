"""Tool crm_records: whitelist cột, phân trang, tổng, hiển thị an toàn, hai nguồn dữ liệu."""

import asyncio
import json
from datetime import datetime

import httpx
import pytest

from app.modules.chatbot.providers.crm_api import CrmListClient, CrmReportClient
from app.modules.chatbot.providers.openai import OPENAI_CAPABILITIES
from app.modules.chatbot.reporting.datasets import DATASETS
from app.modules.chatbot.reporting.records import MAX_TEXT_CHARS, render_value
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.security.principal import RequestContext
from app.modules.chatbot.schemas.system import AgentRun, ToolCallRequest
from app.modules.chatbot.stages.execution_stage import SourceAllocator
from app.modules.chatbot.tools import RecordsOutput, ToolContext, ToolRegistry, build_crm_records_tool
from tests.chatbot.agent_fakes import crm_state
from tests.chatbot.builders import make_service_principal
from tests.chatbot.report_fakes import NOW, TZ, case
from tests.chatbot.test_crm_report_tool import FakeCrm
from tests.chatbot.test_report_api import FakeReportApi

BASE_URL = "https://crm.test"


def _registry(crm: FakeCrm | None = None, api: FakeReportApi | None = None) -> ToolRegistry:
    crm = crm or FakeCrm()
    list_client = CrmListClient(BASE_URL, timeout_s=5, max_items=100, transport=httpx.MockTransport(crm))
    report_client = CrmReportClient(BASE_URL, timeout_s=5, transport=httpx.MockTransport(api or FakeReportApi()))
    return ToolRegistry([build_crm_records_tool(list_client, DATASETS, tz=TZ, report_client=report_client)])


def _invoke(registry: ToolRegistry, arguments, user_id: str | None = "employee-1"):
    state = crm_state("Danh sách")
    state.principal = make_service_principal(user_id=user_id)
    state.request_context = RequestContext(request_id="req-l", channel=ChannelType.CRM, received_at=NOW)
    state.agent = AgentRun()
    context = ToolContext(parent_state=state, sources=SourceAllocator.for_state(state), tool_call_id="l1")
    call = ToolCallRequest(id="l1", name="crm_records", arguments_raw=json.dumps(arguments))
    return asyncio.run(registry.invoke(call, context, allowed=registry.names, timeout_s=10))


TICKET_LIST = {
    "dataset": "tickets",
    "fields": ["case_number", "status", "customer", "created_at"],
    "filters": [{"field": "status_group", "operator": "eq", "value": "closed"}],
    "limit": 2,
}


def test_lists_tickets_newest_first_with_total_and_next_offset():
    outcome = _invoke(_registry(), TICKET_LIST)

    assert outcome.ok, outcome.error_detail
    output = outcome.output
    assert isinstance(output, RecordsOutput)
    # Phiếu đã xong (resolved/closed), bỏ delete_pending: 1, 2, 6; mới nhất trước.
    assert [item["case_number"] for item in output.items] == ["SC-2", "SC-1"]
    assert output.items[0] == {
        "case_number": "SC-2", "status": "closed", "customer": "Công ty A",
        "created_at": "2026-10-10T09:00+07:00",
    }
    assert (output.returned, output.total, output.has_more, output.next_offset) == (2, 3, True, 2)
    assert output.applied.sort == ["created_at desc"]
    assert output.applied.system_filters == ["delete_pending = false"]

    rest = _invoke(_registry(), {**TICKET_LIST, "offset": 2}).output
    assert [item["case_number"] for item in rest.items] == ["SC-6"]
    assert (rest.has_more, rest.next_offset) == (False, None)


def test_ticket_content_never_reaches_the_llm():
    outcome = _invoke(_registry(), {
        "dataset": "tickets", "fields": list(DATASETS["tickets"].list_columns), "limit": 20,
    })
    text = outcome.message_content(10_000, len)

    assert "SECRET" not in text
    assert "subject" not in text and "description" not in text


def test_strings_are_sanitized_and_cut():
    long_name = "Công ty\x00\x07 " + "X" * 300
    crm = FakeCrm(items=[case("9", "2026-10-01T02:00:00+00:00", customer=("c9", long_name))])
    [item] = _invoke(_registry(crm), {"dataset": "tickets", "fields": ["customer"]}).output.items

    assert "\x00" not in item["customer"] and "\x07" not in item["customer"]
    assert len(item["customer"]) == MAX_TEXT_CHARS and item["customer"].endswith("…")
    assert render_value("", TZ) is None and render_value(True, TZ) is True


@pytest.mark.parametrize(("value", "expected"), [
    # CRM lưu UTC: chuỗi không kèm múi giờ (cột timestamp) là UTC.
    ("2026-10-31 17:30:00.123456", "2026-11-01T00:30+07:00"),
    ("2026-10-01 02:00:00.5+00", "2026-10-01T09:00+07:00"),           # timestamptz
    ("2026-10-01T02:00:00.123456789Z", "2026-10-01T09:00+07:00"),
    ("2026-10-01T09:00:00+07:00", "2026-10-01T09:00+07:00"),
    (datetime(2026, 10, 1, 2, 0), "2026-10-01T09:00+07:00"),           # datetime không múi giờ
    ("2026-10-01", "2026-10-01"),                                      # cột date, kỳ _day: giữ
    ("2026-10", "2026-10"),
    ("Lắp đặt 2026-10-01 02:00", "Lắp đặt 2026-10-01 02:00"),          # chữ có ngày: giữ
])
def test_timestamps_are_shown_in_local_time(value, expected):
    assert render_value(value, TZ) == expected


@pytest.mark.parametrize(("arguments", "message"), [
    ({"dataset": "tickets", "fields": ["full_name"]}, "fields: full_name not allowed here"),
    ({"dataset": "tickets", "fields": ["status"],
      "sort": [{"field": "created_at", "direction": "asc"}]}, "must also be in fields"),
    ({"dataset": "tickets", "fields": ["status"],
      "filters": [{"field": "customer_type", "operator": "eq", "value": "lead"}]}, "not filterable"),
])
def test_invalid_record_queries_are_rejected_before_calling_crm(arguments, message):
    crm = FakeCrm()
    outcome = _invoke(_registry(crm), arguments)

    assert outcome.error_code == "tool_invalid_args"
    assert message in outcome.error_detail
    assert crm.requests == []


def test_limit_is_capped_by_schema():
    outcome = _invoke(_registry(), {"dataset": "tickets", "fields": ["status"], "limit": 50})
    assert outcome.error_code == "tool_invalid_args"


def test_missing_crm_user_is_rejected():
    outcome = _invoke(_registry(), TICKET_LIST, user_id=None)
    assert outcome.error_code == "crm_user_missing"


def test_customers_use_report_api_select_plus_count():
    api = FakeReportApi([
        {"rows": [
            {"code": "KH01", "full_name": "Nguyễn B", "created_at": "2026-10-03 08:00:00"},
        ]},
        {"rows": [{"count": 41}]},
    ])
    outcome = _invoke(_registry(api=api), {
        "dataset": "customers", "fields": ["code", "full_name", "created_at"],
        "date_range": {"field": "created_at", "preset": "last_month"}, "limit": 1,
    })

    assert outcome.ok, outcome.error_detail
    select, count = api.bodies()
    assert select == {
        "dataset": "customers",
        "select": ["code", "full_name", "created_at"],
        "filters": [{"field": "customer_type", "op": "not_in", "value": ["spam", "lost"]}],
        "date_range": {"field": "created_at", "from": "2026-10-01", "to": "2026-10-31"},
        "limit": 1,
        "offset": 0,
        "order_by": [{"field": "created_at", "dir": "desc"}],
    }
    assert count["metrics"] == ["count"] and "select" not in count
    output = outcome.output
    assert output.source == "report_api"
    # CRM trả UTC không kèm múi giờ: hiển thị giờ Việt Nam.
    assert output.items == [{"code": "KH01", "full_name": "Nguyễn B", "created_at": "2026-10-03T15:00+07:00"}]
    assert (output.total, output.has_more, output.next_offset) == (41, True, 1)
    assert output.applied.system_filters == ["customer_type not_in [spam, lost] (mặc định)"]


def test_customer_search_by_name_reads_contact_columns_and_long_notes():
    notes = "Gọi lại sau Tết. " * 80          # 1360 ký tự: vượt trần 1000 của notes
    api = FakeReportApi([
        {"rows": [{
            "code": "KH09", "full_name": "Anna Hohmeier", "phone": "0909123456",
            "email": "anna@example.com", "assigned_sales_id__username": "an", "notes": notes,
        }]},
        {"rows": [{"count": 1}]},
    ])
    outcome = _invoke(_registry(api=api), {
        "dataset": "customers",
        "fields": ["code", "full_name", "phone", "email", "sales_username", "notes"],
        "filters": [{"field": "full_name", "operator": "contains", "value": "hohmeier"}],
    })

    assert outcome.ok, outcome.error_detail
    select, count = api.bodies()
    assert select["select"] == [
        "code", "full_name", "phone", "email", "assigned_sales_id.username", "notes",
    ]
    name_filter = {"field": "full_name", "op": "contains", "value": "hohmeier"}
    assert name_filter in select["filters"] and name_filter in count["filters"]
    [item] = outcome.output.items
    assert item["full_name"] == "Anna Hohmeier" and item["phone"] == "0909123456"
    assert item["sales_username"] == "an"
    assert len(item["notes"]) == 1000 and item["notes"].endswith("…")    # max_chars riêng của notes
    assert outcome.output.total == 1


def test_assignment_list_maps_join_columns_back_to_logical_names():
    api = FakeReportApi([
        {"rows": [{"case_id__case_number": "SC-7", "assigned_to__username": "an"}]},
        {"rows": [{"count": 1}]},
    ])
    outcome = _invoke(_registry(api=api), {
        "dataset": "support_assignments", "fields": ["case_number", "assignee"],
    })

    assert outcome.output.items == [{"case_number": "SC-7", "assignee": "an"}]
    assert api.bodies()[0]["select"] == ["case_id.case_number", "assigned_to.username"]


def test_forbidden_report_dataset_becomes_code():
    outcome = _invoke(_registry(api=FakeReportApi(status=403)), {
        "dataset": "device_deliveries", "fields": ["device_code"],
    })
    assert outcome.error_code == "crm_forbidden"


def test_items_are_cut_to_fit_budget():
    outcome = _invoke(_registry(), {
        "dataset": "tickets", "fields": ["case_number", "customer"], "limit": 20,
    })
    full = outcome.output.to_llm(10_000, len)
    small = outcome.output.to_llm(len(json.dumps(full, ensure_ascii=False)) - 20, len)

    assert "truncated" not in full and len(full["items"]) == 7 - 1   # bỏ delete_pending
    assert small["truncated"] is True
    assert len(small["items"]) + small["omitted_rows"] == len(full["items"])


def test_schema_converts_for_openai_strict_and_lists_columns():
    registry = _registry()
    registry.validate_for(OPENAI_CAPABILITIES)
    [tool] = registry.provider_tools(registry.allowed(make_service_principal()), "openai_strict")

    assert tool["function"]["parameters"]["required"] == [
        "dataset", "fields", "filters", "date_range", "sort", "limit", "offset",
    ]
    description = tool["function"]["description"]
    assert "Dataset tickets" in description and "case_number" in description
    # Nội dung phiếu và cột bí mật không bao giờ có; liên hệ chỉ mở ở customers (2026-11-10).
    for secret in ("subject", "description:", "password", "token"):
        assert secret not in description
    customers_line = next(line for line in description.splitlines() if line.startswith("Dataset customers"))
    assert "phone:" in customers_line and "notes:" in customers_line
    tickets_line = next(line for line in description.splitlines() if line.startswith("Dataset tickets"))
    assert "phone" not in tickets_line and "email" not in tickets_line
