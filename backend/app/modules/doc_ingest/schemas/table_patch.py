"""Lớp vá ô thủ công cho bảng logic (2026-11-25, Toma duyệt hướng).

Dùng cho lỗi nằm sẵn trong dữ liệu trích (raw Docling gán chân/ô sai hàng) mà không sửa được bằng luật chung. Mỗi vá
sửa MỘT chuỗi con trong MỘT ô, xác định bằng (trang, khoá hàng, cột), có chuỗi cần thay phải xuất hiện đúng một lần.
Không khớp thì thành mục review chặn (`table_patch_unmatched`), không im lặng bỏ qua.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.modules.doc_ingest.schemas.base import StrictModel


class CellPatch(StrictModel):
    patch_id: str
    page: int                                  # pdf_page_index của đoạn bảng chứa hàng (hàng được gộp T-15b tính theo hàng đích)
    row_key: str                               # nội dung ô cột 0 của hàng (đã strip)
    column: int = Field(ge=0)
    find: str = Field(min_length=1)            # chuỗi con phải xuất hiện đúng một lần trong ô
    replace: str
    reason: str
    evidence: str                              # trang PDF/ảnh đã đối chiếu
    status: Literal["proposed", "verified"] = "proposed"
    verified_by: str = ""                      # người xác nhận khi status = verified


class TextPatch(StrictModel):
    """T-22 (Giai đoạn 1b, 2026-11-25): thay nguyên văn MỘT dòng chữ của Docling (thường là tiêu đề bị OCR hỏng, vd.
    `ES    S    EM` thay cho `3.4.2 ASSIGN MACHINE…`) trước khi dựng mục và chunk. Dòng cần sửa xác định bằng (trang,
    nội dung dòng đã gộp khoảng trắng) và phải là dòng duy nhất khớp trên trang."""

    patch_id: str
    page: int                                  # pdf_page_index
    find: str = Field(min_length=1)            # nội dung dòng hiện tại (gộp khoảng trắng)
    replace: str = Field(min_length=1)
    reason: str
    evidence: str                              # vd. "re-OCR vùng tiêu đề 3x + ảnh trang PDF"
    status: Literal["proposed", "verified"] = "proposed"
    verified_by: str = ""


class TablePatchFile(StrictModel):
    schema_version: Literal[1] = 1
    doc_id: str
    patches: list[CellPatch] = Field(default_factory=list)
    text_patches: list[TextPatch] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "TablePatchFile":
        ids = [p.patch_id for p in [*self.patches, *self.text_patches]]
        if len(ids) != len(set(ids)):
            raise ValueError("patch_id trùng nhau")
        return self
