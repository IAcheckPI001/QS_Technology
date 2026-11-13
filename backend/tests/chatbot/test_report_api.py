"""Dataset report_api: compile sang JSON của CRM Reporting Query API, ghép kết quả, tool đi hết đường."""

import asyncio
import json
import logging

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.modules.chatbot.providers.crm_api import CrmApiError, CrmListClient, CrmReportClient
from app.modules.chatbot.reporting.datasets import DATASETS
from app.modules.chatbot.reporting.report_api import (
    ApiResult,
    api_column,
    compile_report,
    merge_report,
)
from app.modules.chatbot.reporting.validate import ReportQueryError, validate_query
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.security.principal import RequestContext
from app.modules.chatbot.schemas.system import AgentRun, ToolCallRequest
from app.modules.chatbot.schemas.system.report import ReportQuery
from app.modules.chatbot.stages.execution_stage import SourceAllocator
from app.modules.chatbot.tools import ReportOutput, ToolContext, ToolRegistry, build_crm_report_tool
from tests.chatbot.agent_fakes import crm_state
from tests.chatbot.builders import make_service_principal
from tests.chatbot.report_fakes import NOW, TZ

BASE_URL = "https://crm.test"
OCTOBER = {"field": "assigned_at", "start": "2026-10-01", "end": "2026-11-01"}


def normalized(**fields):
    query = ReportQuery.model_validate(fields)
    return validate_query(query, DATASETS, now=NOW, tz=TZ)


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------

def test_compile_counts_distinct_customers_through_joins():
    """Ví dụ 5.1 của tài liệu CRM: đường join nằm trong catalog, ngày nửa mở → from/to bao gồm."""
    query = normalized(
        dataset="support_assignments",
        metrics=["assignment_count", "distinct_customer_count"],
        filters=[{"field": "assignee", "operator": "eq", "value": "SaleA"}],
        date_range=OCTOBER,
    )
    [api_query] = compile_report(query).queries

    assert api_query.body == {
        "dataset": "support_assignments",
        "metrics": ["count", "count_distinct:case_id.product_item_id.customer_id"],
        "filters": [{"field": "assigned_to.username", "op": "eq", "value": "SaleA"}],
        "date_range": {"field": "created_at", "from": "2026-10-01", "to": "2026-10-31"},
    }


def test_compile_preset_and_default_filter_for_customers():
    """Ví dụ 5.2: top sale có nhiều khách mới; spam/lost bị loại mặc định."""
    query = normalized(
        dataset="customers", metrics=["customer_count"], dimensions=["assigned_sales"],
        date_range={"field": "created_at", "preset": "last_month"}, limit=10,
    )
    compiled = compile_report(query)
    [api_query] = compiled.queries

    assert api_query.body == {
        "dataset": "customers",
        "metrics": ["count"],
        "dimensions": ["assigned_sales"],
        "order_by": [{"field": "count", "dir": "desc"}],
        "limit": 1000,
        "totals": True,
        "filters": [{"field": "customer_type", "op": "not_in", "value": ["spam", "lost"]}],
        "date_range": {"field": "created_at", "from": "2026-10-01", "to": "2026-10-31"},
    }
    assert compiled.applied_filters == ("customer_type not_in [spam, lost] (mặc định)",)


@pytest.mark.parametrize("override", [
    {"filters": [{"field": "customer_type", "operator": "eq", "value": "spam"}]},
    {"dimensions": ["customer_type"]},
])
def test_default_filter_is_dropped_when_query_uses_the_field(override):
    query = normalized(dataset="customers", metrics=["customer_count"], **override)
    compiled = compile_report(query)
    filters = compiled.queries[0].body.get("filters", [])

    assert {"field": "customer_type", "op": "not_in", "value": ["spam", "lost"]} not in filters
    assert compiled.applied_filters == ()


def test_compile_groups_by_product_name_with_system_filter():
    """Ví dụ 5.4: sản phẩm 'bán được' = thiết bị giao, không tính chuyển nhượng."""
    query = normalized(
        dataset="device_deliveries", metrics=["delivery_count"], dimensions=["product_name"],
        date_range={"field": "delivered_at", "start": "2026-10-01", "end": "2026-11-01"},
    )
    [api_query] = compile_report(query).queries

    assert api_query.body["dimensions"] == ["product_item_id.product_id.name"]
    assert api_query.body["filters"] == [{"field": "transferred_from_ownership_id", "op": "is_null"}]


def test_values_are_strings_and_people_group_by_id_and_show_username():
    query = normalized(
        dataset="support_assignments", metrics=["assignment_count"], dimensions=["assignee"],
        filters=[
            {"field": "is_current", "operator": "eq", "value": True},
            {"field": "case_status", "operator": "in", "value": ["đã giải quyết", "closed"]},
        ],
    )
    body = compile_report(query).queries[0].body

    assert body["dimensions"] == ["assigned_to", "assigned_to.username"]
    assert body["filters"] == [
        {"field": "is_current", "op": "eq", "value": "true"},
        {"field": "case_id.status", "op": "in", "value": ["resolved", "closed"]},
    ]


def test_metric_with_own_filter_runs_as_separate_query():
    query = normalized(
        dataset="support_assignments", metrics=["assignment_count", "current_assignment_count"],
        dimensions=["assignee"],
    )
    queries = compile_report(query).queries

    assert [(q.metrics, q.base) for q in queries] == [
        (("assignment_count",), True), (("current_assignment_count",), False),
    ]
    assert queries[1].body["filters"] == [{"field": "is_current", "op": "eq", "value": "true"}]


def test_time_grain_adds_ranking_query_and_uses_dataset_period_names():
    query = normalized(
        dataset="customers", metrics=["customer_count"], dimensions=["assigned_sales"],
        date_range={"field": "created_at", "start": "2026-09-01", "end": "2026-11-01"},
        time_grain="month",
    )
    queries = compile_report(query).queries

    assert [q.role for q in queries] == ["values", "ranking"]
    assert queries[0].body["dimensions"] == ["assigned_sales", "created_month"]
    assert queries[1].body["dimensions"] == ["assigned_sales"]


@pytest.mark.parametrize(("fields", "message"), [
    ({"dataset": "customers", "time_grain": "week",
      "date_range": {"field": "created_at", "preset": "this_month"}}, "time_grain week is not available"),
    ({"dataset": "customers", "time_grain": "month",
      "date_range": {"field": "last_contact_at", "preset": "this_month"}}, "allowed: created_at day"),
    ({"dataset": "customers", "dimensions": ["case_status"]}, "dimensions: case_status not allowed"),
])
def test_report_api_specific_errors_go_back_to_the_agent(fields, message):
    with pytest.raises(ReportQueryError, match=message):
        normalized(metrics=["customer_count"], **fields)


def test_string_filters_keep_case_for_sql_exact_match():
    query = normalized(
        dataset="customers", metrics=["customer_count"],
        filters=[{"field": "source", "operator": "eq", "value": "  Facebook "}],
    )
    assert query.filters[0].value == "Facebook"


def test_contains_compiles_to_api_contains_for_name_search():
    query = normalized(
        dataset="customers", metrics=["customer_count"],
        filters=[
            {"field": "full_name", "operator": "contains", "value": " Hohmeier "},
            {"field": "sales_username", "operator": "eq", "value": "an.nguyen"},
        ],
    )
    body = compile_report(query).queries[0].body

    assert body["filters"] == [
        {"field": "customer_type", "op": "not_in", "value": ["spam", "lost"]},
        {"field": "full_name", "op": "contains", "value": "Hohmeier"},
        {"field": "assigned_sales_id.username", "op": "eq", "value": "an.nguyen"},
    ]


@pytest.mark.parametrize(("fields", "message"), [
    ({"filters": [{"field": "customer_type", "operator": "contains", "value": "le"}]},
     r"customer_type \(enum\) supports operators eq, ne, in, not_in$"),
    ({"filters": [{"field": "full_name", "operator": "contains", "value": ["a", "b"]}]},
     "needs a single value"),
])
def test_contains_is_string_only(fields, message):
    with pytest.raises(ReportQueryError, match=message):
        normalized(dataset="customers", metrics=["customer_count"], **fields)


def test_text_search_fields_are_not_dimensions():
    with pytest.raises(ValidationError, match="dimensions.0"):
        normalized(dataset="customers", metrics=["customer_count"], dimensions=["full_name"])


def test_sales_username_groups_by_join_path():
    query = normalized(dataset="customers", metrics=["customer_count"], dimensions=["sales_username"])
    assert compile_report(query).queries[0].body["dimensions"] == ["assigned_sales_id.username"]


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def test_merge_joins_metric_groups_by_key_and_labels_people():
    query = normalized(
        dataset="support_assignments", metrics=["assignment_count", "current_assignment_count"],
        dimensions=["assignee"],
    )
    compiled = compile_report(query)
    base = ApiResult(rows=[
        {"assigned_to": "u1", "assigned_to__username": "an", "count": 5},
        {"assigned_to": "u2", "assigned_to__username": "binh", "count": 7},
        {"assigned_to": "", "assigned_to__username": "", "count": 1},
    ], totals={"count": 13})
    current = ApiResult(rows=[{"assigned_to": "u2", "assigned_to__username": "binh", "count": 3}],
                        totals={"count": 3})
    result = merge_report(query, compiled, [base, current])

    assert result.rows == [
        {"assignee": "binh", "assignment_count": 7, "current_assignment_count": 3},
        {"assignee": "an", "assignment_count": 5, "current_assignment_count": 0},
        {"assignee": "(giao cho tổ chức)", "assignment_count": 1, "current_assignment_count": 0},
    ]
    assert (result.total_groups, result.matched_count) == (3, 13)


def test_merge_without_dimensions_reads_counts_as_numbers():
    query = normalized(
        dataset="support_assignments", metrics=["distinct_customer_count"], date_range=OCTOBER,
    )
    compiled = compile_report(query)
    column = api_column("count_distinct:case_id.product_item_id.customer_id")
    result = merge_report(query, compiled, [ApiResult([{"count": "15", column: "12"}], None)])

    assert result.rows == [{"distinct_customer_count": 12}]
    assert result.matched_count == 15


def test_merge_time_grain_fills_empty_periods_and_computes_change():
    query = normalized(
        dataset="customers", metrics=["customer_count"], dimensions=["assigned_sales"],
        date_range={"field": "created_at", "start": "2026-08-01", "end": "2026-11-01"},
        time_grain="month", limit=1,
    )
    compiled = compile_report(query)
    values = ApiResult(rows=[
        {"assigned_sales": "s1", "created_month": "2026-08-01 00:00:00", "count": 2},
        {"assigned_sales": "s1", "created_month": "2026-10-01 00:00:00", "count": 6},
        {"assigned_sales": "s2", "created_month": "2026-09-01 00:00:00", "count": 1},
    ], totals={"count": 9})
    ranking = ApiResult(rows=[
        {"assigned_sales": "s1", "count": 8}, {"assigned_sales": "s2", "count": 1},
    ], totals={"count": 9})
    result = merge_report(query, compiled, [values, ranking])

    assert [(row["assigned_sales"], row["period"], row["customer_count"]) for row in result.rows] == [
        ("s1", "2026-08", 2), ("s1", "2026-09", 0), ("s1", "2026-10", 6),
    ]
    assert result.rows[2]["change"] == {"customer_count": {"delta": 6, "delta_pct": None}}
    assert (result.total_groups, result.matched_count) == (2, 9)


# ---------------------------------------------------------------------------
# Tool đi hết đường với CRM Reporting API giả
# ---------------------------------------------------------------------------

class FakeReportApi:
    def __init__(self, responses=None, status=200, error=None):
        self.responses = list(responses or [])
        self.status = status
        self.error = error
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.status != 200:
            return httpx.Response(self.status, json={"error": "invalid report query: table has no column"})
        body = self.responses.pop(0) if self.responses else {"rows": [{"count": 0}]}
        return httpx.Response(200, json=body)

    def bodies(self):
        return [json.loads(request.content) for request in self.requests]


def _list_client() -> CrmListClient:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    return CrmListClient(BASE_URL, timeout_s=5, max_items=10, transport=transport)


def _report_client(api: FakeReportApi) -> CrmReportClient:
    return CrmReportClient(BASE_URL, timeout_s=5, transport=httpx.MockTransport(api))


def _registry(api: FakeReportApi, *, with_report_client=True) -> ToolRegistry:
    report_client = _report_client(api) if with_report_client else None
    return ToolRegistry([
        build_crm_report_tool(_list_client(), DATASETS, tz=TZ, report_client=report_client),
    ])


def _state(token: str | None = "eyJ.REPORT-SECRET.sig"):
    state = crm_state("Báo cáo")
    state.principal = make_service_principal(user_id="employee-1")
    if token is not None:
        state.principal = state.principal.acting_for("employee-1", SecretStr(token))
    state.request_context = RequestContext(request_id="req-r", channel=ChannelType.CRM, received_at=NOW)
    state.agent = AgentRun()
    return state


def _invoke(registry: ToolRegistry, arguments):
    state = _state()
    context = ToolContext(parent_state=state, sources=SourceAllocator.for_state(state), tool_call_id="r1")
    call = ToolCallRequest(id="r1", name="crm_report", arguments_raw=json.dumps(arguments))
    return asyncio.run(registry.invoke(call, context, allowed=registry.names, timeout_s=10))


SALE_OCTOBER = {
    "dataset": "support_assignments",
    "metrics": ["distinct_customer_count", "assigned_case_count"],
    "filters": [{"field": "assignee", "operator": "eq", "value": "SaleA"}],
    "date_range": OCTOBER,
}


def test_tool_posts_compiled_query_with_employee_token_and_returns_definitions(caplog):
    api = FakeReportApi([{"rows": [{
        "count": 15, "count_distinct_case_id": 14,
        "count_distinct_case_id__product_item_id__customer_id": 12,
    }]}])
    with caplog.at_level(logging.INFO):
        outcome = _invoke(_registry(api), SALE_OCTOBER)

    assert outcome.ok, outcome.error_detail
    [request] = api.requests
    assert request.url.path == "/api/v1/reports/query"
    assert request.headers["Authorization"] == "Bearer eyJ.REPORT-SECRET.sig"
    assert "REPORT-SECRET" not in caplog.text
    output = outcome.output
    assert isinstance(output, ReportOutput)
    assert output.source == "report_api"
    assert output.rows == [{"distinct_customer_count": 12, "assigned_case_count": 14}]
    assert (output.matched_count, output.fetched_count, output.skipped_count) == (15, None, None)
    assert any("thiết bị" in item for item in output.definitions)
    text = outcome.message_content(3000, len)
    assert "case_id.product_item_id" not in text and "REPORT-SECRET" not in text


@pytest.mark.parametrize(("api", "code"), [
    (FakeReportApi(status=400), "crm_report_contract_error"),
    (FakeReportApi(status=401), "crm_auth_failed"),
    (FakeReportApi(status=403), "crm_forbidden"),
    (FakeReportApi(status=500), "crm_unavailable"),
    (FakeReportApi(error=httpx.ReadTimeout("slow")), "crm_unavailable"),
])
def test_report_api_errors_become_codes(api, code):
    outcome = _invoke(_registry(api), SALE_OCTOBER)
    assert outcome.error_code == code
    assert "no column" not in (outcome.error_detail or "")


def test_unexpected_body_is_unavailable():
    api = FakeReportApi([{"rows": "nope"}])
    client = _report_client(api)
    with pytest.raises(CrmApiError) as error:
        asyncio.run(client.query({"dataset": "customers", "metrics": ["count"]}, "t"))
    assert error.value.code == "crm_unavailable"


def test_parallel_queries_for_conditional_metric():
    api = FakeReportApi([
        {"rows": [{"assigned_to": "u1", "assigned_to__username": "an", "count": 4}], "totals": {"count": 4}},
        {"rows": [{"assigned_to": "u1", "assigned_to__username": "an", "count": 2}], "totals": {"count": 2}},
    ])
    outcome = _invoke(_registry(api), {
        "dataset": "support_assignments", "dimensions": ["assignee"],
        "metrics": ["assignment_count", "current_assignment_count"],
    })

    assert outcome.ok, outcome.error_detail
    assert len(api.requests) == 2
    assert outcome.output.rows == [{"assignee": "an", "assignment_count": 4, "current_assignment_count": 2}]


def test_report_datasets_are_unavailable_without_report_client():
    api = FakeReportApi()
    registry = _registry(api, with_report_client=False)
    outcome = _invoke(registry, SALE_OCTOBER)

    assert outcome.error_code == "tool_invalid_args"
    assert "not available" in outcome.error_detail
    assert api.requests == []
    [tool] = registry.provider_tools(registry.allowed(make_service_principal()), "openai_strict")
    assert "Dataset support_assignments" not in tool["function"]["description"]


def test_description_lists_report_datasets_and_their_time_grains():
    registry = _registry(FakeReportApi())
    [tool] = registry.provider_tools(registry.allowed(make_service_principal()), "openai_strict")
    description = tool["function"]["description"]

    assert "Dataset customers" in description and "Dataset device_deliveries" in description
    assert "time_grain: created_at day, created_at month." in description
    assert "assigned_to" not in description           # đường dẫn cột không lộ cho LLM
