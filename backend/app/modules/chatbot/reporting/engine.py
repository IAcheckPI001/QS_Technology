"""Engine báo cáo: hàm thuần trên danh sách record, chung cho mọi dataset.

Thứ tự: filter hệ thống → filter của query (AND) + date_range → nhóm theo
dimensions (+ kỳ) → metric theo catalog → điền kỳ trống, delta so với kỳ trước →
sort → limit. Engine chỉ đọc DatasetSpec, không biết dataset là ticket hay gì khác.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.modules.chatbot.schemas.system.report import PERIOD

from .catalog import DatasetSpec, FieldSpec, MetricSpec
from .dates import period_key, period_start
from .validate import Condition, NormalizedQuery

CHANGE = "change"

_COMPARE: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda v, x: v == x,
    "ne": lambda v, x: v != x,
    "in": lambda v, x: v in x,
    "not_in": lambda v, x: v not in x,
    "gt": lambda v, x: v is not None and v > x,
    "gte": lambda v, x: v is not None and v >= x,
    "lt": lambda v, x: v is not None and v < x,
    "lte": lambda v, x: v is not None and v <= x,
    "contains": lambda v, x: isinstance(v, str) and str(x).casefold() in v.casefold(),
}


@dataclass(frozen=True)
class ReportResult:
    rows: list[dict[str, Any]]
    total_groups: int           # số nhóm trước limit (có time_grain: số tổ hợp dimension)
    matched_count: int          # số bản ghi sau mọi filter


def run_report(query: NormalizedQuery, records: Sequence[Any]) -> ReportResult:
    matched = _filter(query, records)
    if query.time_grain is None:
        rows = _group_rows(query, matched)
        total = len(rows)
        rows = _sort(rows, query.sort or _default_sort(query))
        if query.dimensions:
            rows = rows[:query.limit]
        return ReportResult(rows, total, len(matched))
    return _period_rows(query, matched)


def compute_metric(metric: MetricSpec, records: Sequence[Any], query: NormalizedQuery) -> Any:
    now = query.now
    rows = [r for r in records if metric.where is None or metric.where(r, now)]
    if metric.agg == "count":
        return len(rows)
    assert metric.value is not None
    values = [v for r in rows if (v := metric.value(r, now)) is not None]
    if metric.agg == "count_distinct":
        return len(set(values))
    if not values:
        return None             # avg/max của tập rỗng: không có giá trị, không phải 0
    if metric.agg == "avg":
        return round(sum(values) / len(values), metric.digits)
    if metric.agg == "max":
        return round(max(values), metric.digits)
    return round(sum(values), metric.digits)


def _filter(query: NormalizedQuery, records: Sequence[Any]) -> list[Any]:
    return filter_records(
        query.dataset, records, query.filters,
        date_field=query.date_field, start=query.start, end=query.end, now=query.now,
    )


def filter_records(
    spec: DatasetSpec,
    records: Sequence[Any],
    filters: Sequence[Condition],
    *,
    date_field: str | None,
    start: datetime | None,
    end: datetime | None,
    now: datetime,
) -> list[Any]:
    """Filter hệ thống → filters (AND) → [start, end) theo trường ngày. Chỉ nguồn list_api."""
    predicates: list[Callable[[Any], bool]] = [
        (lambda r, keep=keep: bool(keep(r, now))) for _, keep in spec.system_filters
    ]
    predicates += [_predicate(spec.fields[c.field], c, now) for c in filters]
    if date_field is not None:
        get_date = spec.date_fields[date_field]
        assert get_date is not None

        def in_range(record: Any) -> bool:
            moment = get_date(record, now)
            return (
                moment is not None
                and (start is None or moment >= start)
                and (end is None or moment < end)
            )

        predicates.append(in_range)
    return [r for r in records if all(predicate(r) for predicate in predicates)]


def _predicate(field: FieldSpec, condition: Condition, now: datetime) -> Callable[[Any], bool]:
    compare = _COMPARE[condition.operator]
    expected = condition.value
    get = field.get
    assert get is not None
    if field.type == "string" and field.casefold:
        def value(record: Any) -> Any:
            raw = get(record, now)
            return raw.casefold() if isinstance(raw, str) else raw
    else:
        def value(record: Any) -> Any:
            return get(record, now)
    return lambda record: compare(value(record), expected)


def _combo(query: NormalizedQuery, record: Any) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """(khóa nhóm, giá trị hiển thị) theo các dimension."""
    keys: list[Any] = []
    shown: list[Any] = []
    for name in query.dimensions:
        field = query.dataset.fields[name]
        display = field.get(record, query.now)
        key = field.key(record, query.now) if field.key else display
        keys.append(key)
        shown.append(field.missing_label if display is None else display)
    return tuple(keys), tuple(shown)


def _groups(query: NormalizedQuery, records: Sequence[Any]) -> tuple[dict, dict]:
    members: dict[tuple, list[Any]] = defaultdict(list)
    labels: dict[tuple, tuple] = {}
    for record in records:
        key, shown = _combo(query, record)
        members[key].append(record)
        labels.setdefault(key, shown)
    return members, labels


def _metrics(query: NormalizedQuery, records: Sequence[Any]) -> dict[str, Any]:
    return {
        name: compute_metric(query.dataset.metrics[name], records, query)
        for name in query.metrics
    }


def _dimension_values(query: NormalizedQuery, shown: tuple) -> dict[str, Any]:
    return dict(zip(query.dimensions, shown))


def _group_rows(query: NormalizedQuery, records: Sequence[Any]) -> list[dict[str, Any]]:
    if not query.dimensions:
        return [_metrics(query, records)]       # một dòng tổng, kể cả khi không có bản ghi
    members, labels = _groups(query, records)
    return [
        {**_dimension_values(query, labels[key]), **_metrics(query, group)}
        for key, group in members.items()
    ]


def _period_rows(query: NormalizedQuery, records: Sequence[Any]) -> ReportResult:
    grain, tz = query.time_grain, query.tz
    assert grain is not None and query.date_field is not None
    get_date = query.dataset.date_fields[query.date_field]
    members, labels = _groups(query, records)
    if not query.dimensions:
        members.setdefault((), [])
        labels.setdefault((), ())

    # Xếp hạng tổ hợp dimension theo giá trị trên cả khoảng; limit áp lên tổ hợp, giữ đủ kỳ.
    combos = [
        {"_key": key, **_dimension_values(query, labels[key]), **_metrics(query, group)}
        for key, group in members.items()
    ]
    rank_sort = [(field, direction) for field, direction in query.sort if field != PERIOD]
    combos = _sort(combos, rank_sort or _default_sort(query))
    total = len(combos)
    if query.dimensions:
        combos = combos[:query.limit]

    descending = (PERIOD, "desc") in query.sort
    rows: list[dict[str, Any]] = []
    for combo in combos:
        by_period: dict[str, list[Any]] = defaultdict(list)
        for record in members[combo["_key"]]:
            moment = get_date(record, query.now)
            by_period[period_key(period_start(moment, grain, tz), grain)].append(record)
        series: list[dict[str, Any]] = []
        previous: dict[str, Any] | None = None
        for period in query.periods:               # kỳ không có bản ghi vẫn có dòng
            row = {
                **_dimension_values(query, labels[combo["_key"]]),
                PERIOD: period,
                **_metrics(query, by_period.get(period, [])),
            }
            if previous is not None:
                row[CHANGE] = _change(query.metrics, previous, row)
            series.append(row)
            previous = row
        rows.extend(reversed(series) if descending else series)
    return ReportResult(rows, total, len(records))


def period_change(metrics: Sequence[str], previous: dict[str, Any], current: dict[str, Any]) -> dict:
    """change.delta/delta_pct của từng metric so với kỳ liền trước (dùng chung cho mọi nguồn)."""
    return _change(metrics, previous, current)


def default_sort(query: NormalizedQuery) -> tuple[tuple[str, str], ...]:
    return _default_sort(query)


def sort_rows(rows: list[dict[str, Any]], sort: Sequence[tuple[str, str]]) -> list[dict[str, Any]]:
    return _sort(rows, sort)


def _change(metrics: Sequence[str], previous: dict[str, Any], current: dict[str, Any]) -> dict:
    change: dict[str, dict[str, Any]] = {}
    for name in metrics:
        before, after = previous[name], current[name]
        if before is None or after is None:
            change[name] = {"delta": None, "delta_pct": None}
            continue
        change[name] = {
            "delta": round(after - before, 2),
            "delta_pct": None if before == 0 else round((after - before) / before * 100, 1),
        }
    return change


def _default_sort(query: NormalizedQuery) -> tuple[tuple[str, str], ...]:
    return ((query.metrics[0], "desc"),)


def _sort(rows: list[dict[str, Any]], sort: Sequence[tuple[str, str]]) -> list[dict[str, Any]]:
    """Sort ổn định nhiều khóa (khóa phụ trước); None luôn xếp cuối."""
    for field, direction in reversed(list(sort)):
        present = [row for row in rows if row.get(field) is not None]
        missing = [row for row in rows if row.get(field) is None]
        present.sort(key=lambda row: row[field], reverse=direction == "desc")
        rows = present + missing
    return rows
