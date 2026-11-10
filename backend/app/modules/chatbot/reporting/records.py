"""Chế độ danh sách (tool `crm_records`): kiểm tra RecordQuery, lọc/sort/cắt trang, hiển thị an toàn.

Chỉ cột khai báo trong `DatasetSpec.list_columns` được đọc và trả về (whitelist): cột nội
dung tự do, liên hệ hay bí mật không có trong catalog nên không bao giờ tới LLM. Chuỗi bị
bỏ ký tự điều khiển và cắt `MAX_TEXT_CHARS`.

- list_api (tickets): record từ API danh sách → `filter_records` của engine → sort → trang.
- report_api: `select` của Reporting API + một query `count` cùng filter để biết tổng
  (API không trả tổng cho `select`).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Any

from app.modules.chatbot.schemas.system.records import RecordQuery

from .catalog import DatasetSpec
from .engine import filter_records
from .report_api import MAX_ROWS, api_column, api_date_range, base_filters
from .validate import Condition, ReportQueryError, condition_of, date_range_of

DEFAULT_RECORDS = 10
MAX_TEXT_CHARS = 120
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


@dataclass(frozen=True)
class NormalizedRecords:
    dataset: DatasetSpec
    fields: tuple[str, ...]
    filters: tuple[Condition, ...]
    date_field: str | None
    start: datetime | None
    end: datetime | None
    sort: tuple[tuple[str, str], ...]
    limit: int
    offset: int
    now: datetime
    tz: tzinfo


@dataclass(frozen=True)
class RecordPage:
    items: list[dict[str, Any]]
    total: int | None
    applied_filters: tuple[str, ...] = ()


def validate_records(
    query: RecordQuery,
    datasets: dict[str, DatasetSpec],
    *,
    now: datetime,
    tz: tzinfo,
) -> NormalizedRecords:
    spec = datasets.get(query.dataset)
    if spec is None or not spec.list_columns:
        raise ReportQueryError(f"dataset {query.dataset!r} cannot be listed")
    errors: list[str] = []
    allowed = list(spec.list_columns)
    fields = tuple(dict.fromkeys(query.fields))
    unknown = [name for name in fields if name not in allowed]
    if unknown:
        errors.append(f"fields: {', '.join(unknown)} not allowed here; allowed: {', '.join(allowed)}")

    filters: list[Condition] = []
    for index, item in enumerate(query.filters):
        try:
            filters.append(condition_of(spec, item.field, item.operator, item.value))
        except ReportQueryError as error:
            errors.append(f"filters[{index}]: {error}")
    date_field, start, end = date_range_of(errors, spec, query.date_range, now, tz)

    sort = tuple((item.field, item.direction) for item in query.sort)
    bad_sort = [field for field, _ in sort if field not in fields]
    if bad_sort:
        errors.append(f"sort: {', '.join(bad_sort)} must also be in fields")
    if len({field for field, _ in sort}) < len(sort):
        errors.append("sort: each field at most once")
    if not sort and spec.default_date_field in fields:
        sort = ((spec.default_date_field, "desc"),)

    if errors:
        raise ReportQueryError("; ".join(errors))
    return NormalizedRecords(
        dataset=spec, fields=fields, filters=tuple(filters), date_field=date_field,
        start=start, end=end, sort=sort, limit=query.limit or DEFAULT_RECORDS,
        offset=query.offset, now=now, tz=tz,
    )


# ---------------------------------------------------------------------------
# list_api
# ---------------------------------------------------------------------------

def list_records(query: NormalizedRecords, records: Sequence[Any]) -> RecordPage:
    spec = query.dataset
    matched = filter_records(
        spec, records, query.filters,
        date_field=query.date_field, start=query.start, end=query.end, now=query.now,
    )
    rows = [
        {name: _get(spec, name, record, query.now) for name in query.fields}
        for record in matched
    ]
    for field, direction in reversed(query.sort):
        present = [row for row in rows if row.get(field) is not None]
        missing = [row for row in rows if row.get(field) is None]
        present.sort(key=lambda row: _sort_key(row[field]), reverse=direction == "desc")
        rows = present + missing
    page = rows[query.offset:query.offset + query.limit]
    return RecordPage([render(row, query.tz) for row in page], len(matched))


def _get(spec: DatasetSpec, name: str, record: Any, now: datetime) -> Any:
    get = spec.list_columns[name].get
    assert get is not None, f"column {spec.name}.{name} has no list API getter"
    return get(record, now)


def _sort_key(value: Any) -> Any:
    return value.casefold() if isinstance(value, str) else value


# ---------------------------------------------------------------------------
# report_api
# ---------------------------------------------------------------------------

def compile_records(query: NormalizedRecords) -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]:
    """(query select, query count, filter hệ thống/mặc định đã áp dụng)."""
    spec = query.dataset
    assert spec.report is not None
    filters, labels = base_filters(spec, query.filters)
    date_range = api_date_range(spec, query.date_field, query.start, query.end, now=query.now, tz=query.tz)
    common: dict[str, Any] = {}
    if filters:
        common["filters"] = filters
    if date_range is not None:
        common["date_range"] = date_range
    select = {
        "dataset": spec.report.table,
        "select": [_path(spec, name) for name in query.fields],
        **common,
        "limit": min(query.limit, MAX_ROWS),
        "offset": query.offset,
    }
    if query.sort:
        select["order_by"] = [
            {"field": _path(spec, field), "dir": direction} for field, direction in query.sort
        ]
    count = {"dataset": spec.report.table, "metrics": ["count"], **common}
    return select, count, tuple(labels)


def report_records(
    query: NormalizedRecords,
    rows: Sequence[dict[str, Any]],
    count_rows: Sequence[dict[str, Any]],
    applied_filters: tuple[str, ...],
) -> RecordPage:
    spec = query.dataset
    items = [
        render({name: row.get(api_column(_path(spec, name))) for name in query.fields}, query.tz)
        for row in rows[:query.limit]
    ]
    total = None
    if count_rows:
        try:
            total = int(float(count_rows[0].get("count")))
        except (TypeError, ValueError):
            total = None
    return RecordPage(items, total, applied_filters)


def _path(spec: DatasetSpec, name: str) -> str:
    path = spec.list_columns[name].api_path
    assert path is not None, f"column {spec.name}.{name} has no report API path"
    return path


# ---------------------------------------------------------------------------
# Hiển thị
# ---------------------------------------------------------------------------

def render(row: dict[str, Any], tz: tzinfo) -> dict[str, Any]:
    return {name: render_value(value, tz) for name, value in row.items()}


def render_value(value: Any, tz: tzinfo) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        return value.astimezone(tz).isoformat(timespec="minutes")
    text = _CONTROL.sub(" ", str(value)).strip()
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS - 1].rstrip() + "…"
    return text
