"""Đọc response của CRM Reporting API: tên cột trong response và giá trị an toàn để đưa LLM."""

import re
from datetime import UTC, datetime, tzinfo
from typing import Any

DEFAULT_MAX_TEXT_CHARS = 120
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
# Thời điểm ISO có giờ (dấu cách hoặc T), tuỳ chọn giây, phần lẻ và múi giờ (Z, +00, +07:00).
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}(:?\d{2})?)?")


def api_column(path: str) -> str:
    """Tên cột trong response: `.` → `__`, `:` → `_` (quy tắc của API)."""
    return path.replace(".", "__").replace(":", "_")


def render_value(value: Any, tz: tzinfo, max_chars: int = DEFAULT_MAX_TEXT_CHARS) -> Any:
    """Giá trị an toàn để đưa LLM; thời điểm đổi sang `tz` (giờ hiển thị cho nhân viên).

    CRM lưu mọi timestamp theo UTC (xác nhận 2026-11-12): giá trị không kèm múi giờ, dù là
    `datetime` hay chuỗi ("2026-10-01 02:00:00.123456"), được hiểu là UTC. Chuỗi chỉ có ngày
    (cột `date`, kỳ `*_day/_month`) giữ nguyên.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        return _local(value, tz)
    if isinstance(value, str) and _TIMESTAMP.fullmatch(value):
        try:
            return _local(datetime.fromisoformat(value), tz)
        except ValueError:
            pass
    text = _CONTROL.sub(" ", str(value)).strip()
    if len(text) > max_chars:
        text = text[:max_chars - 1].rstrip() + "…"
    return text


def _local(moment: datetime, tz: tzinfo) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(tz).isoformat(timespec="minutes")


__all__ = ["api_column", "render_value"]
