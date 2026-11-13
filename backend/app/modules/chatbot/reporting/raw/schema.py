"""Schema bảng CRM cho tool truy vấn thô (`crm_schema`, `crm_query`).

Hai nguồn:
- Index tĩnh `schema_index.TABLES`, sinh từ `docs/ai/tool_instruction/database-structure.sql`
  bằng `backend/scripts/build_crm_schema_index.py`: tên bảng (enum cho LLM), kiểu cột gọn,
  khoá ngoại và giá trị hợp lệ lấy từ CHECK/ENUM. Không cần gọi mạng.
- Schema sống `GET /api/v1/reports/tables/{table}` của CRM (cột thật CRM cho dùng, mô tả cột,
  quan hệ hai chiều kèm cardinality/nullable, nghĩa của deleted_at) và mô tả bảng từ
  `GET /api/v1/reports/datasets`, cache trong tiến trình. Schema không phải dữ liệu: cache dùng chung giữa người dùng; quyền
  đọc dữ liệu vẫn do CRM kiểm tra ở `POST /reports/query` theo token.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from app.modules.chatbot.providers.crm_api import CrmApiError, CrmReportClient

from .hints import LookupSpec

logger = logging.getLogger(__name__)

MAX_LOOKUP_VALUES = 60

# Tiền tố kiểu PostgreSQL → kiểu gọn hiển thị cho LLM (thứ tự quan trọng: "character" trước
# "char…", "timestamp" trước "time", "jsonb" trước "json").
_TYPES = (
    ("uuid", "uuid"),
    ("character varying", "text"), ("character", "text"), ("varchar", "text"),
    ("citext", "text"), ("text", "text"),
    ("smallint", "int"), ("integer", "int"), ("bigint", "int"),
    ("numeric", "number"), ("decimal", "number"), ("real", "number"), ("double precision", "number"),
    ("boolean", "bool"),
    ("timestamp", "timestamp"), ("date", "date"), ("time", "time"), ("interval", "text"),
    ("jsonb", "json"), ("json", "json"),
)
DATE_TYPES = frozenset({"timestamp", "date"})


def compact_type(raw: str, enums: Mapping[str, tuple[str, ...]] | None = None) -> str:
    """`character varying(50)` → `text`, `timestamp without time zone` → `timestamp`, `text[]` giữ `[]`.

    Kiểu ENUM của schema public (có trong `enums`) là `text`; kiểu lạ giữ nguyên.
    """
    array = raw.endswith("[]")
    base = raw.removesuffix("[]").strip()
    if base.startswith("public."):
        name = "text" if base.removeprefix("public.") in (enums or {}) else base
    else:
        name = next((short for prefix, short in _TYPES if base.startswith(prefix)), base or "?")
    return f"{name}[]" if array else name


@dataclass(frozen=True)
class TableIndex:
    """Một bảng trong index tĩnh.

    columns: tên cột → kiểu gọn (uuid, text, int, number, bool, timestamp, date, time, json;
    hậu tố `[]` cho mảng). relations: cột khoá ngoại → bảng đích. values: cột → giá trị hợp lệ
    (CHECK `= ANY (ARRAY[...])` hoặc kiểu ENUM).
    """

    columns: Mapping[str, str]
    relations: Mapping[str, str] = field(default_factory=dict)
    values: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveReference:
    table: str                  # bảng con
    column: str                 # cột khoá ngoại của bảng con
    one_to_one: bool = False


@dataclass(frozen=True)
class LiveTable:
    """Schema bảng do CRM trả: cột CRM cho dùng (đã ẩn cột bí mật theo tên) và quan hệ.

    columns: tên cột → kiểu PostgreSQL. relations: khoá ngoại → bảng đích. Phần còn lại là ngữ
    nghĩa CRM mô tả (rỗng khi CRM không trả): mô tả cột, khoá ngoại tuỳ chọn (`nullable`) và
    1-1, bảng con trỏ tới (`referenced_by`), nghĩa của `deleted_at` ("deleted" | "ended").
    """

    columns: Mapping[str, str]
    relations: Mapping[str, str]
    column_descriptions: Mapping[str, str] = field(default_factory=dict)
    optional_relations: frozenset[str] = frozenset()
    one_to_one_relations: frozenset[str] = frozenset()
    referenced_by: tuple[LiveReference, ...] = ()
    deleted_at_meaning: str = ""


def _lookup_line(row: Mapping[str, object], columns: tuple[str, ...]) -> str:
    """"sales = Sales User"; nhãn rỗng hoặc trùng giá trị thì bỏ."""
    value = str(row.get(columns[0]) or "").strip()
    labels = []
    for column in columns[1:]:
        label = str(row.get(column) or "").strip()
        if label and label != value and label not in labels:
            labels.append(label)
    return f"{value} = {' | '.join(labels)}" if labels else value


class CrmSchemaCache:
    """Cache `GET /reports/tables/{table}` theo bảng và mô tả bảng (`GET /reports/datasets`),
    hết hạn sau `ttl_s` giây.

    Lỗi CRM (401/403/không phản hồi) không được cache: lần sau gọi lại. Mô tả bảng là phần phụ:
    lỗi khi lấy mô tả không làm hỏng tool, chỉ trả mô tả rỗng.
    """

    def __init__(
        self,
        client: CrmReportClient,
        *,
        ttl_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._ttl_s = ttl_s
        self._clock = clock
        self._tables: dict[str, tuple[float, LiveTable]] = {}
        self._descriptions: tuple[float, Mapping[str, str]] | None = None
        self._lookups: dict[str, tuple[float, tuple[str, ...]]] = {}

    def cached(self, table: str) -> LiveTable | None:
        entry = self._tables.get(table)
        if entry is None or self._clock() - entry[0] > self._ttl_s:
            return None
        return entry[1]

    async def table(self, table: str, token: str) -> LiveTable:
        live = self.cached(table)
        if live is not None:
            return live
        payload = await self._client.get_table(table, token)
        live = LiveTable(
            columns={item.name: item.type for item in payload.columns},
            relations={item.name: item.table for item in payload.relations},
            column_descriptions={item.name: item.description for item in payload.columns if item.description},
            optional_relations=frozenset(item.name for item in payload.relations if item.nullable),
            one_to_one_relations=frozenset(item.name for item in payload.relations if item.one_to_one),
            referenced_by=tuple(
                LiveReference(item.table, item.column, item.one_to_one) for item in payload.referenced_by
            ),
            deleted_at_meaning=payload.deleted_at_meaning,
        )
        self._tables[table] = (self._clock(), live)
        return live

    async def lookup(self, table: str, spec: LookupSpec, token: str) -> tuple[str, ...] | None:
        """Giá trị hiện có của bảng tra cứu, mỗi dòng "giá_trị = nhãn | nhãn"; lỗi CRM → None.

        Là dữ liệu (không phải schema) nhưng ít đổi và không riêng tư (tên vai trò, trạng thái),
        nên cache chung cùng TTL. Token không đủ quyền (403) → None, không cache: lần sau gọi lại.
        """
        entry = self._lookups.get(table)
        if entry is not None and self._clock() - entry[0] <= self._ttl_s:
            return entry[1]
        request: dict[str, object] = {
            "dataset": table, "select": list(spec.columns),
            "order_by": [{"field": spec.columns[0], "dir": "asc"}], "limit": MAX_LOOKUP_VALUES + 1,
        }
        if spec.filters:
            request["filters"] = [dict(item) for item in spec.filters]
        try:
            page = await self._client.query(request, token)
        except CrmApiError as error:
            logger.warning("crm lookup unavailable table=%s code=%s", table, error.code)
            return None
        values = tuple(_lookup_line(row, spec.columns) for row in page.rows[:MAX_LOOKUP_VALUES])
        if len(page.rows) > MAX_LOOKUP_VALUES:
            values = (*values, f"... (còn nữa, lọc contains trên {spec.columns[0]})")
        self._lookups[table] = (self._clock(), values)
        return values

    async def descriptions(self, token: str) -> Mapping[str, str]:
        """Tên bảng → mô tả của CRM; lỗi CRM → rỗng (không cache)."""
        if self._descriptions is not None and self._clock() - self._descriptions[0] <= self._ttl_s:
            return self._descriptions[1]
        try:
            descriptions = await self._client.get_table_descriptions(token)
        except CrmApiError as error:
            logger.warning("crm table descriptions unavailable code=%s", error.code)
            return {}
        self._descriptions = (self._clock(), descriptions)
        return descriptions

    async def tables(self, names: list[str], token: str) -> dict[str, LiveTable]:
        """Nhiều bảng song song; lỗi CRM đầu tiên được ném ra (CrmApiError)."""
        results = await asyncio.gather(*(self.table(name, token) for name in names))
        return dict(zip(names, results, strict=True))
