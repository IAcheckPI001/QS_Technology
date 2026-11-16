from datetime import datetime

import pytest

from app.modules.chatbot.reporting.raw.render import DEFAULT_MAX_TEXT_CHARS, api_column, render_value
from tests.chatbot.crm_fakes import TZ


def test_api_column_follows_crm_response_naming():
    assert api_column("count_distinct:case_id.product_item_id.customer_id") == (
        "count_distinct_case_id__product_item_id__customer_id"
    )


def test_strings_are_sanitized_and_cut():
    value = render_value("Công ty\x00\x07 " + "X" * 300, TZ)

    assert "\x00" not in value and "\x07" not in value
    assert len(value) == DEFAULT_MAX_TEXT_CHARS and value.endswith("…")
    assert render_value("", TZ) is None and render_value(True, TZ) is True


@pytest.mark.parametrize(("value", "expected"), [
    # CRM lưu UTC: chuỗi không kèm múi giờ (cột timestamp) là UTC.
    ("2026-10-31 17:30:00.123456", "2026-11-01T00:30+07:00"),
    ("2026-10-01 02:00:00.5+00", "2026-10-01T09:00+07:00"),           # timestamptz
    ("2026-10-01T02:00:00.123456789Z", "2026-10-01T09:00+07:00"),
    ("2026-10-01T09:00:00+07:00", "2026-10-01T09:00+07:00"),
    (datetime(2026, 10, 1, 2, 0), "2026-10-01T09:00+07:00"),           # datetime không múi giờ
    ("2026-10-01", "2026-10-01"),                                      # cột date, kỳ _day: giữ
    ("2026-10", "2026-10"),
    ("Lắp đặt 2026-10-01 02:00", "Lắp đặt 2026-10-01 02:00"),          # chữ có ngày: giữ
])
def test_timestamps_are_shown_in_local_time(value, expected):
    assert render_value(value, TZ) == expected
