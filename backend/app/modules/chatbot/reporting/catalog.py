"""Catalog báo cáo: mô tả dataset bằng dữ liệu để engine không biết gì về từng nguồn.

Một dataset khai báo record (trường giữ lại từ API, trường nhạy cảm bị bỏ ngay khi
parse), trường lọc/nhóm, metric và trường ngày. Thêm dataset mới (vd customers) là
thêm một DatasetSpec, không sửa contract, validate hay engine.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

FieldType = Literal["enum", "string", "bool", "number"]
Aggregation = Literal["count", "count_distinct", "avg", "max", "sum"]

# Getter nhận record và mốc `now` cố định của request (trường dẫn xuất như tuổi ticket).
Getter = Callable[[Any, datetime], Any]

OPERATORS_BY_TYPE: dict[FieldType, tuple[str, ...]] = {
    "enum": ("eq", "ne", "in", "not_in"),
    "string": ("eq", "ne", "in", "not_in"),
    "bool": ("eq", "ne"),
    "number": ("eq", "ne", "gt", "gte", "lt", "lte"),
}


@dataclass(frozen=True)
class FieldSpec:
    """Trường dùng để lọc và/hoặc nhóm.

    get: giá trị để lọc và hiển thị. key: khóa nhóm khi khác giá trị hiển thị
    (vd khách hàng nhóm theo customer_id, hiển thị tên). normalize: chuẩn hóa giá
    trị filter của LLM về giá trị trong dữ liệu; trả None nếu không nhận ra.
    """

    type: FieldType
    get: Getter
    description: str
    values: tuple[str, ...] = ()                  # enum: giá trị hợp lệ
    labels: Mapping[str, str] = field(default_factory=dict)   # enum: nhãn tiếng Việt
    key: Getter | None = None
    normalize: Callable[[str], str | None] | None = None
    missing_label: str = "(không có)"
    filterable: bool = True
    groupable: bool = True


@dataclass(frozen=True)
class MetricSpec:
    agg: Aggregation
    description: str
    value: Getter | None = None                   # count không cần
    where: Getter | None = None                   # điều kiện riêng của metric
    digits: int = 2                               # làm tròn avg/max/sum


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    description: str
    source_path: str                              # đường dẫn API danh sách bản ghi
    record_model: type[BaseModel]                 # extra="ignore": trường lạ/nhạy cảm bị bỏ
    fields: Mapping[str, FieldSpec]
    metrics: Mapping[str, MetricSpec]
    date_fields: Mapping[str, Getter]
    default_date_field: str
    system_filters: Sequence[tuple[str, Getter]] = ()   # (mô tả, điều kiện giữ bản ghi)
    default_limit: int = 10
    max_limit: int = 50

    def parse(self, items: Sequence[Any]) -> tuple[list[BaseModel], int]:
        """Item API → record. Item sai kiểu bị bỏ và chỉ được đếm (không log nội dung)."""
        records: list[BaseModel] = []
        skipped = 0
        for item in items:
            try:
                records.append(self.record_model.model_validate(item))
            except ValidationError:
                skipped += 1
        return records, skipped

    def filter_fields(self) -> list[str]:
        return [name for name, spec in self.fields.items() if spec.filterable]

    def dimensions(self) -> list[str]:
        return [name for name, spec in self.fields.items() if spec.groupable]


def hours_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds() / 3600
