"""NormalizedQuery → JSON của CRM Reporting Query API, và kết quả API → ReportResult.

LLM không thấy JSON này: đường dẫn cột, filter hệ thống và metric API lấy từ catalog.
Hàm thuần (không gọi API) để test bằng ví dụ của tài liệu CRM.

- Mỗi nhóm metric cùng filter riêng là một query `values` (metric có filter riêng, vd
  `current_assignment_count`, không gộp được vào query gốc). Query gốc luôn có `count`
  để lấy `matched_count`.
- Chia kỳ có dimension: thêm query `ranking` (không chia kỳ) để xếp hạng, cắt limit theo tổ hợp
  dimension và đếm `total_groups` đúng với cả metric không cộng dồn (count_distinct).
- Khoảng ngày nửa mở [start, end) đổi thành `from`/`to` bao gồm cả hai đầu; mọi value là chuỗi.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from typing import Any, Literal

from app.modules.chatbot.schemas.system.report import PERIOD

from .catalog import DatasetSpec, FieldSpec
from .dates import end_of_today
from .engine import CHANGE, ReportResult, default_sort, period_change, sort_rows
from .validate import Condition, NormalizedQuery

MAX_ROWS = 1000                 # trần `limit` của API
BASE_COUNT = "count"
_EARLIEST = date(1970, 1, 1)
_OPERATORS = {"eq": "eq", "ne": "neq", "in": "in", "not_in": "not_in"}
_COUNTING = ("count", "count_distinct")


def api_column(path: str) -> str:
    """Tên cột trong response: `.` → `__`, `:` → `_` (quy tắc của API)."""
    return path.replace(".", "__").replace(":", "_")


@dataclass(frozen=True)
class ApiQuery:
    role: Literal["values", "ranking"]
    metrics: tuple[str, ...]            # tên logic của nhóm metric
    base: bool                          # nhóm không có filter riêng (có `count` gốc)
    body: dict[str, Any]


@dataclass(frozen=True)
class CompiledReport:
    queries: tuple[ApiQuery, ...]
    applied_filters: tuple[str, ...]    # filter hệ thống + mặc định đã áp dụng (mô tả)


@dataclass(frozen=True)
class ApiResult:
    rows: list[dict[str, Any]]
    totals: Mapping[str, Any] | None


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------

def base_filters(
    spec: DatasetSpec,
    filters: Sequence[Condition],
    grouped: Sequence[str] = (),
) -> tuple[list[dict[str, Any]], list[str]]:
    """Filter hệ thống + filter mặc định (khi query không lọc/nhóm trường đó) + filter của query."""
    report = spec.report
    assert report is not None
    result = [dict(item) for _, item in report.system_filters]
    labels = [label for label, _ in report.system_filters]
    used = {condition.field for condition in filters} | set(grouped)
    for label, field_name, item in report.default_filters:
        if field_name not in used:
            result.append(dict(item))
            labels.append(label)
    result += [_api_filter(spec.fields[c.field], c) for c in filters]
    return result, labels


def api_date_range(
    spec: DatasetSpec,
    date_field: str | None,
    start: datetime | None,
    end: datetime | None,
    *,
    now: datetime,
    tz: tzinfo,
) -> dict[str, str] | None:
    if date_field is None:
        return None
    assert spec.report is not None
    first = start.astimezone(tz).date() if start is not None else _EARLIEST
    last_exclusive = (end or end_of_today(now, tz)).astimezone(tz).date()
    return {
        "field": spec.report.date_paths[date_field],
        "from": first.isoformat(),
        "to": (last_exclusive - timedelta(days=1)).isoformat(),
    }


def compile_report(query: NormalizedQuery) -> CompiledReport:
    spec = query.dataset
    report = spec.report
    assert report is not None, f"dataset {spec.name} is not a report_api dataset"
    filters, labels = base_filters(spec, query.filters, query.dimensions)
    date_range = api_date_range(
        spec, query.date_field, query.start, query.end, now=query.now, tz=query.tz,
    )
    dimension_paths = [path for name in query.dimensions for path in _paths(spec.fields[name])]
    period = _period_dimension(query)

    queries: list[ApiQuery] = []
    for metrics, extra in _metric_groups(query):
        base = not extra
        api_metrics = list(dict.fromkeys(
            [*(spec.metrics[m].api_metric or BASE_COUNT for m in metrics), *([BASE_COUNT] if base else [])]
        ))
        common = {"filters": [*filters, *extra], "date_range": date_range}
        values_dims = [*dimension_paths, *([period] if period else [])]
        queries.append(ApiQuery("values", metrics, base, _body(report.table, values_dims, api_metrics, common)))
        if period and dimension_paths:
            queries.append(ApiQuery(
                "ranking", metrics, base, _body(report.table, dimension_paths, api_metrics, common),
            ))
    return CompiledReport(tuple(queries), tuple(labels))


def _body(table: str, dimensions: list[str], metrics: list[str], common: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {"dataset": table, "metrics": metrics}
    if dimensions:
        body["dimensions"] = dimensions
        body["order_by"] = [{"field": metrics[0], "dir": "desc"}]
        body["limit"] = MAX_ROWS
        body["totals"] = True
    if common["filters"]:
        body["filters"] = common["filters"]
    if common["date_range"] is not None:
        body["date_range"] = common["date_range"]
    return body


def _metric_groups(query: NormalizedQuery) -> list[tuple[tuple[str, ...], list[dict[str, Any]]]]:
    """Nhóm metric theo filter riêng; nhóm gốc (không filter riêng) luôn có và đứng đầu."""
    groups: dict[str, tuple[list[str], list[dict[str, Any]]]] = {"[]": ([], [])}
    for name in query.metrics:
        extra = [dict(item) for item in query.dataset.metrics[name].api_filters]
        key = json.dumps(extra, sort_keys=True, ensure_ascii=False)
        groups.setdefault(key, ([], extra))[0].append(name)
    return [(tuple(names), extra) for names, extra in groups.values() if names or not extra]


def _paths(field: FieldSpec) -> list[str]:
    assert field.api_path is not None
    if field.api_label_path and field.api_label_path != field.api_path:
        return [field.api_path, field.api_label_path]
    return [field.api_path]


def _period_dimension(query: NormalizedQuery) -> str | None:
    if query.time_grain is None or query.date_field is None:
        return None
    assert query.dataset.report is not None
    return query.dataset.report.period_dimension(query.date_field, query.time_grain)


def _api_filter(field: FieldSpec, condition: Condition) -> dict[str, Any]:
    path = field.api_filter_path or field.api_path
    assert path is not None
    value = (
        [_api_value(item) for item in condition.value]
        if condition.operator in ("in", "not_in")
        else _api_value(condition.value)
    )
    return {"field": path, "op": _OPERATORS[condition.operator], "value": value}


def _api_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# ---------------------------------------------------------------------------
# Kết quả API → ReportResult
# ---------------------------------------------------------------------------

def merge_report(query: NormalizedQuery, compiled: CompiledReport, results: Sequence[ApiResult]) -> ReportResult:
    """Ghép kết quả các query theo khóa dimension (+ kỳ), rồi sort/limit/điền kỳ/delta như engine."""
    by_role: dict[str, list[tuple[ApiQuery, ApiResult]]] = {"values": [], "ranking": []}
    for api_query, result in zip(compiled.queries, results, strict=True):
        by_role[api_query.role].append((api_query, result))
    period = _period_dimension(query)
    matched = _matched_count(query, by_role["ranking"] or by_role["values"])

    if period is None:
        rows = list(_combine(query, by_role["values"], with_period=False).values())
        if not rows:
            rows = [_empty_metrics(query)]
        total = len(rows) if query.dimensions else 1
        rows = sort_rows(rows, query.sort or default_sort(query))
        if query.dimensions:
            rows = rows[:query.limit]
        return ReportResult(rows, total, matched)

    values = _combine(query, by_role["values"], with_period=True)
    if query.dimensions:
        combos = list(_combine(query, by_role["ranking"], with_period=False).items())
    else:
        combos = [((), _empty_metrics(query))]
    rank_sort = [(field, direction) for field, direction in query.sort if field != PERIOD]
    ranked = sort_rows([{**row, "_key": key} for key, row in combos], rank_sort or default_sort(query))
    total = len(ranked)
    if query.dimensions:
        ranked = ranked[:query.limit]

    descending = (PERIOD, "desc") in query.sort
    rows: list[dict[str, Any]] = []
    for combo in ranked:
        key = combo["_key"]
        labels = {name: combo[name] for name in query.dimensions}
        series: list[dict[str, Any]] = []
        previous: dict[str, Any] | None = None
        for period_key in query.periods:
            found = values.get((*key, period_key))
            metrics = {name: found[name] for name in query.metrics} if found else _empty_metrics(query)
            row = {**labels, PERIOD: period_key, **metrics}
            if previous is not None:
                row[CHANGE] = period_change(query.metrics, previous, row)
            series.append(row)
            previous = row
        rows.extend(reversed(series) if descending else series)
    return ReportResult(rows, total, matched)


def _combine(
    query: NormalizedQuery,
    parts: Sequence[tuple[ApiQuery, ApiResult]],
    *,
    with_period: bool,
) -> dict[tuple, dict[str, Any]]:
    """Khóa (dimension…[, kỳ]) → {dimension hiển thị, metric}; metric thiếu của một nhóm = 0."""
    spec = query.dataset
    period = _period_dimension(query) if with_period else None
    combined: dict[tuple, dict[str, Any]] = {}
    for api_query, result in parts:
        for raw in result.rows:
            key: list[Any] = []
            shown: dict[str, Any] = {}
            for name in query.dimensions:
                field = spec.fields[name]
                assert field.api_path is not None
                key_value = _blank_to_none(raw.get(api_column(field.api_path)))
                label = (
                    _blank_to_none(raw.get(api_column(field.api_label_path)))
                    if field.api_label_path else key_value
                )
                key.append(key_value)
                shown[name] = field.missing_label if label is None else label
            if period is not None:
                period_key = _period_key(raw.get(api_column(period)), query.time_grain)
                if period_key is None:
                    continue
                key.append(period_key)
            entry = combined.setdefault(tuple(key), {**shown, **_empty_metrics(query)})
            for name in api_query.metrics:
                entry[name] = _metric_value(raw.get(api_column(spec.metrics[name].api_metric or BASE_COUNT)))
    return combined


def _matched_count(query: NormalizedQuery, parts: Sequence[tuple[ApiQuery, ApiResult]]) -> int:
    for api_query, result in parts:
        if not api_query.base:
            continue
        if result.totals is not None and BASE_COUNT in result.totals:
            return int(_metric_value(result.totals[BASE_COUNT]) or 0)
        return sum(int(_metric_value(row.get(BASE_COUNT)) or 0) for row in result.rows)
    return 0


def _empty_metrics(query: NormalizedQuery) -> dict[str, Any]:
    return {
        name: 0 if query.dataset.metrics[name].agg in _COUNTING else None
        for name in query.metrics
    }


def _metric_value(raw: Any) -> Any:
    if raw is None or isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return raw
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _blank_to_none(value: Any) -> Any:
    return None if value is None or value == "" else value


def _period_key(raw: Any, grain: str | None) -> str | None:
    """Giá trị kỳ của API (vd `2026-10`, `2026-10-01`, `2026-10-01T00:00:00`) → khóa kỳ của engine."""
    if raw is None or raw == "":
        return None
    text = str(raw)
    return text[:7] if grain == "month" else text[:10]
