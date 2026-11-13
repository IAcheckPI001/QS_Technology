"""Bảng/cột LLM không được đọc hay lọc qua `crm_query`, kể cả khi CRM cho phép.

CRM tự ẩn các bảng phiên/token (sessions, sso_tickets, ...) và cột có tên chứa password,
token, secret, hash, api_key, otp. Dịch vụ AI chặn thêm khoá và bí mật CRM vẫn để lộ
(quyết định 2026-11-10: mở mọi dữ liệu nghiệp vụ, kể cả liên hệ và chat; chặn khoá/bí mật):
- `app_settings`: cấu hình hệ thống (key/value).
- `keygen_history`: input/output sinh khoá kích hoạt máy.
- Khoá mở máy và dữ liệu đầu vào sinh khoá (`unlock_key`, `device_input`, `inputs`/`result`
  của yêu cầu kích hoạt), khoá lưu trữ file, checksum firmware.
Ngoài ra không dùng bảng CRM không còn trả (`NOT_EXPOSED_TABLES`) và bảng của module CRM
chưa triển khai (`UNRELEASED_TABLES`, quyết định 2026-11-12).
Chặn áp lên dataset, mọi đoạn join và cột cuối của mọi đường dẫn (select, dimensions,
metrics, filters, date_range, order_by).
"""

import re
from collections.abc import Callable

from .schema_index import TABLES

BLOCKED_TABLES: frozenset[str] = frozenset({
    "app_settings",
    "keygen_history",
    # CRM đã ẩn khỏi Reporting API; chặn cả ở đây để không phụ thuộc cấu hình CRM.
    "password_reset_tokens",
    "push_device_tokens",
    "schema_migrations",
    "sessions",
    "sso_tickets",
    "verification_codes",
})
# Có trong SQL dump (index tĩnh) nhưng CRM không còn trả qua Reporting API (kiểm 2026-11-12).
NOT_EXPOSED_TABLES: frozenset[str] = frozenset({"sales_users", "user_types"})
# Bảng của module CRM mới khởi tạo, chưa triển khai (Toma, 2026-11-12): không dùng tới khi
# module được đưa vào sử dụng, kể cả khi CRM trả qua schema sống hoặc join tới.
UNRELEASED_TABLES: frozenset[str] = frozenset({
    "goods_inspection_items",
    "goods_inspections",
    "issue_types",
    "item_categories",
    "material_request_items",
    "material_requests",
    "material_uoms",
    "receipt_types",
})
UNAVAILABLE_TABLES: frozenset[str] = BLOCKED_TABLES | NOT_EXPOSED_TABLES | UNRELEASED_TABLES
BLOCKED_COLUMNS: dict[str, frozenset[str]] = {
    "lock_requests": frozenset({"unlock_key", "device_input"}),
    "product_items": frozenset({"device_input"}),
    "product_item_activation_requests": frozenset({"inputs", "result"}),
    "files": frozenset({"storage_key"}),
    "iot_firmwares": frozenset({"sha256"}),
}
# Phòng khi CRM thêm cột bí mật mới: chặn theo tên như CRM (thêm credential).
SECRET_NAME = re.compile(r"password|token|secret|hash|api_key|otp|credential")
_PERIOD_SUFFIX = re.compile(r"_(day|month|year)$")

QUERYABLE_TABLES: tuple[str, ...] = tuple(sorted(name for name in TABLES if name not in UNAVAILABLE_TABLES))

RelationTarget = Callable[[str, str], str | None]
# Kiểu gọn của cột (uuid, text, int, number, bool, timestamp, date, ...); None = không biết.
ColumnType = Callable[[str, str], str | None]
DATE_KINDS = frozenset({"timestamp", "date"})
DATE_PART = "date_part"     # cột ảo chia kỳ của cột ngày (created_at_month, ...)


class PathError(ValueError):
    """Đường dẫn cột không dùng được; message gửi lại cho LLM."""


def table_blocked(table: str) -> bool:
    return table in UNAVAILABLE_TABLES


def column_blocked(table: str, column: str) -> bool:
    """Cột bị chặn; `created_at_month` xét theo cột gốc `created_at`."""
    if table_blocked(table):
        return True
    names = {column, _PERIOD_SUFFIX.sub("", column)}
    blocked = BLOCKED_COLUMNS.get(table, frozenset())
    return any(name in blocked or SECRET_NAME.search(name) for name in names)


def static_relation(table: str, column: str) -> str | None:
    index = TABLES.get(table)
    return index.relations.get(column) if index is not None else None


def static_column_type(table: str, column: str) -> str | None:
    index = TABLES.get(table)
    return index.columns.get(column) if index is not None else None


def static_values(table: str, column: str) -> tuple[str, ...]:
    """Giá trị hợp lệ (CHECK/ENUM) theo index tĩnh; rỗng = không biết."""
    index = TABLES.get(table)
    return index.values.get(column, ()) if index is not None else ()


def column_kind(table: str, column: str, column_type: ColumnType = static_column_type) -> str | None:
    """Kiểu gọn của cột; cột ảo `<cột ngày>_day/_month/_year` là DATE_PART; None = không biết."""
    kind = column_type(table, column)
    if kind is not None:
        return kind
    base = _PERIOD_SUFFIX.sub("", column)
    if base != column and column_type(table, base) in DATE_KINDS:
        return DATE_PART
    return None


def check_path(dataset: str, path: str, relation_target: RelationTarget = static_relation) -> str:
    """Đi theo các đoạn khoá ngoại của `path` từ `dataset`; trả bảng chứa cột cuối.

    Raise PathError nếu gặp bảng/cột bị chặn hoặc khoá ngoại không biết bảng đích.
    """
    segments = path.split(".")
    table = dataset
    for position, foreign_key in enumerate(segments[:-1]):
        if column_blocked(table, foreign_key):
            raise PathError(f"{path}: {table}.{foreign_key} is not available")
        target = relation_target(table, foreign_key)
        if target is None:
            raise PathError(
                f"{path}: {table} has no relation {foreign_key}; check relations with crm_schema"
                + _table_name_hint(table, foreign_key, segments[position + 1:])
            )
        if table_blocked(target):
            raise PathError(f"{path}: table {target} is not available")
        table = target
    if column_blocked(table, segments[-1]):
        raise PathError(f"{path}: {table}.{segments[-1]} is not available")
    return table


def _table_name_hint(table: str, name: str, rest: list[str]) -> str:
    """LLM viết tên bảng thay tên khoá ngoại (`support_cases.x` thay `case_id.x`, eval 2026-11-12):
    gợi ý khoá ngoại trỏ tới bảng đó theo index tĩnh."""
    index = TABLES.get(table)
    via = [column for column, target in index.relations.items() if target == name] if index else []
    if not via:
        return ""
    return f" ({name} is a table: join through {' or '.join(via)}, e.g. {'.'.join([via[0], *rest])})"
