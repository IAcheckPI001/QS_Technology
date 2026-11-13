"""Kiểm và chuẩn hoá giá trị filter của `crm_query` theo kiểu cột (luật chung, suy ra từ schema).

Mục tiêu: query sai kiểu không tới CRM, vì CRM vẫn chạy và trả 0 dòng (sai im lặng). Ví dụ đo
được 2026-11-11: tên người trên cột uuid, `created_at in ["last_month"]`, `closed_at contains
"2023-10"` kèm date_range kỳ khác.

- uuid: eq/neq/in/not_in chỉ nhận UUID thật; không `contains`.
- int/number: chuẩn hoá cách viết số ("1.000", "1,5"); không parse được mới từ chối; không `contains`.
- bool: true/false/1/0/có/không → "true"/"false"; không `contains`.
- Cột có giá trị hợp lệ (CHECK/ENUM): so không phân biệt hoa thường, gửi giá trị chuẩn; ngoài tập
  thì từ chối kèm danh sách.
- Cột ngày (và cột ảo chia kỳ): kỳ thời gian đi qua date_range. Filter chỉ được `is_null`/
  `not_null`, hoặc `contains` "YYYY"/"YYYY-MM"/"YYYY-MM-DD" trên cột ngày KHÁC cột của date_range
  (điều kiện ngày thứ hai, vd tạo tháng 10 nhưng đóng tháng 11).
- Kiểu khác hoặc không biết: không kiểm (CRM quyết như trước).
`is_null`/`not_null` không có giá trị nên luôn qua.
"""

import re
from collections.abc import Sequence
from typing import Any

from .policy import DATE_KINDS, DATE_PART

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
DATE_TEXT_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
_THOUSANDS_RE = re.compile(r"^-?\d{1,3}([.,]\d{3})+$")
_TRUE = frozenset({"true", "1", "yes", "có", "co", "đúng", "dung"})
_FALSE = frozenset({"false", "0", "no", "không", "khong", "sai"})
_NULL_OPS = ("is_null", "not_null")
_MAX_LISTED = 30


class ValueRuleError(ValueError):
    """Giá trị filter không hợp kiểu cột; message gửi lại cho LLM."""


def check_filter(
    item: dict[str, Any],
    kind: str | None,
    allowed: Sequence[str],
    *,
    date_range_field: str | None,
) -> dict[str, Any]:
    """Filter đã chuẩn hoá (giá trị đúng dạng) hoặc ValueRuleError."""
    op = item["op"]
    if op in _NULL_OPS:
        return item
    field = item["field"]
    if kind in DATE_KINDS or kind == DATE_PART:
        return _date_filter(item, kind, date_range_field)
    if kind == "uuid":
        if op == "contains":
            raise ValueRuleError(
                f"{field} is a uuid column: contains is not allowed, filter by a text column through "
                f"the relation (e.g. {field}.username, {field}.full_name, {field}.name)",
            )
        bad = [value for value in _values(item) if not UUID_RE.match(value)]
        if bad:
            raise ValueRuleError(
                f"{field} is a uuid column and only takes real UUIDs, got {bad[:3]}, filter by a text "
                f"column through the relation (e.g. {field}.username, {field}.name) or look up the id first",
            )
        return item
    if kind in ("int", "number"):
        _no_contains(field, op, kind)
        return _with_values(item, [_number(field, value, kind) for value in _values(item)])
    if kind == "bool":
        _no_contains(field, op, kind)
        return _with_values(item, [_bool(field, value) for value in _values(item)])
    if allowed and op != "contains":
        canonical = {value.casefold(): value for value in allowed}
        mapped = [canonical.get(value.casefold()) for value in _values(item)]
        if any(value is None for value in mapped):
            listed = ", ".join(allowed[:_MAX_LISTED])
            raise ValueRuleError(f"{field} allows only: {listed}")
        return _with_values(item, mapped)                                      # type: ignore[arg-type]
    return item


def _date_filter(item: dict[str, Any], kind: str | None, date_range_field: str | None) -> dict[str, Any]:
    field, op = item["field"], item["op"]
    second_date = (
        kind != DATE_PART and date_range_field is not None and field != date_range_field
        and op == "contains" and DATE_TEXT_RE.match(str(item.get("value", "")))
    )
    if second_date:
        return item
    raise ValueRuleError(
        f"{field} is a date column: put the period in date_range (preset, month/year or custom), not "
        "filters; a month or year the question does not state is year=null (latest, see <now>). Only "
        "is_null/not_null, or contains \"YYYY-MM\" on a second date column other than "
        "date_range.field, are allowed in filters",
    )


def _no_contains(field: str, op: str, kind: str) -> None:
    if op == "contains":
        raise ValueRuleError(f"{field} is a {kind} column: use eq/in, not contains")


def _values(item: dict[str, Any]) -> list[str]:
    value = item.get("value")
    return value if isinstance(value, list) else [value]


def _with_values(item: dict[str, Any], values: list[str]) -> dict[str, Any]:
    value: str | list[str] = values if isinstance(item.get("value"), list) else values[0]
    return {**item, "value": value}


def _number(field: str, raw: str, kind: str) -> str:
    """Dấu phân cách nghìn: cột int "1.000"/"1,000" → 1000, mọi cột "1.000.000" → 1000000.
    Một dấu phẩy, không có chấm: thập phân kiểu Việt ("1,5" → 1.5). Còn lại theo float()."""
    text = raw.strip().replace(" ", "")
    if _THOUSANDS_RE.match(text) and (kind == "int" or text.count(".") + text.count(",") > 1):
        text = text.replace(".", "").replace(",", "")
    elif text.count(",") == 1 and "." not in text:
        text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        raise ValueRuleError(f"{field} is a {kind} column, got {raw!r} (not a number)") from None
    if kind == "int":
        if not number.is_integer():
            raise ValueRuleError(f"{field} is an int column, got {raw!r}")
        return str(int(number))
    return str(int(number)) if number.is_integer() else repr(number)


def _bool(field: str, raw: str) -> str:
    text = raw.strip().casefold()
    if text in _TRUE:
        return "true"
    if text in _FALSE:
        return "false"
    raise ValueRuleError(f"{field} is a bool column: use true or false, got {raw!r}")


__all__ = ["DATE_TEXT_RE", "UUID_RE", "ValueRuleError", "check_filter"]
