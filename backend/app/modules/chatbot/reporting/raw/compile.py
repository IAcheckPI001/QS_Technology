"""RawQuery (LLM dựng) → JSON của `POST /api/v1/reports/query`, và rows của CRM → rows cho LLM.

Kiểm tra trước khi gọi CRM (lỗi gom thành một RawQueryError gửi lại LLM):
- `mode=list` cần `select`; `mode=aggregate` cần `metrics`/`dimensions`. Field của chế độ kia
  bị bỏ qua và ghi vào `ignored` (OpenAI strict bắt LLM điền mọi field nên chúng hay bị điền
  bừa; báo lỗi thì LLM lặp lại đúng lỗi đó);
- value hợp toán tử (eq/neq/contains: một chuỗi; in/not_in: mảng; is_null/not_null: không có);
- `order_by` theo trường chưa chọn: mode=list thì thêm cột đó vào `select` (còn chỗ), ngược lại
  bị bỏ (CRM sẽ từ chối) và ghi vào `ignored`;
- preset ngày đổi thành from/to bao gồm cả hai đầu (`month`/`year` là kỳ lịch do code tính);
  field không thuộc preset đã chọn bị bỏ và ghi vào `ignored`;
- năm LLM tự điền mà người dùng không nêu (`stated_years`) bị bỏ, dùng kỳ gần nhất; kỳ đặt nhầm
  trong filters khi chưa có date_range được chuyển thành date_range; filter lặp lại kỳ của
  date_range trên cùng cột bị bỏ; dataset trong `hints.DROP_WITH_DATE_RANGE` bỏ filter trạng
  thái hiện tại khi có kỳ (vd is_current);
- filter mặc định của dataset (`hints.DEFAULT_FILTERS`, vd user_roles chỉ tài khoản còn dùng)
  được thêm khi LLM không tự lọc trên cột đó và không đặt `include_inactive`, và ghi vào
  `filters` của applied;
- mọi đường dẫn qua `policy.check_path` (bảng/cột bị chặn, khoá ngoại không biết);
- giá trị filter hợp kiểu cột cuối của đường dẫn (`values.check_filter`: uuid, số, bool, giá trị
  hợp lệ, cột ngày chỉ qua date_range).
Cột/quan hệ có tồn tại hay không do CRM kiểm tra (400 → `crm_query_invalid`).
Hàm thuần, không gọi API.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from typing import Any

from app.modules.chatbot.schemas.system.raw_query import (
    CUSTOM_RANGE,
    MAX_IN_VALUES,
    MAX_RAW_FILTERS,
    MAX_SELECT,
    MONTH_RANGE,
    YEAR_RANGE,
    QueryMode,
    RawDateRange,
    RawFilter,
    RawQuery,
)

from ..dates import calendar_range, end_of_today, latest_year_of, preset_range
from ..records import render_value
from ..report_api import api_column
from .hints import DEFAULT_FILTERS, DROP_WITH_DATE_RANGE
from .policy import (
    DATE_KINDS,
    DATE_PART,
    ColumnType,
    PathError,
    RelationTarget,
    check_path,
    column_kind,
    static_column_type,
    static_relation,
    static_values,
)
from .values import ValueRuleError, check_filter

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 50
DEFAULT_AGGREGATE_LIMIT = 50
MAX_TEXT_CHARS = 300
_EARLIEST = date(1970, 1, 1)
_SINGLE = ("eq", "neq", "contains")


class RawQueryError(ValueError):
    """Query sai hình dạng hoặc chạm bảng/cột bị chặn; message gửi lại cho LLM."""


@dataclass(frozen=True)
class CompiledRaw:
    mode: QueryMode
    body: dict[str, Any]
    count_body: dict[str, Any] | None   # danh sách: đếm tổng cùng filter (select không trả tổng)
    columns: tuple[str, ...]            # tên logic theo thứ tự: select | dimensions + metrics
    filters: tuple[str, ...]            # mô tả filter đã áp dụng (cho applied)
    date_range: dict[str, str] | None   # {"field", "from", "to"} đã đổi ra ngày
    limit: int
    offset: int
    ignored: tuple[str, ...] = ()       # phần argument bị bỏ qua (báo lại cho LLM)


def compile_raw(
    query: RawQuery,
    *,
    now: datetime,
    tz: tzinfo,
    relation_target: RelationTarget = static_relation,
    column_type: ColumnType = static_column_type,
    stated_years: frozenset[int] | None = None,
) -> CompiledRaw:
    """column_type: kiểu gọn của cột (schema sống trước, index tĩnh sau) để kiểm giá trị filter.

    stated_years: các năm người dùng nêu (`dates.stated_years`). Có thì năm LLM tự điền mà không
    nằm trong đó bị bỏ (dùng kỳ gần nhất); None = không đối chiếu (gọi ngoài agent).
    """
    errors: list[str] = []
    ignored: list[str] = []
    dimensions = list(dict.fromkeys(query.dimensions))
    metrics = list(dict.fromkeys(query.metrics))
    if query.mode == "list":
        if not query.select:
            errors.append("mode=list needs select (columns to show)")
        if dimensions or metrics:
            ignored.append("dimensions/metrics (mode=list)")
        columns = tuple(dict.fromkeys(query.select))
        paths: list[str] = list(columns)
    else:
        if not dimensions and not metrics:
            errors.append("mode=aggregate needs metrics (and optional dimensions)")
        if query.select:
            ignored.append("select (mode=aggregate)")
        columns = (*dimensions, *metrics)
        paths = [*dimensions, *(metric.split(":", 1)[1] for metric in metrics if ":" in metric)]

    date_item = query.date_range
    raw_filters = list(query.filters)
    if date_item is None:
        # Chuyển trước khi đối chiếu năm: năm của kỳ chuyển sang được `_date_range` đối chiếu.
        date_item, raw_filters = _period_from_filters(
            query.dataset, raw_filters, relation_target, column_type, ignored,
        )
    if stated_years is not None:
        raw_filters = [
            _ground_filter(query.dataset, item, stated_years, now, tz, relation_target, column_type, ignored)
            for item in raw_filters
        ]
    if date_item is not None:
        dropped = DROP_WITH_DATE_RANGE.get(query.dataset, ())
        for item in [item for item in raw_filters if item.field in dropped]:
            raw_filters.remove(item)
            ignored.append(f"filters {item.field} (has a date_range: count every row in the period)")

    date_range = None
    if date_item is not None:
        try:
            date_range = _date_range(date_item, now, tz, ignored, stated_years)
            paths.append(date_item.field)
        except RawQueryError as error:
            errors.append(f"date_range: {error}")
    if date_range is not None:
        raw_filters = _drop_same_period(
            query.dataset, raw_filters, date_range, relation_target, column_type, ignored,
        )
    date_field = date_item.field if date_item is not None else None

    filters: list[dict[str, Any]] = []
    labels: list[str] = []
    for index, item in enumerate(raw_filters):
        try:
            built = _filter(item)
            built = _typed(query.dataset, built, relation_target, column_type, date_field)
        except (RawQueryError, ValueRuleError) as error:
            errors.append(f"filters[{index}]: {error}")
            continue
        filters.append(built)
        paths.append(item.field)
        labels.append(_describe(built))

    filtered = {item.field for item in raw_filters}
    defaults = DEFAULT_FILTERS.get(query.dataset, ())
    if query.include_inactive:
        if not defaults:
            ignored.append(f"include_inactive ({query.dataset} has no default filter)")
        defaults = ()
    for default in defaults:
        if default.field not in filtered and len(filters) < MAX_RAW_FILTERS:
            filters.append({"field": default.field, "op": default.op, "value": default.value})
            paths.append(default.field)
            labels.append(f"{default.field} {default.op} {default.value} ({default.reason})")

    order_by = []
    for item in query.order_by:
        if item.field not in columns and query.mode == "list" and _is_column(item.field) \
                and len(columns) < MAX_SELECT:
            # "5 khách mới nhất": sắp theo cột chưa chọn thì thêm cột đó, không bỏ im lặng.
            columns = (*columns, item.field)
            paths.append(item.field)
        if item.field in columns:
            order_by.append({"field": item.field, "dir": item.dir})
        else:
            ignored.append(f"order_by {item.field} (not among the chosen columns)")

    for path in dict.fromkeys(paths):
        try:
            check_path(query.dataset, path, relation_target)
        except PathError as error:
            errors.append(str(error))

    if errors:
        raise RawQueryError("; ".join(errors))

    common: dict[str, Any] = {}
    if filters:
        common["filters"] = filters
    if date_range is not None:
        common["date_range"] = date_range
    if query.mode == "list":
        limit = min(query.limit or DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT)
        body: dict[str, Any] = {"dataset": query.dataset, "select": list(columns), **common}
        count_body: dict[str, Any] | None = {"dataset": query.dataset, "metrics": ["count"], **common}
    else:
        limit = query.limit or DEFAULT_AGGREGATE_LIMIT
        body = {"dataset": query.dataset, **common}
        if dimensions:
            body["dimensions"] = dimensions
        if metrics:
            body["metrics"] = metrics
        if dimensions and metrics:
            body["totals"] = True
        count_body = None
    if order_by:
        body["order_by"] = order_by
    body["limit"] = limit
    if query.offset:
        body["offset"] = query.offset
    return CompiledRaw(
        mode=query.mode, body=body, count_body=count_body, columns=columns, filters=tuple(labels),
        date_range=date_range, limit=limit, offset=query.offset, ignored=tuple(ignored),
    )


def _filter(item: RawFilter) -> dict[str, Any]:
    value = item.value
    if item.op in ("is_null", "not_null"):
        return {"field": item.field, "op": item.op}       # value bị bỏ qua
    if item.op in _SINGLE:
        if isinstance(value, list):
            if len(value) != 1:
                raise RawQueryError(f"{item.op} needs one string (use in/not_in for a list)")
            value = value[0]
        if value is None:
            raise RawQueryError(f"{item.op} needs a value")
        return {"field": item.field, "op": item.op, "value": value}
    values = value if isinstance(value, list) else ([value] if value is not None else [])
    values = list(dict.fromkeys(values))
    if not 1 <= len(values) <= MAX_IN_VALUES:
        raise RawQueryError(f"{item.op} needs 1 to {MAX_IN_VALUES} values")
    return {"field": item.field, "op": item.op, "value": values}


def _typed(
    dataset: str,
    item: dict[str, Any],
    relation_target: RelationTarget,
    column_type: ColumnType,
    date_field: str | None,
) -> dict[str, Any]:
    """Kiểm/chuẩn hoá giá trị theo kiểu cột cuối; đường dẫn sai để vòng check_path báo."""
    try:
        table = check_path(dataset, item["field"], relation_target)
    except PathError:
        return item
    column = item["field"].rsplit(".", 1)[-1]
    kind = column_kind(table, column, column_type)
    return check_filter(item, kind, static_values(table, column), date_range_field=date_field)


def _is_column(field: str) -> bool:
    """Đường dẫn cột (không phải metric `count`/`hàm:cột`)."""
    return ":" not in field and field != "count"


def _describe(item: dict[str, Any]) -> str:
    if "value" not in item:
        return f"{item['field']} {item['op']}"
    return f"{item['field']} {item['op']} {item['value']}"


_RANGE_FIELDS = {
    CUSTOM_RANGE: ("from_date", "to_date"),
    MONTH_RANGE: ("month", "year"),
    YEAR_RANGE: ("year",),
}


_UNSTATED_YEAR = "year not in the question: using the latest such period"


def _date_range(
    item: RawDateRange,
    now: datetime,
    tz: tzinfo,
    ignored: list[str],
    stated: frozenset[int] | None = None,
) -> dict[str, str]:
    used = _RANGE_FIELDS.get(item.preset, ())
    stray = [name for name in ("month", "year", "from_date", "to_date")
             if name not in used and getattr(item, name) is not None]
    if stray:
        ignored.append(f"date_range.{'/'.join(stray)} (preset={item.preset})")
    year = item.year
    if stated is not None and year is not None and year not in stated \
            and item.preset in (MONTH_RANGE, YEAR_RANGE):
        if item.preset == MONTH_RANGE and item.month is not None:
            latest = latest_year_of(item.month, 1, now, tz)
        else:
            latest = now.astimezone(tz).year
        if year != latest:            # trùng kỳ gần nhất thì không có gì để báo
            ignored.append(f"date_range.year={year} ({_UNSTATED_YEAR})")
        year = None
    if item.preset == MONTH_RANGE:
        if item.month is None:
            raise RawQueryError("preset=month needs month (1-12)")
        first, last = calendar_range(item.month, year, now, tz)
    elif item.preset == YEAR_RANGE:
        first, last = calendar_range(None, year, now, tz)
    elif item.preset != CUSTOM_RANGE:
        start, end = preset_range(item.preset, now, tz)
        first = start.astimezone(tz).date()
        last = end.astimezone(tz).date() - timedelta(days=1)
    elif item.from_date is None and item.to_date is None:
        raise RawQueryError("preset=custom needs from_date and/or to_date")
    else:
        from_date, to_date = item.from_date, item.to_date
        if stated is not None and from_date is not None and from_date.year not in stated \
                and (to_date is None or to_date.year not in stated):
            shift = latest_year_of(from_date.month, from_date.day, now, tz) - from_date.year
            if shift:
                from_date = _shift_year(from_date, shift)
                to_date = _shift_year(to_date, shift) if to_date is not None else None
                ignored.append(f"date_range.from_date/to_date year ({_UNSTATED_YEAR})")
        first = from_date or _EARLIEST
        last = to_date or end_of_today(now, tz).astimezone(tz).date() - timedelta(days=1)
    if first > last:
        raise RawQueryError("from_date must not be after to_date")
    return {"field": item.field, "from": first.isoformat(), "to": last.isoformat()}


def _shift_year(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:                       # 29/2 sang năm không nhuận
        return day.replace(year=day.year + years, day=28)


# Kỳ viết dạng YYYY, YYYY-MM hoặc YYYY-MM-DD (giá trị filter trên cột ngày).
_PERIOD = re.compile(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?")
_PART_SUFFIX = re.compile(r"_(day|month|year)$")


def _date_kind(
    dataset: str, field: str, relation_target: RelationTarget, column_type: ColumnType,
) -> str | None:
    """"date" (cột ngày), DATE_PART (cột ảo `_day/_month/_year`) hoặc None."""
    try:
        table = check_path(dataset, field, relation_target)
    except PathError:
        return None
    kind = column_kind(table, field.rsplit(".", 1)[-1], column_type)
    if kind in DATE_KINDS:
        return "date"
    return DATE_PART if kind == DATE_PART else None


def _grounded(value: str, stated: frozenset[int], now: datetime, tz: tzinfo) -> str:
    """Giá trị kỳ với năm không có trong câu hỏi đổi sang năm gần nhất (tháng/ngày giữ nguyên)."""
    match = _PERIOD.fullmatch(value)
    if match is None or int(match.group(1)) in stated:
        return value
    month = int(match.group(2)) if match.group(2) else None
    if month is not None and not 1 <= month <= 12:
        return value
    day = int(match.group(3)) if match.group(3) else 1
    year = latest_year_of(month, day, now, tz) if month is not None else now.astimezone(tz).year
    return f"{year}{value[4:]}"


def _ground_filter(
    dataset: str,
    item: RawFilter,
    stated: frozenset[int],
    now: datetime,
    tz: tzinfo,
    relation_target: RelationTarget,
    column_type: ColumnType,
    ignored: list[str],
) -> RawFilter:
    if item.op not in ("eq", "contains") or not isinstance(item.value, str):
        return item
    if _date_kind(dataset, item.field, relation_target, column_type) is None:
        return item
    value = _grounded(item.value, stated, now, tz)
    if value == item.value:
        return item
    ignored.append(f"filters {item.field} {item.op} {item.value} → {value} ({_UNSTATED_YEAR})")
    return item.model_copy(update={"value": value})


_MONTH_NUMBER = re.compile(r"\d{1,2}")


def _period_parts(
    dataset: str, item: RawFilter, relation_target: RelationTarget, column_type: ColumnType,
) -> tuple[str, int | None, int | None, int | None] | None:
    """(cột ngày gốc, năm, tháng, ngày) của filter kỳ; None nếu filter không phải kỳ.

    Nhận `<cột ngày> contains/eq "YYYY[-MM[-DD]]"`, `<cột>_year/_month/_day eq "YYYY[-MM[-DD]]"` và
    `<cột>_month eq "N"` (tháng không kèm năm: năm None).
    """
    if item.op not in ("eq", "contains") or not isinstance(item.value, str):
        return None
    kind = _date_kind(dataset, item.field, relation_target, column_type)
    if kind is None or (kind == DATE_PART and item.op != "eq"):
        return None
    field = _PART_SUFFIX.sub("", item.field) if kind == DATE_PART else item.field
    match = _PERIOD.fullmatch(item.value)
    if match is not None:
        year, month, day = (int(part) if part else None for part in match.groups())
    elif kind == DATE_PART and item.field.endswith("_month") and _MONTH_NUMBER.fullmatch(item.value):
        year, month, day = None, int(item.value), None
    else:
        return None
    if month is not None and not 1 <= month <= 12:
        return None
    if day is not None:
        try:
            date(year, month, day)
        except ValueError:
            return None
    return field, year, month, day


def _period_from_filters(
    dataset: str,
    filters: list[RawFilter],
    relation_target: RelationTarget,
    column_type: ColumnType,
    ignored: list[str],
) -> tuple[RawDateRange | None, list[RawFilter]]:
    """Kỳ LLM đặt nhầm trong filters khi chưa có date_range → date_range (thay vì chặn và bắt gọi lại).

    Chỉ chuyển kỳ đầu tiên (`<cột>_month` và `<cột>_year` cùng cột thì ghép thành một tháng); các
    filter ngày còn lại đi luật "điều kiện ngày thứ hai". Năm chưa đối chiếu với câu hỏi: việc
    đó do `_date_range` làm.
    """
    for item in filters:
        parts = _period_parts(dataset, item, relation_target, column_type)
        if parts is None:
            continue
        field, year, month, day = parts
        used = [item]
        if day is None and (year is None) != (month is None):
            # Chỉ tháng hoặc chỉ năm: tìm phần còn lại ở cột ảo cùng cột ngày (created_at_year + _month).
            for other in filters:
                other_parts = None if other is item else _period_parts(
                    dataset, other, relation_target, column_type,
                )
                if other_parts is None or other_parts[0] != field or other_parts[3] is not None:
                    continue
                if year is None and other_parts[1] is not None and other_parts[2] is None:
                    year = other_parts[1]
                elif month is None and other_parts[2] is not None and other_parts[1] is None:
                    month = other_parts[2]
                else:
                    continue
                used.append(other)
                break
        if day is not None:
            picked = date(year, month, day)
            period = RawDateRange(field=field, preset=CUSTOM_RANGE, from_date=picked, to_date=picked)
        elif month is not None:
            period = RawDateRange(field=field, preset=MONTH_RANGE, month=month, year=year)
        else:
            period = RawDateRange(field=field, preset=YEAR_RANGE, year=year)
        ignored.extend(f"filters {other.field} {other.op} {other.value} → date_range" for other in used)
        return period, [other for other in filters if all(other is not done for done in used)]
    return None, filters


def _drop_same_period(
    dataset: str,
    filters: list[RawFilter],
    date_range: dict[str, str],
    relation_target: RelationTarget,
    column_type: ColumnType,
    ignored: list[str],
) -> list[RawFilter]:
    """Bỏ filter kỳ trên chính cột của date_range mà kỳ của nó chứa trọn date_range (LLM lặp lại kỳ,
    vd date_range tháng 10 + `created_at contains "2026-10"`, eval 2026-11-12: 8 lần bị chặn).
    Kỳ khác date_range thì giữ để `check_filter` chặn như cũ (hai kỳ mâu thuẫn trên một cột).
    """
    first = date.fromisoformat(date_range["from"])
    last = date.fromisoformat(date_range["to"])
    kept: list[RawFilter] = []
    for item in filters:
        parts = _period_parts(dataset, item, relation_target, column_type)
        if parts is None or parts[0] != date_range["field"]:
            kept.append(item)
            continue
        _, year, month, day = parts
        if day is not None:
            covers = first == last == date(year, month, day)
        elif month is not None:
            covers = first.month == last.month == month and first.year == last.year \
                and year in (None, first.year)
        else:
            covers = first.year == last.year == year
        if covers:
            ignored.append(f"filters {item.field} {item.op} {item.value} (same period as date_range)")
        else:
            kept.append(item)
    return kept


def map_rows(
    columns: Sequence[str],
    rows: Sequence[dict[str, Any]],
    tz: tzinfo,
) -> list[dict[str, Any]]:
    """Khóa của CRM (`.` → `__`, `:` → `_`) đổi về tên đã gửi; chuỗi bỏ ký tự điều khiển, cắt ngắn."""
    return [
        {name: render_value(row.get(api_column(name)), tz, MAX_TEXT_CHARS) for name in columns}
        for row in rows
    ]


def map_totals(columns: Sequence[str], totals: dict[str, Any] | None) -> dict[str, Any] | None:
    if not totals:
        return None
    mapped = {name: totals[api_column(name)] for name in columns if api_column(name) in totals}
    return mapped or None


def count_of(rows: Sequence[dict[str, Any]]) -> int | None:
    if not rows:
        return None
    try:
        return int(float(rows[0].get("count")))
    except (TypeError, ValueError):
        return None
