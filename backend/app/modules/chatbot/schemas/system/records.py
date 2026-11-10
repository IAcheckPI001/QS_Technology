"""Contract RecordQuery của tool `crm_records`: liệt kê bản ghi theo whitelist cột của catalog.

Enum sinh từ catalog (chỉ dataset có `list_columns`); cột nào thuộc dataset nào kiểm tra
trong `reporting/records.py`. Filter và khoảng ngày dùng chung contract với ReportQuery.
"""

from typing import Literal

from pydantic import Field

from app.modules.chatbot.reporting.datasets import DATASETS
from app.modules.chatbot.schemas.default import SystemModel

from .report import MAX_FILTERS, ReportDateRange, ReportFilter, SortDirection

MAX_FIELDS = 8
MAX_RECORDS = 20
MAX_OFFSET = 200
MAX_RECORD_SORT = 2


def _names(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


LIST_DATASET_NAMES = _names(name for name, spec in DATASETS.items() if spec.list_columns)
LIST_COLUMN_NAMES = _names(column for spec in DATASETS.values() for column in spec.list_columns)

ListDatasetName = Literal[LIST_DATASET_NAMES]   # type: ignore[valid-type]
ListColumn = Literal[LIST_COLUMN_NAMES]         # type: ignore[valid-type]


class RecordSort(SystemModel):
    field: ListColumn
    direction: SortDirection


class RecordQuery(SystemModel):
    dataset: ListDatasetName
    fields: list[ListColumn] = Field(
        min_length=1, max_length=MAX_FIELDS, description="Cột cần hiện, theo thứ tự.",
    )
    filters: list[ReportFilter] = Field(
        default_factory=list, max_length=MAX_FILTERS, description="Kết hợp bằng AND.",
    )
    date_range: ReportDateRange | None = None
    sort: list[RecordSort] = Field(
        default_factory=list, max_length=MAX_RECORD_SORT, description="Chỉ theo cột có trong fields.",
    )
    limit: int | None = Field(default=None, ge=1, le=MAX_RECORDS)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET, description="Bỏ qua N dòng đầu (xem tiếp).")
