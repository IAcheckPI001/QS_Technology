"""Tool crm_schema + crm_query (truy vấn thô CRM Reporting API): policy, compile, CRM giả, cache."""

import asyncio
import json
from datetime import date

import httpx
import pytest
from pydantic import SecretStr

from app.modules.chatbot.providers.crm_api import CrmReportClient
from app.modules.chatbot.providers.openai import OPENAI_CAPABILITIES
from app.core.tracing import Trace, activate
from app.modules.chatbot.reporting.dates import stated_years
from app.modules.chatbot.reporting.raw.audit import AUDIT_LOGGER, QueryAudit
from app.modules.chatbot.reporting.raw.compile import RawQueryError, compile_raw
from app.modules.chatbot.reporting.raw.hints import LOOKUP_TABLES, TABLE_GROUPS, TABLE_NOTES
from app.modules.chatbot.reporting.raw.policy import QUERYABLE_TABLES, PathError, check_path, column_blocked
from app.modules.chatbot.reporting.raw.schema import CrmSchemaCache, LiveTable
from app.modules.chatbot.reporting.raw.schema_index import TABLES
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.security.principal import RequestContext
from app.modules.chatbot.schemas.system import AgentRun, ToolCallRequest
from app.modules.chatbot.schemas.system.raw_query import RawQuery
from app.modules.chatbot.stages.execution_stage import SourceAllocator
from app.modules.chatbot.tools import (
    QueryOutput,
    SchemaOutput,
    ToolContext,
    ToolRegistry,
    build_crm_query_tool,
    build_crm_schema_tool,
)
from app.modules.chatbot.tools.crm_schema import describe_table
from tests.chatbot.agent_fakes import crm_state
from tests.chatbot.builders import make_service_principal
from tests.chatbot.report_fakes import NOW, TZ

BASE_URL = "https://crm.test"
TOKEN = "eyJ.QUERY-SECRET.sig"


class FakeCrmApi:
    """GET /api/v1/reports/tables/{t}, GET /api/v1/reports/datasets (datasets=None: 404) và
    POST /api/v1/reports/query của CRM giả."""

    def __init__(self, responses=None, *, status=200, tables=None, datasets=None, lookups=None,
                 lookup_status=200, error="invalid report query: x"):
        self.responses = list(responses or [])
        self.status = status
        self.error = error
        self.tables = tables or {}
        self.datasets = datasets
        self.lookups = lookups or {}          # bảng tra cứu → rows trả cho query lấy known_values
        self.lookup_status = lookup_status
        self.requests: list[httpx.Request] = []

    @staticmethod
    def is_lookup(request: httpx.Request) -> bool:
        """Query crm_schema gửi để lấy giá trị bảng tra cứu (select đúng cột của LookupSpec)."""
        if request.method != "POST":
            return False
        body = json.loads(request.content)
        spec = LOOKUP_TABLES.get(body.get("dataset"))
        return spec is not None and body.get("select") == list(spec.columns)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.is_lookup(request):
            if self.lookup_status != 200:
                return httpx.Response(self.lookup_status, json={"error": "forbidden"})
            return httpx.Response(200, json={"rows": self.lookups.get(json.loads(request.content)["dataset"], [])})
        if request.method == "GET" and request.url.path.endswith("/reports/datasets"):
            if self.datasets is None:
                return httpx.Response(404, json={"error": "not found"})
            return httpx.Response(200, json={"datasets": self.datasets})
        if request.method == "GET":
            name = request.url.path.rsplit("/", 1)[-1]
            if name not in self.tables:
                return httpx.Response(404, json={"error": "unknown table"})
            return httpx.Response(200, json=self.tables[name])
        if self.status != 200:
            return httpx.Response(self.status, json={"error": self.error})
        body = self.responses.pop(0) if self.responses else {"rows": [{"count": 0}]}
        return httpx.Response(200, json=body)

    def bodies(self):
        """Body các query của crm_query (không tính query lấy known_values)."""
        return [json.loads(request.content) for request in self.requests
                if request.method == "POST" and not self.is_lookup(request)]

    def lookup_bodies(self):
        return [json.loads(request.content) for request in self.requests if self.is_lookup(request)]

    def gets(self):
        """Các GET schema bảng (không tính GET /reports/datasets)."""
        return [request.url.path for request in self.requests
                if request.method == "GET" and "/reports/tables/" in request.url.path]

    def dataset_gets(self):
        return [request for request in self.requests if request.url.path.endswith("/reports/datasets")]


def _live_table(name: str) -> dict:
    index = TABLES[name]
    return {
        "table": name,
        "columns": [{"name": column, "type": "character varying"} for column in index.columns],
        "relations": [{"name": column, "table": target} for column, target in index.relations.items()]
        or None,
    }


def _tools(api: FakeCrmApi, *, clock=lambda: 0.0, audit: QueryAudit | None = None):
    client = CrmReportClient(BASE_URL, timeout_s=5, transport=httpx.MockTransport(api))
    cache = CrmSchemaCache(client, ttl_s=600, clock=clock)
    registry = ToolRegistry([
        build_crm_schema_tool(cache),
        build_crm_query_tool(client, cache, tz=TZ, audit=audit),
    ])
    return registry, cache


def _invoke(registry: ToolRegistry, name: str, arguments, *, token: str | None = TOKEN):
    return _invoke_many(registry, [(name, arguments)], token=token)[0]


def _invoke_many(registry: ToolRegistry, calls, *, token: str | None = TOKEN):
    """Các call trong cùng một lượt (cùng state). arguments là str = JSON thô của LLM."""
    state = _state(token)

    async def run():
        outcomes = []
        for index, (name, arguments) in enumerate(calls, start=1):
            if isinstance(arguments, str):
                raw = arguments
            else:
                if name == "crm_query" and "mode" not in arguments:
                    arguments = {"mode": "list" if arguments.get("select") else "aggregate", **arguments}
                raw = json.dumps(arguments)
            context = ToolContext(
                parent_state=state, sources=SourceAllocator.for_state(state), tool_call_id=f"q{index}",
            )
            call = ToolCallRequest(id=f"q{index}", name=name, arguments_raw=raw)
            outcomes.append(await registry.invoke(call, context, allowed=registry.names, timeout_s=10))
        return outcomes

    return asyncio.run(run())


def _state(token: str | None):
    state = crm_state("Dữ liệu CRM")
    state.principal = make_service_principal(user_id="employee-1")
    if token is not None:
        state.principal = state.principal.acting_for("employee-1", SecretStr(token))
    else:
        state.principal = state.principal.acting_for(None, None)
    state.request_context = RequestContext(request_id="req-q", channel=ChannelType.CRM, received_at=NOW)
    state.agent = AgentRun()
    return state


def _query(**fields) -> RawQuery:
    mode = "list" if fields.get("select") else "aggregate"
    return RawQuery.model_validate({"dataset": "customers", "mode": mode, **fields})


# Filter mặc định của customers (Toma 2026-11-12: "khách hàng" không tính khách spam).
NO_SPAM = {"field": "customer_type", "op": "neq", "value": "spam"}


def _compile(**fields):
    return compile_raw(_query(**fields), now=NOW, tz=TZ)


# ---------------------------------------------------------------------------
# Index tĩnh, nhóm bảng, policy
# ---------------------------------------------------------------------------

def test_every_queryable_table_is_in_exactly_one_group_and_notes_name_real_tables():
    grouped = [table for tables in TABLE_GROUPS.values() for table in tables]
    assert sorted(grouped) == sorted(QUERYABLE_TABLES)
    assert set(TABLE_NOTES) <= set(QUERYABLE_TABLES)


def test_static_index_has_columns_relations_and_check_values():
    customers = TABLES["customers"]
    assert customers.columns["full_name"] == "text" and customers.columns["created_at"] == "timestamp"
    assert customers.relations["assigned_sales_id"] == "auth_users"
    assert customers.values["customer_type"] == ("lead", "student", "official", "spam", "lost")
    assert TABLES["roles"].values["data_scope"] == ("SELF", "ORGANIZATION", "ORGANIZATION_AND_CHILDREN", "ALL")
    assert "group" in TABLES["customer_statuses"].columns          # tên cột trong "" của dump


def test_secret_tables_and_columns_are_blocked_but_business_data_is_not():
    for table in ("keygen_history", "app_settings", "sessions", "password_reset_tokens"):
        assert table not in QUERYABLE_TABLES
    assert column_blocked("lock_requests", "unlock_key")
    assert column_blocked("product_item_activation_requests", "result")
    assert column_blocked("auth_users", "password_hash")
    assert column_blocked("files", "storage_key")
    for table, column in (("customers", "phone"), ("customers", "notes"), ("auth_users", "email"),
                          ("chat_messages", "body"), ("lock_requests", "status")):
        assert not column_blocked(table, column)


@pytest.mark.parametrize(("dataset", "path", "message"), [
    ("customers", "assigned_sales_id.password_hash", "auth_users.password_hash is not available"),
    ("support_cases", "product_item_id.device_input", "product_items.device_input is not available"),
    ("customers", "nope_id.full_name", "customers has no relation nope_id; check relations with crm_schema"),
])
def test_paths_are_checked_through_every_join(dataset, path, message):
    with pytest.raises(ValueError, match=message.replace(".", r"\.")):
        check_path(dataset, path)


def test_join_path_returns_table_of_last_column():
    assert check_path("support_assignments", "case_id.product_item_id.customer_id.full_name") == "customers"


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------

def test_list_mode_has_count_query_with_same_filters():
    compiled = _compile(
        select=["code", "full_name", "assigned_sales_id.username"],
        filters=[{"field": "full_name", "op": "contains", "value": "Hohmeier"}],
        date_range={"field": "created_at", "preset": "last_month"},
    )

    common = {
        "filters": [{"field": "full_name", "op": "contains", "value": "Hohmeier"}, NO_SPAM],
        "date_range": {"field": "created_at", "from": "2026-10-01", "to": "2026-10-31"},
    }
    assert compiled.body == {
        "dataset": "customers", "select": ["code", "full_name", "assigned_sales_id.username"],
        **common, "limit": 20,
    }
    assert compiled.count_body == {"dataset": "customers", "metrics": ["count"], **common}
    assert compiled.mode == "list" and compiled.filters == (
        "full_name contains Hohmeier", "customer_type neq spam (mặc định: không tính khách spam)",
    )


def test_aggregate_mode_matches_crm_doc_example_and_adds_totals():
    """Ví dụ 5.1/5.2 của ai-reporting-query.md."""
    query = RawQuery.model_validate({
        "dataset": "support_assignments", "mode": "aggregate",
        "metrics": ["count", "count_distinct:case_id.product_item_id.customer_id"],
        "filters": [{"field": "assigned_to.username", "op": "eq", "value": "SaleA"}],
        "date_range": {"field": "created_at", "preset": "custom",
                       "from_date": "2026-10-01", "to_date": "2026-10-31"},
    })
    assert compile_raw(query, now=NOW, tz=TZ).body == {
        "dataset": "support_assignments",
        "filters": [{"field": "assigned_to.username", "op": "eq", "value": "SaleA"}],
        "date_range": {"field": "created_at", "from": "2026-10-01", "to": "2026-10-31"},
        "metrics": ["count", "count_distinct:case_id.product_item_id.customer_id"],
        "limit": 50,
    }
    top = _compile(dimensions=["assigned_sales"], metrics=["count"],
                   order_by=[{"field": "count", "dir": "desc"}], limit=10)
    assert top.body == {
        "dataset": "customers", "filters": [NO_SPAM], "dimensions": ["assigned_sales"], "metrics": ["count"],
        "totals": True, "order_by": [{"field": "count", "dir": "desc"}], "limit": 10,
    }
    assert top.count_body is None


@pytest.mark.parametrize(("fields", "message"), [
    ({"mode": "list", "metrics": ["count"]}, "mode=list needs select"),
    ({"mode": "aggregate", "select": ["code"]}, "mode=aggregate needs metrics"),
    ({"select": ["code"], "filters": [{"field": "code", "op": "eq", "value": ["a", "b"]}]}, "needs one string"),
    ({"select": ["code"], "filters": [{"field": "code", "op": "contains", "value": None}]}, "needs a value"),
    ({"select": ["code"], "date_range": {"field": "created_at", "preset": "custom"}}, "preset=custom needs"),
    ({"select": ["code"], "date_range": {"field": "created_at", "preset": "custom", "from_date": "2026-11-02",
                                         "to_date": "2026-11-01"}}, "must not be after"),
    ({"select": ["assigned_sales_id.password_hash"]}, "password_hash is not available"),
])
def test_invalid_queries_are_rejected_before_crm(fields, message):
    with pytest.raises(RawQueryError, match=message):
        _compile(**fields)


def test_fields_of_the_other_mode_and_stray_order_by_are_ignored_not_rejected():
    """OpenAI strict bắt điền mọi field: LLM hay điền select cùng metrics, preset cùng from_date."""
    compiled = _compile(
        mode="aggregate", select=["created_at"], dimensions=["created_month"], metrics=["count"],
        order_by=[{"field": "created_at", "dir": "asc"}, {"field": "created_month", "dir": "asc"}],
        date_range={"field": "created_at", "preset": "this_year",
                    "from_date": "2026-03-01", "to_date": "2026-03-31"},
    )

    assert "select" not in compiled.body and compiled.body["dimensions"] == ["created_month"]
    assert compiled.body["order_by"] == [{"field": "created_month", "dir": "asc"}]
    assert compiled.body["date_range"] == {"field": "created_at", "from": "2026-01-01", "to": "2026-11-02"}
    assert compiled.ignored == (
        "select (mode=aggregate)", "date_range.from_date/to_date (preset=this_year)",
        "order_by created_at (not among the chosen columns)",
    )
    listing = _compile(mode="list", select=["code"], metrics=["count"])
    assert listing.body["select"] == ["code"] and "metrics" not in listing.body
    assert listing.ignored == ("dimensions/metrics (mode=list)",)


def test_filter_values_are_normalized():
    compiled = _compile(select=["code"], filters=[
        {"field": "customer_type", "op": "in", "value": "lead"},
        {"field": "code", "op": "eq", "value": ["KH01"]},
        {"field": "assigned_sales_id", "op": "is_null", "value": "ignored"},
    ])
    assert compiled.body["filters"] == [
        {"field": "customer_type", "op": "in", "value": ["lead"]},
        {"field": "code", "op": "eq", "value": "KH01"},
        {"field": "assigned_sales_id", "op": "is_null"},
    ]


def test_open_date_ranges_and_list_limit_cap():
    compiled = _compile(select=["code"], limit=90,
                        date_range={"field": "created_at", "preset": "custom", "from_date": "2026-10-15"})
    # NOW = 02/11/2026 giờ Việt Nam: to mặc định là hôm nay.
    assert compiled.body["date_range"] == {"field": "created_at", "from": "2026-10-15", "to": "2026-11-02"}
    assert compiled.limit == 50
    until = _compile(select=["code"], date_range={"field": "created_at", "preset": "custom",
                                                  "to_date": date(2026, 1, 31)})
    assert until.body["date_range"]["from"] == "1970-01-01"


# ---------------------------------------------------------------------------
# Luật chung theo kiểu cột (P0): chặn query sai kiểu, cho qua dạng hợp lệ
# ---------------------------------------------------------------------------

UUID = "3f2b8c1e-9a4d-4e7b-8c2a-1d5e6f7a8b9c"


def _compile_on(dataset: str, **fields):
    mode = "list" if fields.get("select") else "aggregate"
    query = RawQuery.model_validate({"dataset": dataset, "mode": mode, **fields})
    return compile_raw(query, now=NOW, tz=TZ)


@pytest.mark.parametrize(("dataset", "item", "message"), [
    # Tên/chuỗi giữ chỗ/subquery trên cột uuid (đo được 2026-11-11).
    ("customers", {"field": "assigned_sales_id", "op": "eq", "value": "Zzyzx"}, "only takes real UUIDs"),
    ("customers", {"field": "assigned_sales_id", "op": "eq", "value": "UUID của nhân viên Hiếu"},
     "only takes real UUIDs"),
    ("user_roles", {"field": "user_id", "op": "in", "value": [UUID, "(SELECT id FROM auth_users)"]},
     "only takes real UUIDs"),
    ("customers", {"field": "assigned_sales_id", "op": "contains", "value": "an"}, "contains is not allowed"),
    # Kỳ thời gian trong filters thay vì date_range.
    # Kỳ dạng YYYY/YYYY-MM được tự chuyển thành date_range (test riêng); dạng khác vẫn bị chặn.
    ("customers", {"field": "created_at", "op": "in", "value": ["last_month"]}, "is a date column"),
    ("customers", {"field": "created_at", "op": "contains", "value": "tháng 10"}, "is a date column"),
    ("customers", {"field": "created_at_day", "op": "eq", "value": "5"}, "is a date column"),
    # Số, bool, giá trị hợp lệ.
    ("support_cases", {"field": "session_minutes_charged", "op": "eq", "value": "nhiều"}, "not a number"),
    ("support_cases", {"field": "session_minutes_charged", "op": "contains", "value": "1"}, "not contains"),
    ("auth_users", {"field": "is_active", "op": "eq", "value": "đang hoạt động"}, "use true or false"),
    ("customers", {"field": "customer_type", "op": "eq", "value": "vip"}, "allows only: lead, student"),
])
def test_values_that_do_not_fit_the_column_type_never_reach_crm(dataset, item, message):
    with pytest.raises(RawQueryError, match=message):
        _compile_on(dataset, metrics=["count"], filters=[item])


def test_valid_forms_of_each_type_pass_and_are_normalized():
    compiled = _compile_on(
        "support_cases", metrics=["count"],
        date_range={"field": "created_at", "preset": "month", "month": 10},
        filters=[
            {"field": "closed_at", "op": "is_null", "value": None},
            {"field": "resolved_at", "op": "contains", "value": "2026-11"},     # ngày thứ hai
            {"field": "created_by", "op": "eq", "value": UUID},
            {"field": "created_by.username", "op": "contains", "value": "an"},  # join tới cột chữ
            {"field": "session_minutes_charged", "op": "in", "value": ["1.000", "30"]},
            {"field": "status", "op": "eq", "value": "Resolved"},             # không có CHECK: giữ nguyên
        ],
    )
    assert compiled.body["filters"] == [
        {"field": "closed_at", "op": "is_null"},
        {"field": "resolved_at", "op": "contains", "value": "2026-11"},
        {"field": "created_by", "op": "eq", "value": UUID},
        {"field": "created_by.username", "op": "contains", "value": "an"},
        {"field": "session_minutes_charged", "op": "in", "value": ["1000", "30"]},
        {"field": "status", "op": "eq", "value": "Resolved"},
    ]
    enum = _compile_on("customers", metrics=["count"], filters=[
        {"field": "customer_type", "op": "not_in", "value": ["SPAM", "Lost"]},
        {"field": "assigned_sales_id.is_active", "op": "eq", "value": "có"},
    ])
    assert enum.body["filters"] == [
        {"field": "customer_type", "op": "not_in", "value": ["spam", "lost"]},
        {"field": "assigned_sales_id.is_active", "op": "eq", "value": "true"},
    ]


def test_staff_by_role_counts_only_accounts_in_use_by_default():
    """Eval 2026-11-12: gpt-4o-mini bỏ user_id.is_active 9/9 lần; compile tự thêm và ghi rõ."""
    compiled = _compile_on("user_roles", metrics=["count_distinct:user_id"],
                           filters=[{"field": "role_id.code", "op": "eq", "value": "sales"}])
    assert compiled.body["filters"] == [
        {"field": "role_id.code", "op": "eq", "value": "sales"},
        {"field": "user_id.is_active", "op": "eq", "value": "true"},
    ]
    assert any("mặc định" in label for label in compiled.filters)

    listed = _compile_on("user_roles", select=["user_id.username"])
    assert listed.count_body["filters"] == listed.body["filters"] == [
        {"field": "user_id.is_active", "op": "eq", "value": "true"},
    ]


def test_default_filter_yields_to_llm_filter_on_same_column():
    """Hỏi kể cả người không còn dùng: LLM lọc chính cột đó, compile không thêm mặc định."""
    compiled = _compile_on("user_roles", metrics=["count_distinct:user_id"],
                           filters=[{"field": "user_id.is_active", "op": "not_null", "value": None}])
    assert compiled.body["filters"] == [{"field": "user_id.is_active", "op": "not_null"}]
    assert "filters" not in _compile_on("user_profiles", select=["first_name"]).body


def test_include_inactive_drops_default_filter():
    """Eval 2026-11-12: model nhỏ không tự lọc not_null; tham số riêng buộc LLM cân nhắc mỗi lần gọi."""
    compiled = _compile_on("user_roles", metrics=["count_distinct:user_id"], include_inactive=True,
                           filters=[{"field": "role_id.code", "op": "eq", "value": "sales"}])
    assert compiled.body["filters"] == [{"field": "role_id.code", "op": "eq", "value": "sales"}]
    assert compiled.ignored == ()
    other = _compile_on("support_cases", metrics=["count"], include_inactive=True)
    assert other.ignored == ("include_inactive (support_cases has no default filter)",)


def test_customers_exclude_spam_by_default_unless_asked():
    """Toma 2026-11-12: "khách hàng" không tính spam (CRM đếm 550, trừ spam 545); lost vẫn tính."""
    assert _compile(metrics=["count"]).body["filters"] == [NO_SPAM]
    about_spam = _compile(metrics=["count"], filters=[{"field": "customer_type", "op": "eq", "value": "spam"}])
    assert about_spam.body["filters"] == [{"field": "customer_type", "op": "eq", "value": "spam"}]
    assert "filters" not in _compile(metrics=["count"], include_inactive=True).body


def test_period_assignments_count_every_handover_not_only_current():
    """Toma 2026-11-12 (eval q13): có kỳ thì bỏ is_current (tháng 10: 25 lần giao, không phải 21)."""
    current = {"field": "is_current", "op": "eq", "value": "true"}
    in_period = _compile_on("support_assignments", dimensions=["assigned_to"], metrics=["count"],
                            filters=[current], date_range={"field": "created_at", "preset": "month", "month": 10})
    assert "filters" not in in_period.body
    assert in_period.ignored == ("filters is_current (has a date_range: count every row in the period)",)
    now_only = _compile_on("support_assignments", dimensions=["assigned_to"], metrics=["count"], filters=[current])
    assert now_only.body["filters"] == [current]


def _compile_asked(question: str, **fields):
    """Như agent: năm đối chiếu với câu hỏi (NOW = 2026-11-11)."""
    mode = "list" if fields.get("select") else "aggregate"
    query = RawQuery.model_validate({"mode": mode, **fields})
    return compile_raw(query, now=NOW, tz=TZ, stated_years=stated_years([question], NOW, TZ))


def test_year_the_question_does_not_state_is_replaced_by_the_latest_period():
    """Eval 2026-11-12: "tháng 10" bị điền 2023, "tháng 12" bị điền 2026 (tương lai)."""
    october = _compile_asked("Tháng 10 bán được bao nhiêu?", dataset="product_ownerships", metrics=["count"],
                             date_range={"field": "created_at", "preset": "month", "month": 10, "year": 2023})
    assert october.date_range == {"field": "created_at", "from": "2026-10-01", "to": "2026-10-31"}
    assert october.ignored == ("date_range.year=2023 (year not in the question: using the latest such period)",)
    december = _compile_asked("Tháng 12 có bao nhiêu khách mới?", dataset="customers", metrics=["count"],
                              date_range={"field": "created_at", "preset": "month", "month": 12, "year": 2026})
    assert december.date_range["from"] == "2025-12-01"
    stated = _compile_asked("Tháng 10 năm 2023 bán được bao nhiêu?", dataset="product_ownerships", metrics=["count"],
                            date_range={"field": "created_at", "preset": "month", "month": 10, "year": 2023})
    assert stated.date_range["from"] == "2023-10-01" and stated.ignored == ()
    last_year = _compile_asked("Năm ngoái có bao nhiêu khách mới?", dataset="customers", metrics=["count"],
                               date_range={"field": "created_at", "preset": "year", "year": 2025})
    assert last_year.date_range == {"field": "created_at", "from": "2025-01-01", "to": "2025-12-31"}
    custom = _compile_asked("Từ 1/12 đến 15/12 có bao nhiêu phiếu?", dataset="support_cases", metrics=["count"],
                            date_range={"field": "created_at", "preset": "custom",
                                        "from_date": "2026-12-01", "to_date": "2026-12-15"})
    assert custom.date_range == {"field": "created_at", "from": "2025-12-01", "to": "2025-12-15"}


def test_period_put_in_filters_becomes_the_date_range():
    """Eval 2026-11-12: 59 lần LLM đặt kỳ trong filters, bị chặn rồi gọi lại (mất một bước)."""
    moved = _compile_asked("Tháng 10 bán được những sản phẩm nào?", dataset="product_ownerships", metrics=["count"],
                           filters=[{"field": "created_at", "op": "contains", "value": "2023-10"}])
    assert moved.date_range == {"field": "created_at", "from": "2026-10-01", "to": "2026-10-31"}
    assert "filters" not in moved.body
    assert moved.ignored == (
        "filters created_at contains 2023-10 → date_range",
        "date_range.year=2023 (year not in the question: using the latest such period)",
    )
    # Hai điều kiện ngày (d2): cái đầu thành date_range, cái sau là điều kiện ngày thứ hai; cả hai đổi năm.
    two = _compile_asked("Phiếu tạo tháng 10 nhưng tháng 11 mới đóng?", dataset="support_cases", metrics=["count"],
                         filters=[{"field": "created_at", "op": "contains", "value": "2023-10"},
                                  {"field": "closed_at", "op": "contains", "value": "2023-11"}])
    assert two.date_range == {"field": "created_at", "from": "2026-10-01", "to": "2026-10-31"}
    assert two.body["filters"] == [{"field": "closed_at", "op": "contains", "value": "2026-11"}]
    part = _compile(metrics=["count"], filters=[{"field": "created_at_year", "op": "eq", "value": "2026"}])
    assert part.date_range == {"field": "created_at", "from": "2026-01-01", "to": "2026-12-31"}


def test_month_number_in_filters_becomes_the_latest_such_month():
    """Eval 2026-11-12 (d1): `created_at_month eq "12"` bị chặn 3/3 lần rồi mới gọi lại bằng date_range."""
    december = _compile_asked("Tháng 12 có bao nhiêu khách mới?", dataset="customers", metrics=["count"],
                              filters=[{"field": "created_at_month", "op": "eq", "value": "12"}])
    assert december.date_range == {"field": "created_at", "from": "2025-12-01", "to": "2025-12-31"}
    assert december.body["filters"] == [NO_SPAM]
    # Tháng và năm ở hai cột ảo: ghép thành một tháng; năm không có trong câu hỏi vẫn bị bỏ.
    paired = _compile_asked("Tháng 12 năm 2024 có bao nhiêu khách mới?", dataset="customers", metrics=["count"],
                            filters=[{"field": "created_at_year", "op": "eq", "value": "2024"},
                                     {"field": "created_at_month", "op": "eq", "value": "12"}])
    assert paired.date_range == {"field": "created_at", "from": "2024-12-01", "to": "2024-12-31"}
    unstated = _compile_asked("Tháng 12 có bao nhiêu khách mới?", dataset="customers", metrics=["count"],
                              filters=[{"field": "created_at_month", "op": "eq", "value": "12"},
                                       {"field": "created_at_year", "op": "eq", "value": "2026"}])
    assert unstated.date_range["from"] == "2025-12-01"


def test_filter_repeating_the_date_range_period_is_dropped_not_rejected():
    """Eval 2026-11-12: date_range tháng 10 kèm `created_at contains "2026-10"` bị chặn 8 lần."""
    repeated = _compile_asked("Tháng 10 nhân viên nào có nhiều phiếu nhất?", dataset="support_assignments",
                              dimensions=["assigned_to"], metrics=["count"],
                              date_range={"field": "created_at", "preset": "month", "month": 10, "year": 2026},
                              filters=[{"field": "created_at", "op": "contains", "value": "2026-10"}])
    assert repeated.date_range == {"field": "created_at", "from": "2026-10-01", "to": "2026-10-31"}
    assert "filters" not in repeated.body
    # Năm 2026 trùng kỳ gần nhất: không báo bỏ năm.
    assert repeated.ignored == ("filters created_at contains 2026-10 (same period as date_range)",)
    month_part = _compile(metrics=["count"], date_range={"field": "created_at", "preset": "month", "month": 10},
                          filters=[{"field": "created_at_month", "op": "eq", "value": "10"}])
    assert month_part.body["filters"] == [NO_SPAM]
    # Kỳ khác date_range trên cùng cột: mâu thuẫn, vẫn chặn.
    with pytest.raises(RawQueryError, match="is a date column"):
        _compile(metrics=["count"], date_range={"field": "created_at", "preset": "month", "month": 10},
                 filters=[{"field": "created_at", "op": "contains", "value": "2026-09"}])


def test_null_checks_ignore_any_value():
    """Eval 2026-11-12 (r2): not_null với value "" làm hỏng validate cả lần gọi."""
    compiled = _compile(metrics=["count"], filters=[{"field": "assigned_sales_id", "op": "not_null", "value": ""}])
    assert compiled.body["filters"] == [{"field": "assigned_sales_id", "op": "not_null"}, NO_SPAM]


def test_table_name_used_as_relation_gets_the_relation_to_use():
    """Eval 2026-11-12 (r1): `support_cases.x` thay vì `case_id.x` trên support_assignments."""
    with pytest.raises(RawQueryError, match=r"join through case_id, e\.g\. case_id\.customer_organization_id"):
        _compile_on("support_assignments", metrics=["count_distinct:support_cases.customer_organization_id"])


def test_stated_years_reads_numbers_and_relative_words_in_every_user_turn():
    assert stated_years(["Tháng 10 có bao nhiêu phiếu?"], NOW, TZ) == frozenset()
    assert stated_years(["Năm ngoái và năm 2023", "năm nay thì sao"], NOW, TZ) == {2025, 2023, 2026}
    assert stated_years(["mã 120234, đơn 20231"], NOW, TZ) == frozenset()


def test_second_date_filter_must_be_on_another_column_than_date_range():
    with pytest.raises(RawQueryError, match="is a date column"):
        _compile_on("support_cases", metrics=["count"],
                    date_range={"field": "closed_at", "preset": "this_month"},
                    filters=[{"field": "closed_at", "op": "contains", "value": "2023-10"}])
    with pytest.raises(RawQueryError, match="is a date column"):
        _compile_on("support_cases", metrics=["count"],
                    date_range={"field": "created_at", "preset": "this_month"},
                    filters=[{"field": "closed_at", "op": "contains", "value": "tháng 10"}])


@pytest.mark.parametrize(("date_range", "expected"), [
    # NOW = 02/11/2026 giờ Việt Nam.
    ({"preset": "month", "month": 10}, ("2026-10-01", "2026-10-31")),
    ({"preset": "month", "month": 11}, ("2026-11-01", "2026-11-30")),
    ({"preset": "month", "month": 12}, ("2025-12-01", "2025-12-31")),     # tháng 12 gần nhất
    ({"preset": "month", "month": 2, "year": 2024}, ("2024-02-01", "2024-02-29")),
    ({"preset": "year", "year": 2025}, ("2025-01-01", "2025-12-31")),
    ({"preset": "year"}, ("2026-01-01", "2026-12-31")),
])
def test_calendar_presets_are_computed_by_code(date_range, expected):
    compiled = _compile(metrics=["count"], date_range={"field": "created_at", **date_range})
    assert (compiled.body["date_range"]["from"], compiled.body["date_range"]["to"]) == expected
    assert compiled.ignored == ()


def test_calendar_preset_needs_month_and_reports_stray_fields():
    with pytest.raises(RawQueryError, match="preset=month needs month"):
        _compile(metrics=["count"], date_range={"field": "created_at", "preset": "month"})
    compiled = _compile(metrics=["count"], date_range={
        "field": "created_at", "preset": "month", "month": 10, "from_date": "2023-10-01",
    })
    assert compiled.body["date_range"]["from"] == "2026-10-01"
    assert compiled.ignored == ("date_range.from_date (preset=month)",)


def test_order_by_on_an_unselected_column_is_added_to_select_in_list_mode():
    compiled = _compile(select=["full_name", "phone"], order_by=[{"field": "created_at", "dir": "desc"}],
                        limit=5)
    assert compiled.body["select"] == ["full_name", "phone", "created_at"]
    assert compiled.body["order_by"] == [{"field": "created_at", "dir": "desc"}]
    assert compiled.columns == ("full_name", "phone", "created_at") and compiled.ignored == ()
    full = _compile(select=[f"c{i}" for i in range(12)], order_by=[{"field": "created_at", "dir": "desc"}])
    assert "order_by" not in full.body and full.ignored == ("order_by created_at (not among the chosen columns)",)


def test_live_column_type_wins_over_static_index():
    query = RawQuery.model_validate({"dataset": "customers", "mode": "aggregate", "metrics": ["count"],
                                     "filters": [{"field": "assigned_sales_id", "op": "eq", "value": "an"}]})
    with pytest.raises(RawQueryError, match="only takes real UUIDs"):
        compile_raw(query, now=NOW, tz=TZ)
    # CRM đổi cột thành text: không còn chặn.
    live = compile_raw(query, now=NOW, tz=TZ, column_type=lambda table, column: "text")
    assert live.body["filters"][0]["value"] == "an"


def test_tool_rejects_name_on_uuid_column_before_crm():
    api = FakeCrmApi()
    registry, _ = _tools(api)
    outcome = _invoke(registry, "crm_query", {
        "dataset": "customers", "metrics": ["count"],
        "filters": [{"field": "assigned_sales_id", "op": "eq", "value": "Zzyzx"}],
    })
    assert outcome.error_code == "tool_invalid_args" and "uuid" in outcome.error_detail
    assert api.requests == []


def test_schema_rejects_blocked_tables_and_bad_paths():
    with pytest.raises(ValueError):
        RawQuery.model_validate({"dataset": "keygen_history", "mode": "list", "select": ["id"]})
    with pytest.raises(ValueError):
        _query(select=["code; drop table x"])
    with pytest.raises(ValueError):
        _query(metrics=["median:qty"])


# ---------------------------------------------------------------------------
# Tool crm_query với CRM giả
# ---------------------------------------------------------------------------

def test_list_query_maps_columns_and_reports_total():
    api = FakeCrmApi([
        {"rows": [{"code": "KH09", "full_name": "Anna Hohmeier", "assigned_sales_id__username": "an",
                   "notes": "x" * 500}]},
        {"rows": [{"count": 3}]},
    ])
    registry, _ = _tools(api)
    outcome = _invoke(registry, "crm_query", {
        "dataset": "customers",
        "select": ["code", "full_name", "assigned_sales_id.username", "notes"],
        "filters": [{"field": "full_name", "op": "contains", "value": "hohmeier"}],
        "limit": 1,
    })

    assert outcome.ok, outcome.error_detail
    output = outcome.output
    assert isinstance(output, QueryOutput)
    [row] = output.rows
    assert row["assigned_sales_id.username"] == "an" and row["full_name"] == "Anna Hohmeier"
    assert len(row["notes"]) == 300 and row["notes"].endswith("…")
    assert (output.returned, output.total, output.has_more, output.next_offset) == (1, 3, True, 1)
    [select, count] = api.bodies()
    assert select["select"][2] == "assigned_sales_id.username" and count["metrics"] == ["count"]
    assert api.requests[0].headers["Authorization"] == f"Bearer {TOKEN}"


def test_aggregate_query_maps_metric_names_and_totals():
    api = FakeCrmApi([{
        "rows": [{"assigned_to__username": "an", "count": 5,
                  "count_distinct_case_id__product_item_id__customer_id": 4}],
        "totals": {"count": 9, "count_distinct_case_id__product_item_id__customer_id": 7},
    }])
    registry, _ = _tools(api)
    outcome = _invoke(registry, "crm_query", {
        "dataset": "support_assignments", "dimensions": ["assigned_to.username"],
        "metrics": ["count", "count_distinct:case_id.product_item_id.customer_id"],
    })

    assert outcome.ok, outcome.error_detail
    assert outcome.output.rows == [{
        "assigned_to.username": "an", "count": 5, "count_distinct:case_id.product_item_id.customer_id": 4,
    }]
    assert outcome.output.totals == {"count": 9, "count_distinct:case_id.product_item_id.customer_id": 7}
    assert (outcome.output.total, outcome.output.has_more) == (None, False)


def test_crm_400_goes_back_to_the_llm_with_crm_message():
    api = FakeCrmApi(status=400, error='invalid report query: unknown select column "nam"')
    registry, _ = _tools(api)
    outcome = _invoke(registry, "crm_query", {"dataset": "customers", "select": ["nam"]})

    assert outcome.error_code == "crm_query_invalid"
    assert outcome.error_detail == 'invalid report query: unknown select column "nam"'


@pytest.mark.parametrize(("status", "code"), [(403, "crm_forbidden"), (401, "crm_auth_failed"),
                                              (500, "crm_unavailable")])
def test_crm_access_errors_keep_their_codes(status, code):
    registry, _ = _tools(FakeCrmApi(status=status))
    outcome = _invoke(registry, "crm_query", {"dataset": "purchase_orders", "metrics": ["count"]})
    assert outcome.error_code == code


def test_blocked_paths_never_reach_crm():
    api = FakeCrmApi()
    registry, _ = _tools(api)
    outcome = _invoke(registry, "crm_query", {"dataset": "lock_requests", "select": ["status", "unlock_key"]})

    assert outcome.error_code == "tool_invalid_args"
    assert "lock_requests.unlock_key is not available" in outcome.error_detail
    assert api.requests == []
    blocked_table = _invoke(registry, "crm_query", {"dataset": "keygen_history", "select": ["id"]})
    assert blocked_table.error_code == "tool_invalid_args" and api.requests == []


def test_only_queries_sent_to_crm_count_toward_the_crm_limit():
    """2026-11-12: lần bị compile chặn không tốn lượt CRM; trần 4 chỉ đếm lần gửi CRM, lần thử tổng
    do runner giới hạn qua max_calls_per_turn."""
    api = FakeCrmApi()
    registry, _ = _tools(api)
    bad = {"dataset": "customers", "metrics": ["count"],
           "filters": [{"field": "assigned_sales_id", "op": "eq", "value": "Hiếu"}]}
    good = {"dataset": "customers", "metrics": ["count"]}
    outcomes = _invoke_many(registry, [("crm_query", bad), ("crm_query", bad), *[("crm_query", good)] * 5])

    assert [outcome.error_code for outcome in outcomes] == [
        "tool_invalid_args", "tool_invalid_args", None, None, None, None, "tool_call_limit",
    ]
    assert "at most 4 CRM queries per turn" in outcomes[-1].error_detail
    assert len(api.bodies()) == 4
    spec = registry.get("crm_query")
    assert spec.max_calls_per_turn == 6


def test_missing_crm_user_is_rejected():
    registry, _ = _tools(FakeCrmApi())
    outcome = _invoke(registry, "crm_query", {"dataset": "customers", "metrics": ["count"]}, token=None)
    assert outcome.error_code == "crm_user_missing"


# ---------------------------------------------------------------------------
# Giám sát chất lượng query: metadata trên trace, audit có giá trị sau cờ
# ---------------------------------------------------------------------------

HOHMEIER = {
    "dataset": "customers", "select": ["code", "full_name"],
    "filters": [{"field": "full_name", "op": "contains", "value": "Hohmeier"}],
    "date_range": {"field": "created_at", "preset": "this_month", "from_date": None, "to_date": None},
}


def _audit_records(caplog):
    return [json.loads(record.getMessage()) for record in caplog.records if record.name == AUDIT_LOGGER]


def _turn_with_three_attempts(audit: QueryAudit, caplog):
    """LLM gửi JSON hỏng, rồi đường dẫn bị chặn, rồi query hợp lệ nhưng 0 dòng."""
    api = FakeCrmApi([{"rows": []}, {"rows": [{"count": 0}]}])
    registry, _ = _tools(api, audit=audit)
    trace = Trace("req-q")
    caplog.set_level("INFO")
    with activate(trace):
        outcomes = _invoke_many(registry, [
            ("crm_query", '{"dataset": "customers", "select": ['),
            ("crm_query", {"dataset": "lock_requests", "select": ["unlock_key"]}),
            ("crm_query", HOHMEIER),
        ])
    return outcomes, trace


def test_audit_is_off_by_default_and_trace_has_only_metadata(caplog):
    outcomes, trace = _turn_with_three_attempts(QueryAudit(enabled=False), caplog)

    assert [outcome.error_code for outcome in outcomes] == ["tool_invalid_args", "tool_invalid_args", None]
    assert _audit_records(caplog) == []
    root = trace.root.attributes
    assert root["crm_query_attempts"] == 3
    assert root["crm_query_outcomes"] == ["invalid_args", "rejected", "empty"]
    assert root["filters"] == ["full_name contains"] and root["filter_value_counts"] == ["1"]
    # Ngày đã đổi ra (không phải PII) nằm trên trace.
    assert root["date_from"] <= root["date_to"] and len(root["date_from"]) == 10
    # Giá trị filter không nằm trong trace hay log thường.
    assert "Hohmeier" not in json.dumps(trace.to_dict(), ensure_ascii=False)
    assert all("Hohmeier" not in record.getMessage() for record in caplog.records)


def test_audit_records_every_attempt_with_values_but_no_rows(caplog):
    _, trace = _turn_with_three_attempts(QueryAudit(enabled=True), caplog)

    records = _audit_records(caplog)
    assert [(item["attempt"], item["phase"], item["outcome"]) for item in records] == [
        (1, "invalid_args", "invalid_args"), (2, "rejected", "rejected"), (3, "sent", "empty"),
    ]
    assert all(item["request_id"] == "req-q" and item["trace_id"] == trace.trace_id for item in records)
    invalid, rejected, sent = records
    assert invalid["arguments_raw"].startswith('{"dataset"') and "arguments" not in invalid
    assert "unlock_key" in rejected["error_detail"] and "body" not in rejected
    assert sent["body"]["filters"][0]["value"] == "Hohmeier"
    assert sent["count_body"]["metrics"] == ["count"]
    assert sent["arguments"]["filters"][0]["value"] == "Hohmeier"
    assert (sent["returned"], sent["total"]) == (0, 0) and sent["date_from"] and sent["date_to"]
    assert all("rows" not in item for item in records)
    # Audit không lọt vào trace.
    assert "Hohmeier" not in json.dumps(trace.to_dict(), ensure_ascii=False)


def test_audit_records_crm_error_and_ignored_fields(caplog):
    api = FakeCrmApi(status=400, error='invalid report query: unknown select column "nam"')
    registry, _ = _tools(api, audit=QueryAudit(enabled=True))
    trace = Trace("req-q")
    caplog.set_level("INFO")
    with activate(trace):
        [outcome] = _invoke_many(registry, [("crm_query", {
            "dataset": "customers", "mode": "list", "select": ["nam"], "metrics": ["count"],
        })])

    assert outcome.error_code == "crm_query_invalid"
    [record] = _audit_records(caplog)
    assert (record["phase"], record["outcome"], record["error_code"]) == ("sent", "crm_invalid", "crm_query_invalid")
    assert record["ignored"] == ["dimensions/metrics (mode=list)"]
    assert trace.root.attributes["ignored"] == ["dimensions/metrics (mode=list)"]
    assert trace.root.attributes["crm_query_outcomes"] == ["crm_invalid"]


def test_rows_are_cut_to_fit_budget():
    api = FakeCrmApi([{"rows": [{"code": f"KH{i:02d}"} for i in range(20)]}, {"rows": [{"count": 20}]}])
    registry, _ = _tools(api)
    output = _invoke(registry, "crm_query", {"dataset": "customers", "select": ["code"]}).output
    full = output.to_llm(10_000, len)
    small = output.to_llm(len(json.dumps(full, ensure_ascii=False)) - 30, len)

    assert "truncated" not in full and len(full["rows"]) == 20
    assert small["truncated"] is True and len(small["rows"]) + small["omitted_rows"] == 20


# ---------------------------------------------------------------------------
# Tool crm_schema và cache
# ---------------------------------------------------------------------------

def test_schema_describes_tables_hides_secrets_and_is_cached():
    now = [0.0]
    api = FakeCrmApi(tables={name: _live_table(name) for name in ("customers", "auth_users")})
    registry, cache = _tools(api, clock=lambda: now[0])

    outcome = _invoke(registry, "crm_schema", {"tables": ["customers", "auth_users"]})
    assert outcome.ok, outcome.error_detail
    output = outcome.output
    assert isinstance(output, SchemaOutput)
    customers, users = output.tables
    assert "customer_type:text=lead|student|official|spam|lost" in customers.columns
    assert "assigned_sales_id->auth_users" in customers.relations
    assert "created_at" in customers.date_columns and customers.note
    assert not any(column.startswith("password_hash") for column in users.columns)
    assert users.hidden_columns == ["password_hash"]

    _invoke(registry, "crm_schema", {"tables": ["customers"]})
    assert len(api.gets()) == 2                       # lần hai lấy từ cache
    now[0] = 601.0
    _invoke(registry, "crm_schema", {"tables": ["customers"]})
    assert len(api.gets()) == 3                       # hết hạn: gọi lại
    assert cache.cached("customers") is not None


def test_schema_tells_how_to_filter_people_and_lists_child_tables():
    """Ca 'nhân viên Hiếu': cột trỏ tới auth_users là UUID, họ tên ở bảng con user_profiles."""
    customers = describe_table("customers", LiveTable(
        columns={column: "uuid" for column in TABLES["customers"].columns},
        relations=dict(TABLES["customers"].relations),
    ))
    assert "assigned_sales_id" in customers.person_filter and "user_profiles" in customers.person_filter
    assert "created_at_month" not in customers.note

    users = describe_table("auth_users", LiveTable(columns={"id": "uuid", "username": "text"}, relations={}))
    assert users.person_filter is None
    # Bảng hồ sơ và bảng nối (ít cột) đứng đầu, danh sách bị cắt có ghi số còn lại.
    assert {"user_profiles.user_id", "user_roles.user_id", "user_organizations.user_id"} <= set(users.referenced_by)
    assert len(users.referenced_by) == 13 and users.referenced_by[-1].startswith("... (+")
    # Bảng không trỏ tới auth_users thì không có gợi ý; cột bị chặn không lộ qua referenced_by.
    products = describe_table("products", LiveTable(columns={"id": "uuid", "name": "text"}, relations={}))
    assert products.person_filter is None and "product_items.product_id" in products.referenced_by
    assert all("password" not in item and "token" not in item
               for items in map(lambda name: describe_table(
                   name, LiveTable(columns={}, relations={})).referenced_by, QUERYABLE_TABLES)
               for item in items)


def test_guide_covers_staff_name_lookup_and_no_date_for_current_state():
    spec = build_crm_query_tool(
        CrmReportClient(BASE_URL, timeout_s=5, transport=httpx.MockTransport(FakeCrmApi())),
        CrmSchemaCache(CrmReportClient(BASE_URL, timeout_s=5), ttl_s=600), tz=TZ,
    )
    assert "user_profiles" in spec.guide and "first_name contains" in spec.guide
    assert "hiện tại" in spec.guide and "date_range = null" in spec.guide
    assert "KHÔNG BAO GIỜ đặt tên người" in spec.guide
    # Luật từ schema CRM 2026-11-12: xoá mềm tự lọc, cột vòng đời, giờ VN và ranh giới UTC.
    assert "không thêm filter deleted_at" in spec.guide and "KẾT THÚC" in spec.guide
    assert "user_id.is_active" in spec.guide and "07:00" in spec.guide
    # Nhân viên theo vai trò: user_roles + known_values, không đếm auth_users, không đoán mã.
    assert "→ user_roles" in spec.guide and "count_distinct:user_id" in spec.guide
    assert "không đếm auth_users" in spec.guide and "KHÔNG tự dịch hay đoán mã" in spec.guide
    date_range = RawQuery.model_json_schema()["properties"]["date_range"]
    assert "hiện tại" in date_range["description"]


def test_unknown_table_on_crm_is_invalid_and_not_cached():
    api = FakeCrmApi(tables={})
    registry, cache = _tools(api)
    outcome = _invoke(registry, "crm_schema", {"tables": ["leads"]})

    assert outcome.error_code == "crm_query_invalid"
    assert cache.cached("leads") is None


def test_query_uses_live_relations_from_cache():
    live = {**_live_table("customers"), "relations": [{"name": "new_partner_id", "table": "organizations"}]}
    api = FakeCrmApi([{"rows": []}, {"rows": [{"count": 0}]}], tables={"customers": live})
    registry, _ = _tools(api)
    _invoke(registry, "crm_schema", {"tables": ["customers"]})

    outcome = _invoke(registry, "crm_query", {"dataset": "customers", "select": ["new_partner_id.name"]})
    assert outcome.ok, outcome.error_detail


def test_describe_table_hides_relations_into_blocked_tables():
    live = LiveTable(columns={"id": "uuid", "key_id": "uuid"}, relations={"key_id": "keygen_history"})
    description = describe_table("lock_requests", live)
    assert description.relations == []


def _ownerships_live() -> dict:
    """Payload GET /reports/tables/product_ownerships theo dạng CRM trả từ 2026-11-12."""
    return {
        "table": "product_ownerships",
        "timezone": "UTC",
        "deleted_at_meaning": "ended",
        "columns": [
            {"name": "id", "type": "uuid", "description": "Primary key."},
            {"name": "is_current", "type": "boolean", "description": "True only for the present owner."},
            {"name": "owner_customer_id", "type": "uuid", "description": "Customer that owns the item " + "x" * 300},
            {"name": "transferred_from_ownership_id", "type": "uuid", "description": "Previous ownership."},
            {"name": "deleted_at", "type": "timestamp without time zone", "timezone": "UTC",
             "description": "END of the ownership period - NOT a deletion."},
        ],
        "relations": [
            {"name": "owner_customer_id", "table": "customers", "ref_column": "id",
             "cardinality": "many_to_one", "nullable": False, "description": "Owner."},
            {"name": "transferred_from_ownership_id", "table": "product_ownerships", "ref_column": "id",
             "cardinality": "one_to_one", "nullable": True, "description": "Previous row."},
        ],
        "referenced_by": [
            {"table": "product_ownership_transfer_requests", "column": "ownership_id", "ref_column": "id",
             "cardinality": "one_to_many", "nullable": False, "description": "Transfer."},
            {"table": "goods_inspections", "column": "ownership_id", "ref_column": "id",   # chưa triển khai
             "cardinality": "one_to_many", "nullable": True, "description": "x"},
        ],
    }


def test_schema_carries_crm_descriptions_relations_and_deleted_at_meaning():
    api = FakeCrmApi(
        tables={"product_ownerships": _ownerships_live()},
        datasets=[{"name": "product_ownerships", "description": "Ownership history of a product item."}],
    )
    registry, _ = _tools(api)
    outcome = _invoke(registry, "crm_schema", {"tables": ["product_ownerships"]})
    assert outcome.ok, outcome.error_detail
    [table] = outcome.output.tables

    assert table.description == "Ownership history of a product item."
    assert "is_current:bool — True only for the present owner." in table.columns
    assert "id:uuid" in table.columns                                  # cột hiển nhiên: bỏ mô tả
    owner = next(column for column in table.columns if column.startswith("owner_customer_id"))
    assert owner.endswith("…") and len(owner) < 200
    assert "owner_customer_id->customers" in table.relations
    assert "transferred_from_ownership_id->product_ownerships (1-1) (có thể trống)" in table.relations
    assert "KẾT THÚC" in table.deleted_at and "is_null" in table.deleted_at
    assert table.referenced_by == ["product_ownership_transfer_requests.ownership_id"]

    _invoke(registry, "crm_schema", {"tables": ["product_ownerships"]})
    assert len(api.dataset_gets()) == 1                                # mô tả bảng cũng được cache


def test_schema_works_without_table_descriptions_and_retries_them():
    api = FakeCrmApi(tables={"customers": {**_live_table("customers"), "deleted_at_meaning": "deleted"}})
    registry, _ = _tools(api)
    outcome = _invoke(registry, "crm_schema", {"tables": ["customers"]})
    assert outcome.ok, outcome.error_detail
    [customers] = outcome.output.tables
    assert customers.description is None and "không cần lọc deleted_at" in customers.deleted_at

    _invoke(registry, "crm_schema", {"tables": ["customers"]})
    assert len(api.dataset_gets()) == 2                                # lỗi không được cache


ROLE_ROWS = [
    {"code": "KHO", "name": "KHO"},
    {"code": "accountant", "name": "Accountant"},
    {"code": "sales", "name": "Sales User"},
]


def _user_roles_live() -> dict:
    return {
        "table": "user_roles",
        "columns": [{"name": "user_id", "type": "uuid"}, {"name": "role_id", "type": "uuid"}],
        "relations": [{"name": "role_id", "table": "roles"}, {"name": "user_id", "table": "auth_users"}],
    }


def test_schema_lists_current_roles_for_user_roles_and_caches_them():
    """Vai trò do admin tạo (không phải enum): crm_schema lấy giá trị thật thay vì để LLM đoán mã."""
    api = FakeCrmApi(tables={"user_roles": _user_roles_live(), "roles": _live_table("roles")},
                     lookups={"roles": ROLE_ROWS})
    registry, _ = _tools(api)
    outcome = _invoke(registry, "crm_schema", {"tables": ["user_roles", "roles"]})
    assert outcome.ok, outcome.error_detail
    user_roles, roles = outcome.output.tables

    expected = ["KHO", "accountant = Accountant", "sales = Sales User"]
    assert user_roles.known_values == {"role_id.code": expected}
    assert roles.known_values == {"code": expected}
    [lookup] = api.lookup_bodies()                                     # hai bảng, một lần gọi CRM
    assert lookup["filters"] == [{"field": "kind", "op": "eq", "value": "system"}]
    assert "count_distinct:user_id" in user_roles.note and "is_active" in user_roles.note

    _invoke(registry, "crm_schema", {"tables": ["user_roles"]})
    assert len(api.lookup_bodies()) == 1                               # cache cùng TTL schema


def test_schema_says_when_roles_cannot_be_listed():
    """Token không đủ quyền đọc roles: tool vẫn chạy, LLM được bảo xem giá trị thật trước khi lọc."""
    api = FakeCrmApi(tables={"user_roles": _user_roles_live()}, lookup_status=403)
    registry, cache = _tools(api)
    outcome = _invoke(registry, "crm_schema", {"tables": ["user_roles"]})
    assert outcome.ok, outcome.error_detail
    [user_roles] = outcome.output.tables
    assert "không lấy được danh sách" in user_roles.known_values["role_id.code"][0]

    _invoke(registry, "crm_schema", {"tables": ["user_roles"]})
    assert len(api.lookup_bodies()) == 2                               # lỗi không được cache


def test_lookup_tables_are_queryable_and_values_are_cut():
    assert set(LOOKUP_TABLES) <= set(QUERYABLE_TABLES)
    many = [{"name": f"s{i:03d}", "label_vi": f"Trạng thái {i}"} for i in range(61)]
    api = FakeCrmApi(tables={"customer_statuses": _live_table("customer_statuses")},
                     lookups={"customer_statuses": many})
    registry, _ = _tools(api)
    [table] = _invoke(registry, "crm_schema", {"tables": ["customer_statuses"]}).output.tables
    values = table.known_values["name"]
    assert len(values) == 61 and values[0] == "s000 = Trạng thái 0" and values[-1].startswith("... (còn nữa")


def test_tables_crm_no_longer_exposes_or_not_released_are_unavailable():
    for name in ("sales_users", "user_types", "goods_inspections", "material_requests"):
        assert name not in QUERYABLE_TABLES
    assert all(name not in tables for tables in TABLE_GROUPS.values()
               for name in ("sales_users", "user_types"))
    with pytest.raises(PathError, match="goods_inspections is not available"):
        check_path("goods_returns", "inspection_id.status", lambda table, column: "goods_inspections")
    live = LiveTable(columns={"id": "uuid", "inspection_id": "uuid"}, relations={"inspection_id": "goods_inspections"})
    assert describe_table("goods_returns", live).relations == []


def test_tools_convert_for_openai_strict():
    registry, _ = _tools(FakeCrmApi())
    registry.validate_for(OPENAI_CAPABILITIES)
    tools = registry.provider_tools(registry.allowed(make_service_principal()), "openai_strict")
    query = next(tool for tool in tools if tool["function"]["name"] == "crm_query")

    parameters = query["function"]["parameters"]
    assert parameters["required"] == [
        "dataset", "mode", "select", "dimensions", "metrics", "filters", "date_range", "include_inactive",
        "order_by", "limit", "offset",
    ]
    preset = parameters["properties"]["date_range"]["properties"]["preset"]
    assert "custom" in preset["enum"] and None not in preset["enum"]
    # Tên bảng kiểm trong code (không lặp enum 116 tên ở hai tool); bảng bị chặn vẫn không qua.
    assert "enum" not in parameters["properties"]["dataset"]
    with pytest.raises(ValueError, match="keygen_history does not exist or is not available"):
        RawQuery.model_validate({"dataset": "keygen_history", "mode": "list", "select": ["id"]})
    with pytest.raises(ValueError, match="did you mean customers"):
        RawQuery.model_validate({"dataset": "customer", "mode": "list", "select": ["id"]})
    schema_tool = next(tool for tool in tools if tool["function"]["name"] == "crm_schema")
    assert "enum" not in schema_tool["function"]["parameters"]["properties"]["tables"]["items"]
    assert "Hỗ trợ khách (phiếu hỗ trợ): support_cases" in schema_tool["function"]["description"]
