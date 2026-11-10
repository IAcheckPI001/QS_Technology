"""Kiểm tra ReportQuery theo catalog của dataset và chuẩn hóa thành truy vấn engine chạy được.

Lỗi gom thành một ReportQueryError, liệt kê giá trị hợp lệ để agent tự sửa call.
Không đọc dữ liệu: chạy trước khi gọi API.
"""

from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Any

from app.modules.chatbot.schemas.system.report import PERIOD, ReportDateRange, ReportQuery

from .catalog import OPERATORS_BY_TYPE, DatasetSpec, FieldSpec
from .dates import end_of_today, local_midnight, periods_between, preset_range

MAX_PERIODS = 62
_LIST_OPERATORS = ("in", "not_in")
_TRUE = {"true", "1", "yes", "có"}
_FALSE = {"false", "0", "no", "không"}


class ReportQueryError(ValueError):
    """Query hợp lệ về schema nhưng sai theo catalog; message gửi lại cho LLM."""


@dataclass(frozen=True)
class Condition:
    field: str
    operator: str
    value: Any                  # đã chuẩn hóa; string so khớp bằng casefold

    def describe(self) -> str:
        value = list(self.value) if isinstance(self.value, tuple) else self.value
        return f"{self.field} {self.operator} {value}"


@dataclass(frozen=True)
class NormalizedQuery:
    dataset: DatasetSpec
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    filters: tuple[Condition, ...]
    date_field: str | None
    start: datetime | None
    end: datetime | None
    time_grain: str | None
    periods: tuple[str, ...]
    sort: tuple[tuple[str, str], ...]
    limit: int
    now: datetime
    tz: tzinfo


def validate_query(
    query: ReportQuery,
    datasets: dict[str, DatasetSpec],
    *,
    now: datetime,
    tz: tzinfo,
) -> NormalizedQuery:
    spec = datasets.get(query.dataset)
    if spec is None:
        raise ReportQueryError(f"dataset {query.dataset!r} is not available")
    errors: list[str] = []

    metrics = tuple(dict.fromkeys(query.metrics))
    _check_names(errors, "metrics", metrics, list(spec.metrics))
    dimensions = tuple(dict.fromkeys(query.dimensions))
    _check_names(errors, "dimensions", dimensions, spec.dimensions())

    filters: list[Condition] = []
    for index, item in enumerate(query.filters):
        try:
            filters.append(_condition(spec, item.field, item.operator, item.value))
        except ReportQueryError as error:
            errors.append(f"filters[{index}]: {error}")

    date_field, start, end = _date_range(errors, spec, query.date_range, now, tz)
    periods: tuple[str, ...] = ()
    if (
        query.time_grain is not None and spec.report is not None and date_field is not None
        and spec.report.period_dimension(date_field, query.time_grain) is None
    ):
        errors.append(
            f"time_grain {query.time_grain} is not available for {spec.name}.{date_field}; "
            f"allowed: {_period_options(spec)}"
        )
    elif query.time_grain is not None:
        if start is None:
            errors.append("time_grain requires date_range with a start (preset or start date)")
        else:
            end = end or end_of_today(now, tz)
            periods = tuple(periods_between(start, end, query.time_grain, tz))
            if len(periods) > MAX_PERIODS:
                errors.append(
                    f"time_grain {query.time_grain} gives {len(periods)} periods "
                    f"(max {MAX_PERIODS}); use a larger grain or a shorter date_range"
                )

    sortable = [*metrics, *dimensions, *([PERIOD] if query.time_grain else [])]
    sort = tuple((item.field, item.direction) for item in query.sort)
    _check_names(errors, "sort", tuple(field for field, _ in sort), sortable)
    if len({field for field, _ in sort}) < len(sort):
        errors.append("sort: each field at most once")

    if errors:
        raise ReportQueryError("; ".join(errors))
    return NormalizedQuery(
        dataset=spec,
        metrics=metrics,
        dimensions=dimensions,
        filters=tuple(filters),
        date_field=date_field,
        start=start,
        end=end,
        time_grain=query.time_grain,
        periods=periods,
        sort=sort,
        limit=min(query.limit or spec.default_limit, spec.max_limit),
        now=now,
        tz=tz,
    )


def _period_options(spec: DatasetSpec) -> str:
    assert spec.report is not None
    options = [
        f"{field} {grain}"
        for field in spec.date_fields
        for grain in ("day", "week", "month")
        if spec.report.period_dimension(field, grain) is not None
    ]
    return ", ".join(options) or "none"


def _check_names(errors: list[str], label: str, names: tuple[str, ...], allowed: list[str]) -> None:
    unknown = [name for name in names if name not in allowed]
    if unknown:
        errors.append(f"{label}: {', '.join(unknown)} not allowed here; allowed: {', '.join(allowed)}")


def _condition(spec: DatasetSpec, name: str, operator: str, raw: Any) -> Condition:
    field = spec.fields.get(name)
    if field is None or not field.filterable:
        raise ReportQueryError(f"field {name} not filterable; allowed: {', '.join(spec.filter_fields())}")
    operators = OPERATORS_BY_TYPE[field.type]
    if operator not in operators:
        raise ReportQueryError(f"{name} ({field.type}) supports operators {', '.join(operators)}")
    if operator in _LIST_OPERATORS:
        items = raw if isinstance(raw, list) else [raw]
        if not items:
            raise ReportQueryError(f"{name} {operator} needs at least one value")
        value: Any = tuple(dict.fromkeys(_scalar(name, field, item) for item in items))
    else:
        if isinstance(raw, list):
            raise ReportQueryError(f"{name} {operator} needs a single value (use in/not_in for a list)")
        value = _scalar(name, field, raw)
    return Condition(name, operator, value)


def _scalar(name: str, field: FieldSpec, raw: Any) -> Any:
    if field.type == "bool":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().casefold()
        if text in _TRUE or text in _FALSE:
            return text in _TRUE
        raise ReportQueryError(f"{name} needs true or false")
    if field.type == "number":
        if isinstance(raw, bool):
            raise ReportQueryError(f"{name} needs a number")
        try:
            return float(raw)
        except (TypeError, ValueError):
            raise ReportQueryError(f"{name} needs a number") from None
    text = str(raw).strip()
    if not text:
        raise ReportQueryError(f"{name} needs a non-empty value")
    if field.type == "string":
        return text.casefold() if field.casefold else text
    normalized = field.normalize(text) if field.normalize else (text if text in field.values else None)
    if normalized is None or normalized not in field.values:
        allowed = ", ".join(
            f"{code} ({field.labels[code]})" if code in field.labels else code for code in field.values
        )
        raise ReportQueryError(f"{name}: unknown value {text!r}; allowed: {allowed}")
    return normalized


def date_range_of(
    errors: list[str],
    spec: DatasetSpec,
    date_range: ReportDateRange | None,
    now: datetime,
    tz: tzinfo,
) -> tuple[str | None, datetime | None, datetime | None]:
    """Khoảng ngày đã chuẩn hóa [start, end) theo múi giờ; lỗi được thêm vào `errors`."""
    return _date_range(errors, spec, date_range, now, tz)


def condition_of(spec: DatasetSpec, name: str, operator: str, raw: Any) -> Condition:
    """Một filter đã kiểm tra theo catalog; raise ReportQueryError nếu sai."""
    return _condition(spec, name, operator, raw)


def _date_range(
    errors: list[str],
    spec: DatasetSpec,
    date_range: ReportDateRange | None,
    now: datetime,
    tz: tzinfo,
) -> tuple[str | None, datetime | None, datetime | None]:
    if date_range is None:
        return None, None, None
    if date_range.field not in spec.date_fields:
        errors.append(f"date_range.field: allowed {', '.join(spec.date_fields)}")
        return None, None, None
    has_dates = date_range.start is not None or date_range.end is not None
    if date_range.preset is not None:
        if has_dates:
            errors.append("date_range: use preset OR start/end, not both")
            return None, None, None
        start, end = preset_range(date_range.preset, now, tz)
        return date_range.field, start, end
    if not has_dates:
        errors.append("date_range: needs preset or start/end")
        return None, None, None
    start = local_midnight(date_range.start, tz) if date_range.start else None
    end = local_midnight(date_range.end, tz) if date_range.end else None
    if start is not None and end is not None and start >= end:
        errors.append("date_range: start must be before end (end is exclusive)")
        return None, None, None
    return date_range.field, start, end
