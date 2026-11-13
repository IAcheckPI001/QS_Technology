"""Contract của tool `crm_schema` và `crm_query`: query CRM Reporting API do LLM tự dựng.

Mirror `POST /api/v1/reports/query` của CRM (docs/ai/tool_instruction/ai-reporting-query.md),
khác vài chỗ để LLM ít sai (OpenAI strict bắt điền mọi field nên field "không dùng" hay bị
điền bừa):
- `mode` bắt buộc chọn `list` (dùng `select`) hoặc `aggregate` (dùng `dimensions`/`metrics`);
  field của chế độ kia bị bỏ qua thay vì làm hỏng query.
- `date_range.preset` bắt buộc: khoảng tương đối, kỳ lịch `month`/`year` (dịch vụ AI tự tính
  ngày, LLM không phải đoán năm) hoặc `custom`; `from_date`/`to_date` (thay `from`/`to`) chỉ dùng
  khi `custom`.
- `limit` có trần nhỏ hơn vì kết quả đi vào context của LLM.
Tên bảng kiểm trong code theo `QUERYABLE_TABLES` (index tĩnh đã trừ bảng bị chặn), không đặt
enum trong JSON schema; cột và đường dẫn join chỉ kiểm tra hình dạng ở đây, tồn tại hay không
do CRM trả lời.
"""

from datetime import date
from difflib import get_close_matches
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from app.modules.chatbot.reporting.raw.policy import QUERYABLE_TABLES
from app.modules.chatbot.schemas.default import SystemModel

from .report import DATE_PRESETS

CUSTOM_RANGE = "custom"
MONTH_RANGE = "month"
YEAR_RANGE = "year"
RangePreset = Literal[(*DATE_PRESETS, MONTH_RANGE, YEAR_RANGE, CUSTOM_RANGE)]     # type: ignore[valid-type]
QueryMode = Literal["list", "aggregate"]

MAX_SCHEMA_TABLES = 4
MAX_SELECT = 12
MAX_DIMENSIONS = 3
MAX_METRICS = 4
MAX_RAW_FILTERS = 20
MAX_ORDER = 3
MAX_QUERY_LIMIT = 100
MAX_QUERY_OFFSET = 1000
MAX_IN_VALUES = 100

_NAME = r"[a-z_][a-z0-9_]*"
# Cột hoặc `fk.fk.cột`: tối đa 4 bước join (giới hạn của CRM).
PATH_PATTERN = rf"^{_NAME}(\.{_NAME}){{0,4}}$"
METRIC_PATTERN = rf"^(count|(count|count_distinct|sum|avg|min|max):{_NAME}(\.{_NAME}){{0,4}})$"
ORDER_PATTERN = rf"^((count|count_distinct|sum|avg|min|max):)?{_NAME}(\.{_NAME}){{0,4}}$"

_QUERYABLE = frozenset(QUERYABLE_TABLES)


def _queryable_table(name: str) -> str:
    """Tên bảng kiểm trong code thay vì enum trong JSON schema: enum 116 tên lặp ở hai tool tốn
    khoảng 1k token mỗi bước LLM, mà danh sách nhóm bảng đã có trong description `crm_schema`."""
    if name in _QUERYABLE:
        return name
    close = get_close_matches(name, QUERYABLE_TABLES, n=3, cutoff=0.6)
    hint = f"; did you mean {', '.join(close)}?" if close else "; pick a table from the crm_schema description"
    raise ValueError(f"table {name} does not exist or is not available{hint}")


TableName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=64, pattern=rf"^{_NAME}$"),
    AfterValidator(_queryable_table),
]
FieldPath = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160, pattern=PATH_PATTERN)]
MetricName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=180, pattern=METRIC_PATTERN)]
OrderField = Annotated[str, StringConstraints(strip_whitespace=True, max_length=180, pattern=ORDER_PATTERN)]
FilterOp = Literal["eq", "neq", "contains", "in", "not_in", "is_null", "not_null"]
FilterValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SchemaRequest(SystemModel):
    tables: list[TableName] = Field(
        min_length=1, max_length=MAX_SCHEMA_TABLES,
        description="Các bảng cần xem cột và quan hệ (bảng gốc và bảng đích của join).",
    )


class RawFilter(SystemModel):
    field: FieldPath = Field(description="Cột hoặc đường dẫn join fk.cột.")
    op: FilterOp
    value: FilterValue | list[FilterValue] | None = Field(
        description=(
            "eq/neq/contains: một chuỗi; in/not_in: mảng chuỗi; is_null/not_null: null. "
            "Số, ngày, UUID, true/false cũng viết dạng chuỗi. Cột uuid chỉ nhận UUID, không nhận "
            "tên người hay mã."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _null_checks_take_no_value(cls, data: Any) -> Any:
        """is_null/not_null bỏ qua value: "" hay giá trị bất kỳ không làm hỏng lần gọi (eval 2026-11-12)."""
        if isinstance(data, dict) and data.get("op") in ("is_null", "not_null"):
            return {**data, "value": None}
        return data


class RawDateRange(SystemModel):
    field: FieldPath = Field(description="Cột ngày (hoặc đường dẫn join tới cột ngày).")
    preset: RangePreset = Field(
        description=(
            "Khoảng tương đối theo giờ Việt Nam (today, this_month, last_month, this_year...); "
            "'tháng N' → month (+ month, year); 'năm YYYY' → year (+ year); khoảng ngày tuỳ ý → "
            "custom + from_date/to_date."
        ),
    )
    month: int | None = Field(
        default=None, ge=1, le=12,
        description="Chỉ khi preset=month: tháng 1-12. year=null: tháng đó gần nhất tính tới hôm nay.",
    )
    year: int | None = Field(
        default=None, ge=2000, le=2100,
        description=(
            "Chỉ điền khi câu hỏi nêu năm. preset=month: năm của tháng (null = gần nhất); "
            "preset=year: năm (null = năm nay). Năm không có trong câu hỏi bị bỏ."
        ),
    )
    from_date: date | None = Field(default=None, description="Chỉ khi preset=custom: ngày đầu (bao gồm).")
    to_date: date | None = Field(
        default=None, description="Chỉ khi preset=custom: ngày cuối (bao gồm); null = hôm nay.",
    )


class RawOrder(SystemModel):
    field: OrderField = Field(description="Tên gốc đã có trong select (list) hoặc dimensions/metrics (aggregate).")
    dir: Literal["asc", "desc"]


class RawQuery(SystemModel):
    dataset: TableName = Field(description="Bảng gốc.")
    mode: QueryMode = Field(
        description=(
            "list: danh sách bản ghi, chỉ dùng select. aggregate: con số/thống kê, chỉ dùng "
            "metrics (+ dimensions để chia nhóm). Field của chế độ kia bị bỏ qua: để []."
        ),
    )
    select: list[FieldPath] = Field(
        default_factory=list, max_length=MAX_SELECT,
        description="mode=list: cột cần hiện.",
    )
    dimensions: list[FieldPath] = Field(
        default_factory=list, max_length=MAX_DIMENSIONS,
        description="mode=aggregate: nhóm theo cột; cột ngày thêm _day/_month/_year để nhóm theo kỳ.",
    )
    metrics: list[MetricName] = Field(
        default_factory=list, max_length=MAX_METRICS,
        description="mode=aggregate: count, count_distinct:<cột>, count:<cột>, sum/avg/min/max:<cột số>.",
    )
    filters: list[RawFilter] = Field(default_factory=list, max_length=MAX_RAW_FILTERS, description="AND.")
    date_range: RawDateRange | None = Field(
        default=None,
        description=(
            "null khi câu hỏi không nêu kỳ thời gian ('hiện tại', 'đang có', 'tới giờ' không phải kỳ)."
        ),
    )
    include_inactive: bool = Field(
        default=False,
        description=(
            "true CHỈ khi câu hỏi nói rõ tính cả phần bị loại mặc định: người/tài khoản đã nghỉ "
            "(user_roles), khách spam (customers). false: giữ điều kiện mặc định."
        ),
    )
    order_by: list[RawOrder] = Field(default_factory=list, max_length=MAX_ORDER)
    limit: int | None = Field(
        default=None, ge=1, le=MAX_QUERY_LIMIT,
        description="Danh sách: mặc định 20, tối đa 50. Thống kê: mặc định 50, tối đa 100.",
    )
    offset: int = Field(default=0, ge=0, le=MAX_QUERY_OFFSET, description="Bỏ qua N dòng đầu (xem tiếp).")
