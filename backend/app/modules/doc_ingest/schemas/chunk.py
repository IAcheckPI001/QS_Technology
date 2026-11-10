"""Chunk nháp của chunk builder (contract C2 §4, §13) và kết quả kiểm chất lượng (§10).

`DraftChunk` là tập dữ liệu chunk **độc lập với bảng** `doc_chunks`: gồm trường lõi tương ứng cột hiện có và
trường ứng viên có kiểu (§13). Adapter `export/doc_chunks_v1.py` chuyển thành dòng đúng bảng hiện tại.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.modules.doc_ingest.schemas.base import StrictModel
from app.modules.doc_ingest.schemas.manifest import Scope
from app.modules.doc_ingest.schemas.normalized import ApplicabilityCandidate, Box
from app.modules.doc_ingest.technical_refs.params import ParamRef

ChunkType = Literal[
    "section", "procedure", "parameter", "alarm", "table", "figure", "wiring", "pinout", "dimension",
    "overview", "spec",
]
ChunkRole = Literal["parent", "child", "standalone"]
VISUAL_TYPES: frozenset[str] = frozenset({"figure", "wiring", "pinout", "dimension"})


class ChunkAsset(StrictModel):
    """`bucket`, `path`, `page`, `printed_page` khớp `ChunkAsset` của chatbot; `element_id`, `local_path` chỉ dùng
    offline (adapter bỏ đi)."""

    bucket: str
    path: str                                    # "<doc_id>/<element_id với : → _>.png"
    page: int
    printed_page: int | None = None
    element_id: str
    local_path: str | None = None                # tương đối với thư mục chạy; None = chưa render


class FigureLabel(StrictModel):
    text: str
    element_id: str                              # picture/screenshot chứa nhãn
    bbox: Box | None = None
    source: Literal["text_layer", "ocr", "crop_ocr"]


class DraftChunk(StrictModel):
    schema_version: Literal[1] = 1
    # định danh, quan hệ
    chunk_key: str                               # "{doc_id}:B{chunk_index:04d}"
    parent_key: str | None = None
    chunk_role: ChunkRole
    source: Literal["builder"] = "builder"
    chunk_index: int
    # lọc
    domain: Literal["technical_docs"] = "technical_docs"
    scopes: list[Scope]
    product_models: list[str]
    control_interface: list[str] = Field(default_factory=list)
    spec_attributes: list[str] = Field(default_factory=list)
    chunk_type: ChunkType
    is_active: bool = True
    # tài liệu, trích dẫn
    doc_id: str
    doc_type: str
    doc_title: str
    doc_version: str
    lang: str
    section_id: str | None = None
    section_path: list[str] = Field(default_factory=list)
    section_title: str
    page_start: int
    page_end: int
    printed_page_start: str | None = None
    printed_page_end: str | None = None
    assets: list[ChunkAsset] = Field(default_factory=list)
    # nội dung, tìm kiếm
    content: str
    summary_vi: str | None = None
    faq_vi: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    embed_text: str
    token_count: int | None = None               # tiktoken cl100k trên embed_text; None khi venv không có tiktoken
    content_hash: str
    # nguồn, trường ứng viên (§13)
    element_ids: list[str] = Field(default_factory=list)
    extraction: Literal["text_layer", "ocr", "mixed", "unknown"] = "unknown"
    logical_table_id: str | None = None
    row_ids: list[str] = Field(default_factory=list)
    param_refs: list[ParamRef] = Field(default_factory=list)
    io_codes: list[str] = Field(default_factory=list)
    applicability: list[ApplicabilityCandidate] = Field(default_factory=list)
    applies_to_models: list[str] = Field(default_factory=list)
    figure_labels: list[FigureLabel] = Field(default_factory=list)
    related_chunk_keys: list[str] = Field(default_factory=list)
    review_blockers: list[str] = Field(default_factory=list)   # mã review chặn chunk: không được xuất bản
    review_notes: list[str] = Field(default_factory=list)      # mã review chặn fact (thông tin cho người duyệt)
    flags: list[str] = Field(default_factory=list)
    enrichment_status: Literal["none", "draft", "approved"] = "none"


class CheckResult(StrictModel):
    check_id: str
    title: str
    checked: int
    passed: bool | None                          # None: không có gì để kiểm
    failures: list[str] = Field(default_factory=list)
    note: str = ""


class Coverage(StrictModel):
    required: int
    covered: int
    missing: list[str] = Field(default_factory=list)
    duplicated: list[str] = Field(default_factory=list)
    excluded: dict[str, int] = Field(default_factory=dict)   # lý do -> số phần tử không cần chunk
    chars_total: int = 0
    chars_kept: int = 0
    char_ratio: float | None = None


class BoundaryMatch(StrictModel):
    page: int
    chunk_type: str
    start: str
    end: str
    matched_key: str | None = None
    matched_type: str | None = None


class BoundaryScore(StrictModel):
    labels_verified: bool
    pages: list[int] = Field(default_factory=list)
    expected: int = 0
    matched: int = 0
    type_correct: int = 0
    chunks_on_pages: int = 0
    chunks_matched: int = 0
    precision: float | None = None
    recall: float | None = None
    type_accuracy: float | None = None
    details: list[BoundaryMatch] = Field(default_factory=list)
    unmatched_chunks: list[str] = Field(default_factory=list)


class ManualMatch(StrictModel):
    manual_index: int
    manual_type: str
    manual_title: str
    manual_page: int | None
    manual_chars: int
    best_key: str | None
    best_type: str | None
    containment: float                            # tỷ lệ token của chunk tay có trong chunk builder khớp nhất
    union_containment: float                      # tỷ lệ token chunk tay có trong mọi chunk builder cùng trang


class ManualComparison(StrictModel):
    csv_path: str
    doc_id: str
    manual_chunks: int
    builder_chunks: int
    covered: int                                  # containment ≥ ngưỡng
    threshold: float
    matches: list[ManualMatch] = Field(default_factory=list)
    builder_unmatched: list[str] = Field(default_factory=list)
    manual_types: dict[str, int] = Field(default_factory=dict)
    builder_types: dict[str, int] = Field(default_factory=dict)


class ReviewSummary(StrictModel):
    ok: int = 0
    fix: int = 0
    pending: int = 0
    stale: int = 0                                # đã duyệt nhưng content_hash đổi sau khi build lại
    open_fix: list[str] = Field(default_factory=list)


class GateItem(StrictModel):
    name: str
    value: float | int | None
    threshold: str
    passed: bool | None


class ChunkQuality(StrictModel):
    schema_version: Literal[1] = 1
    doc_id: str
    run_dir: str
    chunks: int
    by_role: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    content_chars: dict[str, int] = Field(default_factory=dict)   # min/median/max cho chunk lá
    token_count_method: Literal["tiktoken", "unavailable"] = "unavailable"
    flags: dict[str, int] = Field(default_factory=dict)
    blocked_chunks: dict[str, int] = Field(default_factory=dict)   # mã review chặn chunk -> số chunk lá mang mã
    checks: list[CheckResult] = Field(default_factory=list)
    coverage: Coverage | None = None
    boundaries: BoundaryScore | None = None
    manual: ManualComparison | None = None
    review: ReviewSummary = Field(default_factory=ReviewSummary)
    export_errors: list[str] = Field(default_factory=list)
    gate: list[GateItem] = Field(default_factory=list)
    gate_passed: bool | None = None
    provisional: bool = True


class ChunkReviewEntry(StrictModel):
    chunk_key: str
    content_hash: str
    verdict: Literal["pending", "ok", "fix"] = "pending"
    note: str = ""
    reviewer: str = ""


class ChunkReviewFile(StrictModel):
    schema_version: Literal[1] = 1
    doc_id: str
    reviews: list[ChunkReviewEntry] = Field(default_factory=list)
