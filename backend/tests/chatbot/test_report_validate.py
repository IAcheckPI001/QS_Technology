import pytest
from pydantic import ValidationError

from app.modules.chatbot.reporting.validate import MAX_PERIODS, ReportQueryError
from tests.chatbot.report_fakes import TZ, normalized, report_query


def _error(**fields) -> str:
    with pytest.raises(ReportQueryError) as error:
        normalized(**fields)
    return str(error.value)


def test_schema_rejects_extra_fields_and_empty_metrics():
    with pytest.raises(ValidationError):
        report_query(subject="x")
    with pytest.raises(ValidationError):
        report_query(metrics=[])
    with pytest.raises(ValidationError):
        report_query(limit=51)


@pytest.mark.parametrize(("value", "expected"), [
    ("in_progress", "in_progress"),
    ("Đang hỗ trợ", "in_progress"),       # nhãn tiếng Việt
    (" CLOSED ", "closed"),
])
def test_enum_values_are_normalized(value, expected):
    query = normalized(filters=[{"field": "status", "operator": "eq", "value": value}])
    assert query.filters[0].value == expected


def test_unknown_enum_value_lists_allowed_values():
    detail = _error(filters=[{"field": "status", "operator": "eq", "value": "đang mở"}])
    assert "unknown value 'đang mở'" in detail
    assert "in_progress (đang hỗ trợ)" in detail


@pytest.mark.parametrize(("value", "expected"), [
    ("Astro 6AH", ("6AH",)),
    (["F86", "ASTRO_6AV"], ("F86", "6AV")),
    ("unknown", ("unknown",)),
])
def test_product_model_uses_registry_aliases(value, expected):
    query = normalized(filters=[{"field": "product_model", "operator": "in", "value": value}])
    assert query.filters[0].value == expected


def test_ambiguous_product_model_is_rejected():
    detail = _error(filters=[{"field": "product_model", "operator": "eq", "value": "10i"}])
    assert "unknown value '10i'" in detail and "10iV" in detail


def test_string_values_compare_case_insensitively():
    query = normalized(filters=[{"field": "category", "operator": "in", "value": ["Alarm", "parameter"]}])
    assert query.filters[0].value == ("alarm", "parameter")


@pytest.mark.parametrize(("item", "message"), [
    ({"field": "assigned", "operator": "gt", "value": True}, "supports operators eq, ne"),
    ({"field": "age_hours", "operator": "gt", "value": "ba ngày"}, "needs a number"),
    ({"field": "assigned", "operator": "eq", "value": "maybe"}, "needs true or false"),
    ({"field": "status", "operator": "eq", "value": ["new", "pending"]}, "needs a single value"),
    ({"field": "status", "operator": "in", "value": []}, "at least one value"),
])
def test_operator_and_value_must_match_field_type(item, message):
    assert message in _error(filters=[item])


def test_bool_and_number_values_are_coerced():
    query = normalized(filters=[
        {"field": "assigned", "operator": "eq", "value": "false"},
        {"field": "age_hours", "operator": "gt", "value": 72},
    ])
    assert [c.value for c in query.filters] == [False, 72.0]


def test_errors_are_collected_in_one_message():
    detail = _error(
        filters=[{"field": "assigned", "operator": "gt", "value": True}],
        sort=[{"field": "status", "direction": "asc"}],
    )
    assert "filters[0]" in detail and "sort: status not allowed here" in detail


def test_sort_must_use_selected_fields_and_period_needs_time_grain():
    assert "sort: period not allowed" in _error(sort=[{"field": "period", "direction": "asc"}])
    query = normalized(
        dimensions=["status"],
        sort=[{"field": "status", "direction": "asc"}, {"field": "ticket_count", "direction": "desc"}],
    )
    assert query.sort == (("status", "asc"), ("ticket_count", "desc"))


def test_date_range_preset_or_dates_resolved_to_local_midnight():
    query = normalized(date_range={"field": "created_at", "start": "2026-10-01", "end": "2026-11-01"})
    assert query.start.isoformat() == "2026-10-01T00:00:00+07:00"
    assert query.end.isoformat() == "2026-11-01T00:00:00+07:00"
    assert query.start.tzinfo == TZ

    preset = normalized(date_range={"field": "closed_at", "preset": "last_month"})
    assert (preset.date_field, preset.start.day, preset.end.month) == ("closed_at", 1, 11)


@pytest.mark.parametrize(("date_range", "message"), [
    ({"field": "created_at", "preset": "this_month", "start": "2026-10-01"}, "not both"),
    ({"field": "created_at"}, "needs preset or start/end"),
    ({"field": "created_at", "start": "2026-11-01", "end": "2026-10-01"}, "start must be before end"),
])
def test_invalid_date_ranges(date_range, message):
    assert message in _error(date_range=date_range)


def test_time_grain_needs_start_and_bounded_periods():
    assert "time_grain requires date_range" in _error(time_grain="month")
    open_end = normalized(date_range={"field": "created_at", "start": "2026-10-01"}, time_grain="month")
    assert open_end.periods == ("2026-10", "2026-11")          # tới hết hôm nay
    assert f"(max {MAX_PERIODS})" in _error(
        date_range={"field": "created_at", "preset": "this_year"}, time_grain="day",
    )


def test_limit_default_and_dedup():
    query = normalized(metrics=["ticket_count", "ticket_count"], dimensions=["status"])
    assert query.metrics == ("ticket_count",)
    assert query.limit == 10
    assert normalized(dimensions=["status"], limit=50).limit == 50
