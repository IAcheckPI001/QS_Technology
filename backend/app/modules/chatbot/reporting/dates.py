"""Khoảng ngày và kỳ báo cáo theo múi giờ cấu hình (mặc định Asia/Ho_Chi_Minh).

Mọi khoảng là nửa mở [start, end). Preset "this_*" và "last_N_days" kết thúc ở
cuối hôm nay (không kéo vào tương lai); "last_*" là kỳ trọn vẹn liền trước.
"""

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
