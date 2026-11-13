from pydantic import AwareDatetime, BaseModel

from app.modules.chatbot.reporting.catalog import DatasetSpec, FieldSpec, MetricSpec
from app.modules.chatbot.reporting.engine import run_report
from app.modules.chatbot.reporting.validate import validate_query
from app.modules.chatbot.schemas.system.report import ReportQuery
from tests.chatbot.report_fakes import NOW, TICKETS, TZ, case, normalized, records

SEP_OCT = {"field": "created_at", "start": "2026-09-01", "end": "2026-11-01"}


def _run(items=None, **fields):
    return run_report(normalized(**fields), records(items))


def test_parse_drops_sensitive_fields_and_go_zero_time():
    [record] = records([case("1", "2026-10-01T00:00:00+00:00", status="new")])

    dumped = record.model_dump()
    assert "subject" not in dumped and "description" not in dumped
    assert record.closed_at is None


def test_parse_skips_malformed_items():
    parsed, skipped = TICKETS.parse([case("1", "2026-10-01T00:00:00+00:00"), {"id": "x"}])
    assert len(parsed) == 1 and skipped == 1


def test_totals_without_dimensions():
    result = _run(metrics=[
        "ticket_count", "active_ticket_count", "closed_ticket_count",
    ])

    # Phiếu 7 (delete_pending) bị loại bởi filter hệ thống.
    assert result.rows == [{"ticket_count": 6, "active_ticket_count": 2, "closed_ticket_count": 3}]
    assert result.matched_count == 6


def test_resolved_counts_as_done_with_resolution_time():
    items = [
        case("1", "2026-10-01T00:00:00+00:00", hours_to_close=2),
        case("2", "2026-10-02T00:00:00+00:00", status="resolved", hours_to_close=6),
        case("3", "2026-10-03T00:00:00+00:00", status="new", assignee=None),
    ]
    result = _run(items, metrics=["closed_ticket_count", "active_ticket_count",
                                  "avg_open_to_close_hours"])
    assert result.rows == [
        {"closed_ticket_count": 2, "active_ticket_count": 1, "avg_open_to_close_hours": 4.0},
    ]
    by_group = {row["status_group"]: row["ticket_count"]
                for row in _run(items, dimensions=["status_group"]).rows}
    assert by_group == {"closed": 2, "active": 1}


def test_metrics_use_their_own_conditions():
    result = _run(metrics=["unassigned_ticket_count", "distinct_customer_count",
                           "avg_open_to_close_hours"])
    assert result.rows == [{
        "unassigned_ticket_count": 1,
        "distinct_customer_count": 4,
        "avg_open_to_close_hours": 5.33,        # (2 + 4 + 10) / 3, chỉ phiếu closed
    }]
    [row] = _run(metrics=["max_open_to_close_hours", "avg_open_age_hours"]).rows
    assert row["max_open_to_close_hours"] == 10
    # Phiếu 3 (13 ngày 1 giờ) và 4 (8 ngày 1 giờ) chưa đóng.
    assert row["avg_open_age_hours"] == 253.0


def test_empty_result_still_returns_one_total_row():
    result = _run(date_range={"field": "created_at", "preset": "today"},
                  metrics=["ticket_count", "avg_open_to_close_hours"])
    assert result.rows == [{"ticket_count": 0, "avg_open_to_close_hours": None}]


def test_filters_are_combined_with_and():
    result = _run(filters=[
        {"field": "status_group", "operator": "eq", "value": "active"},
        {"field": "age_hours", "operator": "gt", "value": 240},
    ])
    assert result.rows == [{"ticket_count": 1}]      # chỉ phiếu 3 mở quá 10 ngày


def test_contains_matches_substring_ignoring_case_and_skips_missing_values():
    by_customer = _run(filters=[{"field": "customer", "operator": "contains", "value": "CÔNG TY a"}])
    assert by_customer.rows == [{"ticket_count": 3}]          # c1 (2 phiếu) và c4 cùng tên
    by_assignee = _run(filters=[{"field": "assignee", "operator": "contains", "value": "viên B"}])
    assert by_assignee.rows == [{"ticket_count": 2}]          # phiếu chưa gán (None) không khớp


def test_group_by_dimension_sorted_and_limited():
    result = _run(dimensions=["product_model"], sort=[{"field": "ticket_count", "direction": "desc"}],
                  limit=2)

    assert result.rows == [
        {"product_model": "F86", "ticket_count": 3},
        {"product_model": "6AH", "ticket_count": 1},
    ]
    assert result.total_groups == 4                  # F86, 6AH, F54, unknown


def test_missing_values_and_unknown_models_have_labels():
    by_assignee = {row["assignee"]: row["ticket_count"] for row in _run(dimensions=["assignee"]).rows}
    assert by_assignee == {"Nhân viên A": 3, "(chưa gán)": 1, "Nhân viên B": 2}
    models = {row["product_model"] for row in _run(dimensions=["product_model"]).rows}
    assert "unknown" in models and "XYZ" not in models


def test_customer_groups_by_id_and_shows_name():
    rows = _run(dimensions=["customer"], sort=[{"field": "customer", "direction": "asc"}]).rows
    # c1 và c4 cùng tên "Công ty A" nhưng là hai khách hàng.
    assert [(row["customer"], row["ticket_count"]) for row in rows] == [
        ("Công ty A", 2), ("Công ty A", 1), ("Công ty B", 2), ("Công ty C", 1),
    ]


def test_none_sorts_last_in_both_directions():
    rows = _run(dimensions=["status"], metrics=["avg_open_to_close_hours"],
                sort=[{"field": "avg_open_to_close_hours", "direction": "asc"}]).rows
    assert rows[0] == {"status": "closed", "avg_open_to_close_hours": 5.33}
    assert all(row["avg_open_to_close_hours"] is None for row in rows[1:])


def test_month_comparison_has_delta():
    result = _run(date_range=SEP_OCT, time_grain="month")

    assert result.rows == [
        {"period": "2026-09", "ticket_count": 1},
        {"period": "2026-10", "ticket_count": 4,
         "change": {"ticket_count": {"delta": 3, "delta_pct": 300.0}}},
    ]


def test_empty_periods_are_filled_per_dimension():
    result = _run(date_range=SEP_OCT, time_grain="month", dimensions=["product_model"],
                  sort=[{"field": "ticket_count", "direction": "desc"}])

    rows = [(r["product_model"], r["period"], r["ticket_count"], r.get("change")) for r in result.rows]
    assert rows == [
        ("F86", "2026-09", 1, None),
        ("F86", "2026-10", 2, {"ticket_count": {"delta": 1, "delta_pct": 100.0}}),
        # Bằng nhau thì giữ thứ tự xuất hiện (sort ổn định).
        ("6AH", "2026-09", 0, None),
        ("6AH", "2026-10", 1, {"ticket_count": {"delta": 1, "delta_pct": None}}),
        ("F54", "2026-09", 0, None),            # kỳ không có phiếu vẫn có dòng 0
        ("F54", "2026-10", 1, {"ticket_count": {"delta": 1, "delta_pct": None}}),
    ]
    assert result.total_groups == 3


def test_period_limit_applies_to_dimension_combinations():
    result = _run(date_range=SEP_OCT, time_grain="month", dimensions=["product_model"],
                  sort=[{"field": "ticket_count", "direction": "desc"},
                        {"field": "period", "direction": "desc"}], limit=1)

    assert [(r["product_model"], r["period"]) for r in result.rows] == [
        ("F86", "2026-10"), ("F86", "2026-09"),
    ]
    assert result.total_groups == 3


def test_no_records_in_range_gives_zero_periods():
    result = _run(date_range={"field": "closed_at", "preset": "last_week"}, time_grain="day")
    assert len(result.rows) == 7
    assert {row["ticket_count"] for row in result.rows} == {0}


class Order(BaseModel):
    color: str
    amount: float
    created_at: AwareDatetime


ORDERS = DatasetSpec(
    name="tickets",           # tên phải nằm trong enum của contract; engine không đọc tên
    description="Dataset giả để kiểm tra engine độc lập với ticket.",
    source_path="/orders",
    record_model=Order,
    fields={"status": FieldSpec("string", lambda r, now: r.color, "Màu.")},
    metrics={"ticket_count": MetricSpec("sum", "Tổng tiền.", value=lambda r, now: r.amount)},
    date_fields={"created_at": lambda r, now: r.created_at},
    default_date_field="created_at",
)


def test_engine_runs_any_dataset_spec():
    orders, _ = ORDERS.parse([
        {"color": "Red", "amount": 1.5, "created_at": "2026-10-01T00:00:00Z"},
        {"color": "red", "amount": 2, "created_at": "2026-10-02T00:00:00Z"},
        {"color": "Blue", "amount": 4, "created_at": "2026-10-02T00:00:00Z"},
    ])
    query = validate_query(
        ReportQuery.model_validate({
            "dataset": "tickets", "metrics": ["ticket_count"],
            "filters": [{"field": "status", "operator": "eq", "value": "RED"}],
        }),
        {"tickets": ORDERS}, now=NOW, tz=TZ,
    )

    assert run_report(query, orders).rows == [{"ticket_count": 3.5}]

