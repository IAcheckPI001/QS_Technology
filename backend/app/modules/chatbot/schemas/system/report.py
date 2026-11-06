"""Contract ReportQuery: LLM chỉ chọn tên logic đã đăng ký trong catalog báo cáo.

Enum sinh từ catalog (hợp của mọi dataset); ràng buộc theo từng dataset (trường nào
thuộc dataset nào, operator hợp kiểu, giá trị enum) kiểm tra trong
`reporting/validate.py`, lỗi trả lại cho LLM tự sửa. v1 chỉ có truy vấn tổng hợp
(aggregate): chưa có danh sách/chi tiết bản ghi.
"""

from datetime import date
from typing import Literal

from pydantic import Field

from app.modules.chatbot.reporting.datasets import DATASETS
from app.modules.chatbot.schemas.default import SystemModel

MAX_METRICS = 3
MAX_DIMENSIONS = 2
MAX_FILTERS = 8
MAX_SORT = 3
MAX_LIMIT = 50

DATE_PRESETS = (
    "today", "yesterday", "this_week", "last_week", "this_month", "last_month",
    "last_7_days", "last_30_days", "this_quarter", "last_quarter", "this_year", "last_year",
)
PERIOD = "period"


def _names(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


DATASET_NAMES = _names(DATASETS)
METRIC_NAMES = _names(m for spec in DATASETS.values() for m in spec.metrics)
FILTER_FIELDS = _names(f for spec in DATASETS.values() for f in spec.filter_fields())
DIMENSION_NAMES = _names(d for spec in DATASETS.values() for d in spec.dimensions())
DATE_FIELDS = _names(f for spec in DATASETS.values() for f in spec.date_fields)

DatasetName = Literal[DATASET_NAMES]            # type: ignore[valid-type]
MetricName = Literal[METRIC_NAMES]              # type: ignore[valid-type]
FilterField = Literal[FILTER_FIELDS]            # type: ignore[valid-type]
DimensionName = Literal[DIMENSION_NAMES]        # type: ignore[valid-type]
DateField = Literal[DATE_FIELDS]                # type: ignore[valid-type]
SortField = Literal[_names((*METRIC_NAMES, *DIMENSION_NAMES, PERIOD))]  # type: ignore[valid-type]
DatePreset = Literal[DATE_PRESETS]              # type: ignore[valid-type]
FilterOperator = Literal["eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte"]
TimeGrain = Literal["day", "week", "month"]
SortDirection = Literal["asc", "desc"]


class ReportFilter(SystemModel):
    field: FilterField
    operator: FilterOperator
    value: bool | float | str | list[str] = Field(
        description="in/not_in: danh sách; bool: true/false; number: số.",
    )


class ReportDateRange(SystemModel):
    field: DateField
    preset: DatePreset | None = Field(
        default=None, description="Khoảng tương đối theo giờ Việt Nam; dùng preset HOẶC start/end.",
    )
    start: date | None = Field(default=None, description="Ngày bắt đầu (bao gồm), YYYY-MM-DD.")
    end: date | None = Field(default=None, description="Ngày kết thúc (KHÔNG bao gồm), YYYY-MM-DD.")


class ReportSort(SystemModel):
    field: SortField
    direction: SortDirection


class ReportQuery(SystemModel):
    dataset: DatasetName
    metrics: list[MetricName] = Field(min_length=1, max_length=MAX_METRICS)
    dimensions: list[DimensionName] = Field(default_factory=list, max_length=MAX_DIMENSIONS)
    filters: list[ReportFilter] = Field(
        default_factory=list, max_length=MAX_FILTERS, description="Kết hợp bằng AND.",
    )
    date_range: ReportDateRange | None = None
    time_grain: TimeGrain | None = Field(
        default=None, description="Chia theo kỳ; cần date_range. Kết quả có delta so với kỳ trước.",
    )
    sort: list[ReportSort] = Field(default_factory=list, max_length=MAX_SORT)
    limit: int | None = Field(default=None, ge=1, le=MAX_LIMIT)
