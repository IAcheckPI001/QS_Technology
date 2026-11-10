"""Catalog báo cáo: mô tả dataset bằng dữ liệu để engine không biết gì về từng nguồn.

Một dataset khai báo trường lọc/nhóm, metric, trường ngày, cột được liệt kê và nguồn:
- `list_api` (vd tickets): record từ API danh sách (trường nhạy cảm bị bỏ ngay khi parse),
  engine trong tiến trình lọc/nhóm/tính.
- `report_api` (`report` khác None): CRM Reporting Query API chạy SQL; mỗi trường/metric/cột
  khai báo sẵn đường dẫn cột (`fk.fk.cột`). LLM chỉ thấy tên logic, không thấy đường dẫn.
Thêm dataset mới là thêm một DatasetSpec, không sửa contract, validate hay engine.
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
# Đường dẫn cột của Reporting API: `cột` hoặc `fk_col.fk_col.cột` (theo relations của CRM).
ApiPath = str

OPERATORS_BY_TYPE: dict[FieldType, tuple[str, ...]] = {
    "enum": ("eq", "ne", "in", "not_in"),
    "string": ("eq", "ne", "in", "not_in"),
    "bool": ("eq", "ne"),
    "number": ("eq", "ne", "gt", "gte", "lt", "lte"),
}


@dataclass(frozen=True)
class FieldSpec:
    """Trường dùng để lọc và/hoặc nhóm.

    get: giá trị để lọc và hiển thị (nguồn list_api). key: khóa nhóm khi khác giá trị hiển
    thị (vd khách hàng nhóm theo customer_id, hiển thị tên). normalize: chuẩn hóa giá
    trị filter của LLM về giá trị trong dữ liệu; trả None nếu không nhận ra.

    Nguồn report_api: api_path là cột để lọc và nhóm; api_label_path (nếu có) là cột hiển
    thị khi nhóm (vd nhóm theo assigned_to, hiển thị assigned_to.username); api_filter_path
    (nếu có) là cột để lọc thay cho api_path (vd lọc người theo username).
    casefold=False: giữ nguyên hoa/thường khi lọc (SQL so khớp chính xác).
    """

    type: FieldType
    get: Getter | None
    description: str
    values: tuple[str, ...] = ()                  # enum: giá trị hợp lệ
    labels: Mapping[str, str] = field(default_factory=dict)   # enum: nhãn tiếng Việt
    key: Getter | None = None
    normalize: Callable[[str], str | None] | None = None
    missing_label: str = "(không có)"
    filterable: bool = True
    groupable: bool = True
    api_path: ApiPath | None = None
    api_label_path: ApiPath | None = None
    api_filter_path: ApiPath | None = None
    casefold: bool = True


@dataclass(frozen=True)
class MetricSpec:
    agg: Aggregation
    description: str
    value: Getter | None = None                   # count không cần
    where: Getter | None = None                   # điều kiện riêng của metric
    digits: int = 2                               # làm tròn avg/max/sum
    # report_api: metric của API (`count`, `count_distinct:<path>`…) và filter riêng của metric
    # (dạng filter của API); metric có filter riêng chạy thành query riêng rồi ghép theo nhóm.
    api_metric: str | None = None
    api_filters: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ColumnSpec:
    """Cột được phép liệt kê ở chế độ danh sách (crm_records): whitelist tường minh.

    Không bao giờ khai báo cột nội dung tự do hay liên hệ (subject, description, phone,
    email, notes, address) hay bí mật. get: nguồn list_api; api_path: nguồn report_api.
    """

    description: str
    get: Getter | None = None
    api_path: ApiPath | None = None


@dataclass(frozen=True)
class ReportApiSource:
    """Dataset chạy trên CRM Reporting Query API.

    table: dataset gốc của API. date_paths: tên trường ngày logic → đường dẫn cột.
    system_filters: (mô tả, filter API) luôn áp dụng. default_filters: (mô tả, trường logic,
    filter API) áp dụng khi query không tự lọc hay nhóm theo trường đó.
    required_permission: quyền CRM cần có (chỉ để mô tả và báo lỗi; CRM tự kiểm tra).
    """

    table: str
    date_paths: Mapping[str, ApiPath]
    system_filters: Sequence[tuple[str, Mapping[str, Any]]] = ()
    default_filters: Sequence[tuple[str, str, Mapping[str, Any]]] = ()
    required_permission: str | None = None
    # Dimension chia kỳ: (trường ngày logic, grain) → tên dimension của API. Rỗng: theo quy
    # tắc hậu tố của API (`<đường dẫn>_day`, `<đường dẫn>_month`). Dataset dựng sẵn của CRM
    # (vd customers) có tên riêng và chỉ khai báo các kỳ nó hỗ trợ.
    period_dimensions: Mapping[tuple[str, str], str] = field(default_factory=dict)

    def period_dimension(self, date_field: str, grain: str) -> str | None:
        if self.period_dimensions:
            return self.period_dimensions.get((date_field, grain))
        path = self.date_paths.get(date_field)
        return f"{path}_{grain}" if path is not None and grain in ("day", "month") else None


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    description: str
    fields: Mapping[str, FieldSpec]
    metrics: Mapping[str, MetricSpec]
    # list_api: getter; report_api: chỉ cần tên (đường dẫn nằm ở report.date_paths).
    date_fields: Mapping[str, Getter | None]
    default_date_field: str
    source_path: str = ""                         # list_api: đường dẫn API danh sách bản ghi
    record_model: type[BaseModel] | None = None   # extra="ignore": trường lạ/nhạy cảm bị bỏ
    system_filters: Sequence[tuple[str, Getter]] = ()   # (mô tả, điều kiện giữ bản ghi)
    default_limit: int = 10
    max_limit: int = 50
    report: ReportApiSource | None = None
    list_columns: Mapping[str, ColumnSpec] = field(default_factory=dict)
    # Giả định/định nghĩa nghiệp vụ cố định, trả kèm kết quả để agent nêu đúng một cách hiểu.
    definitions: Sequence[str] = ()

    @property
    def source(self) -> Literal["list_api", "report_api"]:
        return "list_api" if self.report is None else "report_api"

    def system_filter_labels(self) -> list[str]:
        if self.report is None:
            return [label for label, _ in self.system_filters]
        return [label for label, _ in self.report.system_filters]

    def parse(self, items: Sequence[Any]) -> tuple[list[BaseModel], int]:
        """Item API → record. Item sai kiểu bị bỏ và chỉ được đếm (không log nội dung)."""
        assert self.record_model is not None, f"dataset {self.name} has no list API record"
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
