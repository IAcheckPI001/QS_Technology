from datetime import UTC, datetime

import pytest

from app.modules.chatbot.reporting.dates import (
    period_key,
    period_start,
    periods_between,
    preset_range,
)
from tests.chatbot.report_fakes import NOW, TZ


def _local(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T00:00:00").replace(tzinfo=TZ)


@pytest.mark.parametrize(("preset", "start", "end"), [
    ("today", "2026-11-02", "2026-11-03"),
    ("yesterday", "2026-11-01", "2026-11-02"),
    ("this_week", "2026-11-02", "2026-11-03"),       # NOW là thứ Hai: tuần mới bắt đầu
    ("last_week", "2026-10-26", "2026-11-02"),
    ("this_month", "2026-11-01", "2026-11-03"),      # tới hết hôm nay, không kéo vào tương lai
    ("last_month", "2026-10-01", "2026-11-01"),
    ("last_7_days", "2026-10-27", "2026-11-03"),
    ("last_30_days", "2026-10-04", "2026-11-03"),
    ("this_quarter", "2026-10-01", "2026-11-03"),
    ("last_quarter", "2026-07-01", "2026-10-01"),
    ("this_year", "2026-01-01", "2026-11-03"),
    ("last_year", "2025-01-01", "2026-01-01"),
])
def test_presets_are_half_open_local_ranges(preset, start, end):
    assert preset_range(preset, NOW, TZ) == (_local(start), _local(end))


def test_last_month_crosses_year_boundary():
    january = datetime(2027, 1, 15, tzinfo=UTC)
    assert preset_range("last_month", january, TZ) == (_local("2026-12-01"), _local("2027-01-01"))
    assert preset_range("last_quarter", january, TZ) == (_local("2026-10-01"), _local("2027-01-01"))


def test_period_uses_local_timezone():
    # 20:00 UTC ngày 30/09 là 03:00 ngày 01/10 giờ Việt Nam.
    moment = datetime(2026, 9, 30, 20, 0, tzinfo=UTC)
    assert period_key(period_start(moment, "month", TZ), "month") == "2026-10"
    assert period_key(period_start(moment, "day", TZ), "day") == "2026-10-01"
    assert period_key(period_start(moment, "week", TZ), "week") == "2026-W40"


def test_periods_between_cover_the_range_in_order():
    assert periods_between(_local("2026-09-01"), _local("2026-11-01"), "month", TZ) == [
        "2026-09", "2026-10",
    ]
    assert periods_between(_local("2026-10-26"), _local("2026-11-03"), "week", TZ) == [
        "2026-W44", "2026-W45",
    ]
    assert len(periods_between(_local("2026-10-01"), _local("2026-11-01"), "day", TZ)) == 31
