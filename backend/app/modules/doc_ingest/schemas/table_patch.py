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


class TablePatchFile(StrictModel):
    schema_version: Literal[1] = 1
    doc_id: str
    patches: list[CellPatch]

    @model_validator(mode="after")
    def _unique_ids(self) -> "TablePatchFile":
        ids = [p.patch_id for p in self.patches]
        if len(ids) != len(set(ids)):
            raise ValueError("patch_id trùng nhau")
        return self
