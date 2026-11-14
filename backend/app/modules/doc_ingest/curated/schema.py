"""Schema dữ liệu biên soạn có duyệt (`curated/products/*.yaml`, `curated/selection_matrix.yaml`).

Nhánh "nguồn biên soạn có duyệt" (doc-ingest LOG 2026-11-14): tài liệu mà pipeline trích còn lỗi cấu trúc (catalog:
I-48, I-49) được chép thành dữ liệu có cấu trúc, mỗi giá trị ghi trang nguồn, cách lấy (`origin`) và trạng thái duyệt
(`verified`). Chỉ giá trị `verified` được sinh chunk (`curated/build.py`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from app.modules.doc_ingest.schemas.base import StrictModel

CURATED_DIR = Path(__file__).resolve().parent
PRODUCTS_DIR = CURATED_DIR / "products"
MATRIX_FILE = CURATED_DIR / "selection_matrix.yaml"

Interface = Literal["pulse_train", "ethercat", "mechatrolink"]
INTERFACES: tuple[str, ...] = ("pulse_train", "ethercat", "mechatrolink")
Origin = Literal["text", "recovered", "image"]
Scalar = str | bool
Value = Scalar | dict[Interface, Scalar]


class Source(StrictModel):
    pdf: str
    sha256: str


class Reviewed(StrictModel):
    """Khối nội dung có trang nguồn và trạng thái duyệt."""

    page: int
    origin: Origin
    verified: bool = False


class Spec(Reviewed):
    key: str
    vi: str                                      # nhãn tiếng Việt do người biên soạn đặt (không in trên PDF)
    en: str                                      # nhãn như in trên PDF
    value: Value
    page_value: str | None = None                # giá trị in trên trang khi giá trị đã chốt khác (`decision`)
    decision: str | None = None                  # mã quyết định C-xx
    interface: Interface | list[Interface] | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _decision_pairs(self) -> Spec:
        if self.page_value is not None and self.decision is None:
            raise ValueError(f"{self.key}: page_value cần decision")
        return self


class Heading(Reviewed):
    title: str
    subtitle: str
    interfaces: str


class BilingualList(Reviewed):
    vi: list[str]
    en: list[str]


class SummaryPage(Reviewed):
    heading: str
    items: list[str]


class SystemPackage(Reviewed):
    label: str
    specifications: list[str]
    control_interface: list[str]
    items: list[str]


class ProductSheet(StrictModel):
    schema_version: Literal[1] = 1
    model: str
    display_name: str
    family: Literal["controller"]
    domain: Literal["product_catalog"]
    sources: dict[str, Source]
    heading: Heading
    control_interface: list[Interface]
    specs: list[Spec]
    summary_page: SummaryPage
    features: BilingualList
    operation_interface: BilingualList
    system_package: SystemPackage
    spec_attributes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_keys(self) -> ProductSheet:
        keys = [s.key for s in self.specs]
        dup = sorted({k for k in keys if keys.count(k) > 1})
        if dup:
            raise ValueError(f"{self.model}: key trùng {dup}")
        return self


class MatrixModel(StrictModel):
    page: int
    interfaces: list[Interface]
    column: str                                  # tên cột in trên trang


class Override(StrictModel):
    table_value: Scalar                          # giá trị ô trong bảng
    decision: str


class MatrixRow(StrictModel):
    key: str
    group: str
    en: str
    vi: str
    values: dict[str, Value] | None = None
    all: Scalar | None = None                    # cùng giá trị cho mọi model (hàng "Supported")
    override: dict[str, Override] = Field(default_factory=dict)
    note: str | None = None
    verified: bool = False

    @model_validator(mode="after")
    def _values_or_all(self) -> MatrixRow:
        if (self.values is None) == (self.all is None):
            raise ValueError(f"{self.key}: cần đúng một trong values / all")
        return self


class SelectionMatrix(StrictModel):
    schema_version: Literal[1] = 1
    source: Source
    models: dict[str, MatrixModel]
    rows: list[MatrixRow]

    @model_validator(mode="after")
    def _complete(self) -> SelectionMatrix:
        for row in self.rows:
            if row.values is None:
                continue
            missing = sorted(set(self.models) - set(row.values))
            extra = sorted(set(row.values) - set(self.models))
            if missing or extra:
                raise ValueError(f"{row.key}: thiếu model {missing}, thừa {extra}")
            for model, value in row.values.items():
                if isinstance(value, dict) and not set(value) <= set(self.models[model].interfaces):
                    raise ValueError(f"{row.key}/{model}: giao tiếp ngoài {self.models[model].interfaces}")
            unknown = sorted(set(row.override) - set(self.models))
            if unknown:
                raise ValueError(f"{row.key}: override model lạ {unknown}")
        return self

    def value(self, row: MatrixRow, model: str) -> Value:
        return row.all if row.all is not None else row.values[model]  # type: ignore[index]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_product(path: Path) -> ProductSheet:
    return ProductSheet.model_validate(_load_yaml(path))


def load_products(directory: Path = PRODUCTS_DIR) -> list[ProductSheet]:
    return [load_product(p) for p in sorted(directory.glob("*.yaml"))]


def load_matrix(path: Path = MATRIX_FILE) -> SelectionMatrix:
    return SelectionMatrix.model_validate(_load_yaml(path))
