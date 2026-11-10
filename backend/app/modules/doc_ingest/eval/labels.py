"""Schema bộ nhãn tay mẫu và kết quả chấm điểm (Bước B2, B3; 2026-11-09).

Nhãn nằm ở `backend/tests/doc_ingest/fixtures/eval/{doc_id}.labels.json`. Nhãn do Claude soạn
nháp có `verified: false`; kết quả chấm trên nhãn chưa xác nhận chỉ là **tạm**.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.modules.doc_ingest.schemas.base import StrictModel


class LabelParam(StrictModel):
    label: str                                   # nguyên văn trong tài liệu
    prefix: str
    kind: Literal["single", "range", "list"]
    codes: list[int] = Field(default_factory=list)          # single, list
    range: tuple[int, int] | None = None                     # range: (đầu, cuối)
    role: Literal["definition", "value_option", "mention"]

    def all_codes(self) -> tuple[int, ...]:
        if self.range is not None:
            return tuple(range(self.range[0], self.range[1] + 1))
        return tuple(sorted(set(self.codes)))


class LabelListChild(StrictModel):
    child: str                                   # đầu text của mục con (đủ để nhận ra duy nhất trên trang)
    parent: str                                  # đầu text của mục cha


class LabelChunk(StrictModel):
    """Đơn vị chunk mong đợi bắt đầu trên trang (Bước 2b, contract C2 §10). `start`/`end`: đầu và cuối text
    nguyên văn của đơn vị (đủ để nhận ra duy nhất)."""

    chunk_type: str
    start: str
    end: str
    note: str = ""


class ChunkLabelPage(StrictModel):
    page: int
    expected_chunks: list[LabelChunk] = Field(min_length=1)   # mọi đơn vị (trừ nhóm dòng bảng) bắt đầu trên trang


class ChunkLabels(StrictModel):
    """Nhãn ranh giới chunk (`fixtures/eval/{doc_id}.chunks.json`), tách khỏi nhãn BL-34 để không đổi kết quả
    chấm T-12/T-08 hiện có."""

    schema_version: Literal[1] = 1
    doc_id: str
    verified: bool = False
    labeled_by: str
    method: str
    pages: list[ChunkLabelPage]


class LabelPage(StrictModel):
    page: int
    note: str = ""
    param_refs: list[LabelParam] = Field(default_factory=list)    # đầy đủ mọi mã trong text thân của trang
    list_children: list[LabelListChild] = Field(default_factory=list)
    applicability: list[str] = Field(default_factory=list)        # cụm điều kiện áp dụng (gồm cả trong bảng)
    body_snippets: list[str] = Field(default_factory=list)        # câu phải có trong nội dung thân (không phải chữ trong hình)


class DocLabels(StrictModel):
    schema_version: Literal[1] = 1
    doc_id: str
    source_pdf: str
    verified: bool = False
    labeled_by: str
    method: str
    pages: list[LabelPage]


class Metric(StrictModel):
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float | None = None
    recall: float | None = None


class GroupScore(StrictModel):
    pages: list[int] = Field(default_factory=list)
    t12: Metric = Field(default_factory=Metric)
    t12_role_accuracy: float | None = None
    t08_correct: int = 0
    t08_wrong: int = 0
    t08_missing: int = 0
    t13: Metric = Field(default_factory=Metric)
    content_found: int = 0
    content_total: int = 0


class GateCheck(StrictModel):
    name: str
    value: float | int | None
    threshold: str
    passed: bool | None                          # None: không có dữ liệu để kiểm


class EvalReport(StrictModel):
    schema_version: Literal[1] = 1
    doc_id: str
    run_id: str
    labels_verified: bool
    provisional: bool                            # nhãn chưa xác nhận → kết quả tạm
    groups: dict[str, GroupScore]                # text_layer | ocr
    gate: list[GateCheck]
    gate_passed: bool | None
    details: dict[str, list[str]] = Field(default_factory=dict)   # sai cụ thể: t12_fp, t12_fn, t08, t13_fn, content_missing
