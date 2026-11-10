"""`run_report.json` của một lần chạy (contract §1)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.modules.doc_ingest.schemas.base import StrictModel


class StepState(StrictModel):
    key: str
    label: str
    status: Literal["implemented", "partial", "not_implemented"]
    module: str
    backlog: str
    note: str = ""


class PageProfile(StrictModel):
    """S0: số đo một trang trước khi parse + quyết định OCR (contract §7)."""

    page: int
    text_chars: int
    bad_char_ratio: float
    rotation: int
    bitmap_area_ratio: float
    vector_path_count: int
    page_label: str | None = None
    text_layer: Literal["ok", "missing", "poor"]
    ocr: bool                       # S0 đề nghị OCR
    ocr_applied: bool = False       # Docling thực sự chạy OCR cho trang này
    docling_config: dict[str, object] = Field(default_factory=dict)


class DocumentProfile(StrictModel):
    ocr_mode: Literal["auto", "off", "force"]
    page_labels_present: bool
    pages: list[PageProfile]


class FurnitureKey(StrictModel):
    """T-17: chuỗi header/footer lặp (chữ số thay bằng `#`) và các trang có nó."""

    band: Literal["top", "bottom"]
    key: str
    pages: list[int]
    example: str


class RunSource(StrictModel):
    pdf_name: str | None = None
    pdf_sha256: str | None = None
    raw_dir: str | None = None
    total_pages: int | None = None


class RunStats(StrictModel):
    tables: int
    rows: int
    review_items: int
    review_by_code: dict[str, int]
    blocking_by_step: dict[str, int]


class TokenCount(StrictModel):
    token: str
    count: int


class ShapeCount(StrictModel):
    shape: str                       # chữ số → 9, giữ chữ cái và ký hiệu (vd. `P9-9`, `CN9`)
    count: int
    examples: list[str] = Field(default_factory=list)


class ProfileFit(StrictModel):
    """Độ khớp profile với tài liệu (Bước B1, 2026-11-09): chỉ cảnh báo, không tự đổi profile."""

    pages_total: int
    pages_ocr: int
    ocr_langs: list[str] = Field(default_factory=list)
    param_tokens: dict[str, int] = Field(default_factory=dict)       # prefix -> token đã nhận (text)
    near_miss: list[TokenCount] = Field(default_factory=list)
    unknown_shapes: list[ShapeCount] = Field(default_factory=list)   # dạng mã không profile nào khai báo
    body_chars: int = 0
    figure_text_chars: int = 0
    page_pictures_with_text: list[int] = Field(default_factory=list)  # trang có picture ≥ 50% trang chứa câu văn
    vietnamese_chars: int = 0        # ký tự riêng tiếng Việt trên trang OCR (ă â đ ê ô ơ ư + dấu thanh)
    signals: list[str] = Field(default_factory=list)


class RunReport(StrictModel):
    schema_version: Literal[1] = 1
    doc_id: str
    run_id: str
    created_at: datetime
    source: RunSource
    pages_selected: list[int]
    profile_name: str
    profile_hash: str
    tool_versions: dict[str, str] = Field(default_factory=dict)
    timings_s: dict[str, float] = Field(default_factory=dict)
    steps: list[StepState]
    stats: RunStats
    table_content_hashes: dict[str, str]
    page_range_boundary: dict[str, list[str]]   # logical_table_id -> lý do có thể bị cắt
    validation_summary: dict[str, dict[str, int]] = Field(default_factory=dict)   # V-xx -> passed/failed/not_run
    s0: DocumentProfile | None = None
    furniture_keys: list[FurnitureKey] = Field(default_factory=list)
    printed_pages: dict[int, str | None] = Field(default_factory=dict)   # T-06; None = không có nguồn
    element_types: dict[str, int] = Field(default_factory=dict)          # normalized_type -> số phần tử
    figures: dict[str, int] = Field(default_factory=dict)   # hình theo loại, caption gắn lại, nhãn T-18, ảnh đã render
    lists: dict[str, int] = Field(default_factory=dict)     # T-08: list_item, con, độ sâu, mồ côi, mơ hồ
    refs: dict[str, int] = Field(default_factory=dict)      # T-12/T-13 trên text: ref theo vai trò/kiểu/prefix
    profile_fit: ProfileFit | None = None
    chunks: dict[str, int] = Field(default_factory=dict)    # bước build (BL-16): số chunk theo vai trò/loại, kiểm lỗi
