"""Khoảng ngày và kỳ báo cáo theo múi giờ cấu hình (mặc định Asia/Ho_Chi_Minh).

Mọi khoảng là nửa mở [start, end). Preset "this_*" và "last_N_days" kết thúc ở
cuối hôm nay (không kéo vào tương lai); "last_*" là kỳ trọn vẹn liền trước.
"""

import re
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Literal

TimeGrainName = Literal["day", "week", "month"]


def local_midnight(day: date, tz: tzinfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz)


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _quarter_start(day: date) -> date:
    return date(day.year, (day.month - 1) // 3 * 3 + 1, 1)


def preset_range(preset: str, now: datetime, tz: tzinfo) -> tuple[datetime, datetime]:
    today = now.astimezone(tz).date()
    tomorrow = today + timedelta(days=1)
    week = today - timedelta(days=today.weekday())
    month = _month_start(today)
    quarter = _quarter_start(today)
    year = date(today.year, 1, 1)
    ranges: dict[str, tuple[date, date]] = {
        "today": (today, tomorrow),
        "yesterday": (today - timedelta(days=1), today),
        "this_week": (week, tomorrow),
        "last_week": (week - timedelta(days=7), week),
        "this_month": (month, tomorrow),
        "last_month": (_add_months(month, -1), month),
        "last_7_days": (today - timedelta(days=6), tomorrow),
        "last_30_days": (today - timedelta(days=29), tomorrow),
        "this_quarter": (quarter, tomorrow),
        "last_quarter": (_add_months(quarter, -3), quarter),
        "this_year": (year, tomorrow),
        "last_year": (date(today.year - 1, 1, 1), year),
    }
    start, end = ranges[preset]
    return local_midnight(start, tz), local_midnight(end, tz)


def calendar_range(
    month: int | None,
    year: int | None,
    now: datetime,
    tz: tzinfo,
) -> tuple[date, date]:
    """Kỳ lịch trọn vẹn [ngày đầu, ngày cuối] (bao gồm hai đầu), không cắt ở hôm nay.

    month có, year None: tháng đó gần nhất không sau tháng hiện tại ("tháng 10" hỏi ngày
    11/11/2026 → 10/2026; "tháng 12" → 12/2025). month có, year có: đúng tháng đó.
    month None: cả năm `year` (None = năm nay).
    """
    today = now.astimezone(tz).date()
    if month is None:
        target = year or today.year
        return date(target, 1, 1), date(target, 12, 31)
    if year is None:
        year = today.year if month <= today.month else today.year - 1
    first = date(year, month, 1)
    return first, _add_months(first, 1) - timedelta(days=1)


_YEAR_DIGITS = re.compile(r"(?<!\d)(20\d\d)(?!\d)")
# Từ chỉ năm tương đối → độ lệch so với năm nay (có dấu và không dấu).
_RELATIVE_YEARS: tuple[tuple[str, int], ...] = (
    ("năm nay", 0), ("nam nay", 0),
    ("năm ngoái", -1), ("nam ngoai", -1), ("năm trước", -1), ("nam truoc", -1),
    ("năm kia", -2), ("nam kia", -2),
)


def stated_years(texts: Sequence[str], now: datetime, tz: tzinfo) -> frozenset[int]:
    """Các năm người dùng nêu trong `texts` (câu hỏi và các lượt trước): số 20xx và "năm nay/ngoái/kia".

    Dùng để bỏ năm LLM tự điền mà câu hỏi không nêu (eval 2026-11-12: "tháng 10" bị điền 2023,
    "tháng 12" bị điền 2026 dù prompt có ngày hôm nay).
    """
    this_year = now.astimezone(tz).year
    years: set[int] = set()
    for text in texts:
        years.update(int(match) for match in _YEAR_DIGITS.findall(text))
        lowered = text.lower()
        years.update(this_year + offset for phrase, offset in _RELATIVE_YEARS if phrase in lowered)
    return frozenset(years)


def latest_year_of(month: int, day: int, now: datetime, tz: tzinfo) -> int:
    """Năm gần nhất mà ngày `day/month` không sau hôm nay (cùng quy tắc với `calendar_range`)."""
    today = now.astimezone(tz).date()
    return today.year if (month, day) <= (today.month, today.day) else today.year - 1


def end_of_today(now: datetime, tz: tzinfo) -> datetime:
    return local_midnight(now.astimezone(tz).date() + timedelta(days=1), tz)


def period_start(moment: datetime, grain: TimeGrainName, tz: tzinfo) -> date:
    day = moment.astimezone(tz).date()
    if grain == "month":
        return _month_start(day)
    if grain == "week":
        return day - timedelta(days=day.weekday())
    return day


def period_key(start: date, grain: TimeGrainName) -> str:
    if grain == "month":
        return f"{start.year}-{start.month:02d}"
    if grain == "week":
        iso = start.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return start.isoformat()


def _next_period(start: date, grain: TimeGrainName) -> date:
    if grain == "month":
        return _add_months(start, 1)
    return start + timedelta(days=7 if grain == "week" else 1)


def periods_between(start: datetime, end: datetime, grain: TimeGrainName, tz: tzinfo) -> list[str]:
    """Khóa các kỳ giao với [start, end), theo thứ tự thời gian."""
    keys: list[str] = []
    current = period_start(start, grain, tz)
    while local_midnight(current, tz) < end:
        keys.append(period_key(current, grain))
        current = _next_period(current, grain)
    return keys
