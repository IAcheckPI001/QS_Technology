"""Tool `crm_schema`: cột, quan hệ và ghi chú nghiệp vụ của tối đa 4 bảng CRM trong một call.

Gộp `GET /reports/tables/{table}` của nhiều bảng để agent dựng `crm_query` mà không đoán tên
cột. Không có tool liệt kê bảng: danh sách bảng theo nhóm nằm sẵn trong description (payload
`/reports/datasets` thật khoảng 27k token; tool chỉ lấy mô tả bảng từ đó). Cột bị chặn
(`reporting/raw/policy.py`) không được trả về; kiểu cột gọn và giá trị hợp lệ (CHECK/ENUM) lấy
từ index tĩnh; mô tả cột/bảng, quan hệ tuỳ chọn/1-1, bảng con và nghĩa của deleted_at lấy từ
schema sống của CRM.
"""

import asyncio
import logging
from collections.abc import Mapping

from pydantic import Field

from app.core.tracing import current_span
from app.modules.chatbot.providers.crm_api import CrmApiError
from app.modules.chatbot.reporting.raw.hints import LOOKUP_TABLES, TABLE_GROUPS, TABLE_NOTES
from app.modules.chatbot.reporting.raw.policy import QUERYABLE_TABLES, column_blocked, table_blocked
from app.modules.chatbot.reporting.raw.schema import (
    DATE_TYPES,
    CrmSchemaCache,
    LiveTable,
    compact_type,
)
from app.modules.chatbot.reporting.raw.schema_index import TABLES
from app.modules.chatbot.schemas.default import SystemModel
from app.modules.chatbot.schemas.system.raw_query import SchemaRequest

from .base import ToolContext, ToolOutput, ToolRejected, ToolSpec
from .crm_report import crm_credential

CRM_SCHEMA_TOOL_NAME = "crm_schema"

logger = logging.getLogger(__name__)

CRM_SCHEMA_DESCRIPTION = (
    "Xem mô tả bảng, cột (tên:kiểu, giá trị hợp lệ nếu có, — nghĩa), quan hệ khoá ngoại "
    "(fk->bảng; '(có thể trống)' = khoá ngoại tuỳ chọn: join giữ dòng, cột của bảng đích để trống; "
    "'(1-1)'), bảng con trỏ tới (referenced_by), known_values (giá trị thật hiện có của vai trò, "
    "trạng thái, nhóm...: so từ trong câu hỏi với nhãn rồi lọc bằng giá trị trước dấu =) và ghi chú "
    "nghiệp vụ "
    "của tối đa 4 bảng CRM/ERP trong MỘT call, trước khi dựng crm_query. Gọi cho bảng gốc và các "
    "bảng đích của join cần dùng."
)


PEOPLE_TABLE = "auth_users"
MAX_REFERENCED_BY = 12
# Cột hiển nhiên: bỏ mô tả để tiết kiệm token.
PLAIN_COLUMNS = frozenset({"id", "created_at", "updated_at"})
MAX_COLUMN_NOTE_CHARS = 160
DELETED_AT_NOTES: Mapping[str, str] = {
    "deleted": "CRM đã tự loại dòng xoá mềm (deleted_at khác null): không cần lọc deleted_at.",
    "ended": (
        "deleted_at là lúc KẾT THÚC (thu hồi, thay, thả), không phải xoá; CRM không lọc. Trạng thái "
        "hiện tại: filter deleted_at is_null; lịch sử hoặc số phát sinh trong kỳ: không lọc."
    ),
}


class TableDescription(SystemModel):
    table: str
    description: str | None = None      # mô tả bảng của CRM
    columns: list[str]                  # "tên:kiểu", "tên:kiểu=a|b|c", kèm " — nghĩa" nếu có
    date_columns: list[str]
    relations: list[str]                # "fk->bảng đích", kèm "(1-1)", "(có thể trống)"
    # "bảng_con.cột": bảng con trỏ tới bảng này. Join chỉ đi con → cha, nên muốn dùng thông tin
    # ở bảng con thì phải lấy bảng con làm dataset (vd họ tên ở user_profiles, không ở auth_users).
    referenced_by: list[str] = Field(default_factory=list)
    hidden_columns: list[str] = Field(default_factory=list)   # khoá/bí mật: không truy vấn được
    # Đường dẫn cột → giá trị hiện có của bảng tra cứu do admin tạo ("giá_trị = nhãn"), vd
    # user_roles: {"role_id.code": ["sales = Sales User", ...]}.
    known_values: dict[str, list[str]] = Field(default_factory=dict)
    deleted_at: str | None = None       # cách hiểu cột deleted_at của bảng
    person_filter: str | None = None    # cách lọc các cột trỏ tới auth_users theo người
    note: str | None = None


def _child_rank(table: str) -> tuple[int, int]:
    """Bảng con ít khoá ngoại rồi ít cột trước, để bảng hồ sơ (user_profiles) và bảng nối
    (user_roles) đứng đầu, bảng nghiệp vụ lớn chỉ ghi "người tạo" đứng cuối và bị cắt."""
    index = TABLES.get(table)
    return (len(index.relations), len(index.columns)) if index is not None else (99, 999)


def _referenced_by() -> dict[str, list[str]]:
    """Bảng đích → ["bảng_con.cột"] theo index tĩnh (dùng khi CRM không trả referenced_by)."""
    reverse: dict[str, list[tuple[int, int, str]]] = {}
    for name in QUERYABLE_TABLES:
        for column, target in TABLES[name].relations.items():
            if name != target and not column_blocked(name, column):
                reverse.setdefault(target, []).append((*_child_rank(name), f"{name}.{column}"))
    return {target: [item for *_, item in sorted(items)] for target, items in reverse.items()}


REFERENCED_BY: Mapping[str, list[str]] = _referenced_by()
_QUERYABLE = frozenset(QUERYABLE_TABLES)


def _live_referenced_by(name: str, live: LiveTable) -> list[str]:
    items = [
        (*_child_rank(item.table), f"{item.table}.{item.column}" + (" (1-1)" if item.one_to_one else ""))
        for item in live.referenced_by
        if item.table != name and item.table in _QUERYABLE and not column_blocked(item.table, item.column)
    ]
    return [item for *_, item in sorted(items)]


def _column_note(column: str, live: LiveTable) -> str:
    if column in PLAIN_COLUMNS:
        return ""
    note = " ".join(live.column_descriptions.get(column, "").split())
    if len(note) > MAX_COLUMN_NOTE_CHARS:
        note = note[:MAX_COLUMN_NOTE_CHARS - 1].rstrip() + "…"
    return f" — {note}" if note else ""


def _person_filter(columns: list[str]) -> str:
    listed = ", ".join(columns)
    return (
        f"{listed}: UUID tài khoản, chỉ nhận chuỗi UUID thật. Lọc theo username: thêm .username vào "
        "cột, op contains. Lọc theo TÊN người: gọi crm_query user_profiles (first_name contains) "
        "TRƯỚC, đọc user_id trả về, rồi mới lọc cột này bằng UUID đó."
    )


class SchemaOutput(ToolOutput):
    tables: list[TableDescription] = Field(default_factory=list)


def tables_text() -> str:
    return "\n".join(f"- {group}: {', '.join(tables)}" for group, tables in TABLE_GROUPS.items())


LOOKUP_UNAVAILABLE = "(không lấy được danh sách: chạy crm_query aggregate dimensions=[cột này] để xem)"


def lookup_paths(name: str, live: LiveTable) -> dict[str, str]:
    """Đường dẫn cột → bảng tra cứu: chính bảng đó, hoặc khoá ngoại trỏ tới bảng tra cứu."""
    paths: dict[str, str] = {}
    if name in LOOKUP_TABLES:
        paths[LOOKUP_TABLES[name].columns[0]] = name
    for column, target in live.relations.items():
        if target in LOOKUP_TABLES and target != name and not column_blocked(name, column):
            paths[f"{column}.{LOOKUP_TABLES[target].columns[0]}"] = target
    return paths


def describe_table(
    name: str,
    live: LiveTable,
    description: str | None = None,
    lookups: Mapping[str, tuple[str, ...] | None] | None = None,
) -> TableDescription:
    """lookups: bảng tra cứu → giá trị (None = CRM không trả được); bảng không có trong lookups bị bỏ."""
    index = TABLES.get(name)
    static_columns: Mapping[str, str] = index.columns if index is not None else {}
    values: Mapping[str, tuple[str, ...]] = index.values if index is not None else {}
    columns: list[str] = []
    dates: list[str] = []
    hidden: list[str] = []
    for column, live_type in live.columns.items():
        if column_blocked(name, column):
            hidden.append(column)
            continue
        kind = static_columns.get(column) or compact_type(live_type)
        allowed = values.get(column)
        columns.append(
            f"{column}:{kind}" + (f"={'|'.join(allowed)}" if allowed else "") + _column_note(column, live)
        )
        if kind in DATE_TYPES:
            dates.append(column)
    relations = [
        f"{column}->{target}"
        + (" (1-1)" if column in live.one_to_one_relations else "")
        + (" (có thể trống)" if column in live.optional_relations else "")
        for column, target in live.relations.items()
        if not column_blocked(name, column) and not table_blocked(target)
    ]
    people = [
        column for column, target in live.relations.items()
        if target == PEOPLE_TABLE and not column_blocked(name, column)
    ]
    children = _live_referenced_by(name, live) if live.referenced_by else REFERENCED_BY.get(name, [])
    referenced_by = children[:MAX_REFERENCED_BY]
    if len(children) > MAX_REFERENCED_BY:
        referenced_by.append(f"... (+{len(children) - MAX_REFERENCED_BY} bảng.cột khác)")
    known_values: dict[str, list[str]] = {}
    for path, table in lookup_paths(name, live).items():
        if lookups is not None and table in lookups:
            values = lookups[table]
            known_values[path] = list(values) if values is not None else [LOOKUP_UNAVAILABLE]
    return TableDescription(
        table=name, description=description or None, columns=columns, date_columns=dates,
        relations=relations, referenced_by=referenced_by, hidden_columns=hidden,
        known_values=known_values,
        deleted_at=DELETED_AT_NOTES.get(live.deleted_at_meaning) if "deleted_at" in live.columns else None,
        person_filter=_person_filter(people) if people else None,
        note=TABLE_NOTES.get(name),
    )


def build_crm_schema_tool(cache: CrmSchemaCache, *, timeout_s: float = 20.0) -> ToolSpec:
    async def run(arguments: SchemaRequest, context: ToolContext) -> SchemaOutput:
        token, credential = crm_credential(context.parent_state.principal)
        tables = list(dict.fromkeys(arguments.tables))
        current_span().set(credential_source=credential, tables=tables)
        if not token:
            logger.warning("crm_schema rejected: no acting user")
            raise ToolRejected("crm_user_missing", "no CRM user is attached to this conversation")
        current_span().set(cache_hits=[name for name in tables if cache.cached(name) is not None])
        try:
            live, descriptions = await asyncio.gather(cache.tables(tables, token), cache.descriptions(token))
        except CrmApiError as error:
            logger.warning("crm_schema fetch failed code=%s detail=%s", error.code, error.detail)
            raise ToolRejected(error.code, error.detail) from None
        needed = sorted({target for name in tables for target in lookup_paths(name, live[name]).values()})
        values = await asyncio.gather(
            *(cache.lookup(target, LOOKUP_TABLES[target], token) for target in needed)
        )
        lookups = dict(zip(needed, values, strict=True))
        current_span().set(lookups=needed)
        logger.info("crm_schema done credential=%s tables=%s", credential, ",".join(tables))
        return SchemaOutput(
            tables=[describe_table(name, live[name], descriptions.get(name), lookups) for name in tables],
        )

    return ToolSpec(
        name=CRM_SCHEMA_TOOL_NAME,
        description=f"{CRM_SCHEMA_DESCRIPTION}\nBảng theo nhóm:\n{tables_text()}",
        input_model=SchemaRequest,
        output_model=SchemaOutput,
        run=run,
        read_only=True,
        concurrency_safe=True,
        max_calls_per_turn=2,
        timeout_s=timeout_s,
    )


__all__ = ["CRM_SCHEMA_TOOL_NAME", "SchemaOutput", "build_crm_schema_tool", "describe_table"]
