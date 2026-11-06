"""NormalizedElement, LogicalTable, ứng viên applicability, review queue và log chuẩn hóa
(contract §2, §3, §5, §6)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.modules.doc_ingest.schemas.base import StrictModel
from app.modules.doc_ingest.technical_refs.params import ParamRef

ApplicabilityStatus = Literal["not_available", "available_only", "conditional"]
ReviewCode = Literal[
    "column_count_mismatch",
    "unassigned_cell",
    "unsupported_element",
    "empty_table",
    "ambiguous_continuation",
    "header_demotion_unsure",
    "header_missing",
    "complex_header",
    "orphan_row",
    "ocr_required",
    "furniture_reclassified",
    "furniture_unconfirmed",
    "printed_page_conflict",
    "text_coverage_gap",
    "table_crosscheck_mismatch",
    "column_type_inconsistent",
    "applicability_note",
    "applicability_model_unmatched",
    "caption_ambiguous",
    "watermark_conflict",
    "param_unparseable",
    "range_too_long",
    "param_code_overlap",
    "list_orphan",
    "per_code_values",
    "doc_version_mismatch",
    "source_conflict",
]


class Box(StrictModel):
    """Bbox theo point, gốc trên-trái của trang."""

    x0: float
    y0: float
    x1: float
    y1: float


class ApplicabilityCandidate(StrictModel):
    """Ứng viên ghi chú áp dụng do T-13 đánh trên text/cell. KHÔNG phải fact: chưa trích,
    chưa duyệt; bước trích fact (BL-17) mới tạo `Applicability` gắn với fact."""

    status: ApplicabilityStatus
    note: str                                  # nguyên văn, là chuỗi con của text nguồn
    models: list[str] = Field(default_factory=list)       # khớp registry
    interfaces: list[str] = Field(default_factory=list)   # khớp control_interface của registry
    condition_text: str                        # phần điều kiện nguyên văn sau cụm từ
    rule_id: Literal["T-13"] = "T-13"


class Applicability(StrictModel):
    """Ghi chú áp dụng của một fact (D-04). Fact mang ghi chú luôn được giữ, không bao giờ
    bị bỏ. Chưa dùng: tạo ở bước trích fact (BL-17), trạng thái duyệt thêm cùng bước đó."""

    status: ApplicabilityStatus
    note: str
    models: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    condition_text: str
    source: Literal["lexicon", "llm", "reviewer"]


class Segment(StrictModel):
    element_id: str
    pdf_page_index: int
    bbox: Box
    num_cols_docling: int
    header_rows_docling: list[int] = Field(default_factory=list)


class Column(StrictModel):
    index: int
    header_text: str | None
    x_min: float
    x_max: float
    header_source: Literal["detected", "inherited", "none"]


class Cell(StrictModel):
    col: int
    text: str
    bbox: Box | None
    raw_cell_ref: str | None
    docling_col: int | None
    docling_header: bool
    assigned_by: Literal["bbox", "empty_fill"]
    merged_cell_refs: list[str] = Field(default_factory=list)   # cell nguồn T-15 gộp vào ô này


class Row(StrictModel):
    row_id: str
    segment: int
    is_header: bool
    repeated_header: bool = False
    cells: list[Cell]
    merged_row_ids: list[str] = Field(default_factory=list)
    param_ref: ParamRef | None = None
    applicability_candidates: list[ApplicabilityCandidate] = Field(default_factory=list)


class UnassignedCell(StrictModel):
    row_id: str
    text: str
    bbox: Box
    raw_cell_ref: str
    reason: Literal["outside_columns", "column_collision"]


class LogicalTable(StrictModel):
    schema_version: Literal[1] = 1
    logical_table_id: str
    segments: list[Segment]
    columns: list[Column]
    rows: list[Row]
    unassigned_cells: list[UnassignedCell] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


NormalizedType = Literal[
    "heading", "label_heading", "text", "list_item", "warning", "table_segment", "picture", "screenshot",
    "caption", "watermark_candidate", "furniture", "figure_text", "toc", "unsupported",
]


class PrintedPage(StrictModel):
    """Số trang in (T-06). Không bao giờ suy từ offset: không có nguồn → `value=None`."""

    value: str | None = None
    source: Literal["page_labels", "furniture_sequence", "manifest_override"] | None = None


class RawRef(StrictModel):
    file: str
    self_ref: str


class TableRef(StrictModel):
    logical_table_id: str
    segment_index: int


class ImageInfo(StrictModel):
    """Vùng ảnh của picture/screenshot/watermark_candidate (T-14). Đường dẫn và kích thước px
    chỉ có khi lần chạy có PDF để render; chạy từ raw không có PDF → chỉ `crop_bbox`."""

    original_path: str | None = None           # tương đối với thư mục chạy
    preview_path: str | None = None
    scale: float | None = None
    px_w: int | None = None
    px_h: int | None = None
    crop_bbox: Box
    crop_sources: list[Literal["docling", "bitmap", "vector", "label"]]
    extraction: Literal["page_render_crop", "manual_region"] = "page_render_crop"


class CaptionLink(StrictModel):
    source: Literal["docling", "rule"]
    rule_id: Literal["T-11"] | None = None


class NormalizedElement(StrictModel):
    """Một phần tử sau S1 (contract §2). Trường của bước chưa có code (T-08 list, T-12/T-13
    trên text) để rỗng cho tới khi bước đó có."""

    schema_version: Literal[1] = 1
    element_id: str
    raw_ref: RawRef
    pdf_page_index: int
    printed_page: PrintedPage
    content_layer: Literal["body", "furniture"]
    reading_order: int
    source_element_type: str
    normalized_type: NormalizedType
    bbox: Box | None
    text: str | None
    lang: str | None = None                    # chưa có nhận diện ngôn ngữ (I-16)
    section_path: list[str] = Field(default_factory=list)
    section_path_source: Literal["numbering", "inherited", "none"] = "none"
    label_heading: str | None = None
    parent_element_id: str | None = None       # picture/table chứa phần tử (figure_text, caption)
    list_info: dict[str, object] | None = None  # contract §2 `list` (T-08); đổi tên vì trùng builtin
    table_ref: TableRef | None = None
    image: ImageInfo | None = None
    caption_element_id: str | None = None      # với picture/screenshot/bảng: caption của nó
    caption_link: CaptionLink | None = None
    param_refs: list[ParamRef] = Field(default_factory=list)
    applicability_candidates: list[ApplicabilityCandidate] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    review_required: bool = False


class ReviewItem(StrictModel):
    item_id: str
    element_id: str
    code: ReviewCode
    blocking: bool
    blocks: Literal["chunk", "fact", "publish", "none"]
    target: str | None = None
    detail: str
    suggested_action: str | None = None


class ValidationResult(StrictModel):
    """Một dòng `validation.jsonl` (contract §8). `passed=None`: kiểm không chạy được."""

    check_id: Literal["V-01", "V-02", "V-03", "V-04"]
    target: str
    score: float | None
    threshold: float
    passed: bool | None
    detail: dict[str, object] = Field(default_factory=dict)


class LogEntry(StrictModel):
    rule_id: str
    element_id: str
    target: str | None = None
    before: dict[str, object] = Field(default_factory=dict)
    after: dict[str, object] = Field(default_factory=dict)
    reason: str
    deterministic: bool = True

