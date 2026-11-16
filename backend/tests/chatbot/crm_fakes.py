"""Mốc thời gian dùng chung cho test truy vấn CRM."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
# Thứ Hai 02/11/2026, 10:00 giờ Việt Nam.
NOW = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)
