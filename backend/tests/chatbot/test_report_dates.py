from datetime import UTC, datetime

import pytest

from app.modules.chatbot.reporting.dates import preset_range
from tests.chatbot.crm_fakes import NOW, TZ


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
