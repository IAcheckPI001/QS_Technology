"""T-21: áp lớp vá ô thủ công lên bảng logic (xem `schemas/table_patch.py`; file vá nạp ở `table_patch_io.py`).

Chạy ngay sau `build_logical_tables` (sau T-15/T-15b), trước khi dựng phần tử và chunk. Mỗi vá ghi một dòng log
(`before`/`after` nguyên văn ô) và cờ `cell_patched:<id>` trên bảng; vá không khớp thành review chặn chunk.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.schemas.normalized import LogicalTable
from app.modules.doc_ingest.schemas.table_patch import CellPatch


def apply_patches(tables: Sequence[LogicalTable], patches: Sequence[CellPatch], rec: Recorder) -> int:
    """Áp từng vá theo thứ tự; trả số vá đã áp."""
    applied = 0
    for patch in patches:
        hits = [(t, r) for t in tables for r in t.rows
                if not r.is_header and r.segment < len(t.segments)
                and t.segments[r.segment].pdf_page_index == patch.page and r.cells[0].text.strip() == patch.row_key]
        on_page = [t for t in tables if any(s.pdf_page_index == patch.page for s in t.segments)]
        anchor = (on_page[0].segments[0].element_id if on_page else f"patch:{patch.patch_id}")

        def unmatched(detail: str) -> None:
            rec.add_review(anchor, "table_patch_unmatched", f"{patch.patch_id}: {detail}",
                           target=on_page[0].logical_table_id if on_page else None,
                           suggested_action="re-check the patch against the current normalized table")

        if len(hits) != 1:
            unmatched(f"{len(hits)} rows with key {patch.row_key!r} on page {patch.page}")
            continue
        table, row = hits[0]
        if patch.column >= len(row.cells):
            unmatched(f"column {patch.column} out of range ({len(row.cells)} columns)")
            continue
        cell = row.cells[patch.column]
        count = cell.text.count(patch.find)
        if count != 1:
            unmatched(f"text {patch.find!r} occurs {count} times in the cell")
            continue
        before = cell.text
        cell.text = before.replace(patch.find, patch.replace, 1)
        table.flags.append(f"cell_patched:{patch.patch_id}")
        rec.add_log("T-21", table.segments[row.segment].element_id, patch.reason,
                    target=f"{table.logical_table_id}:{row.row_id}:col{patch.column}",
                    before={"text": before}, after={"text": cell.text, "patch_id": patch.patch_id,
                                                    "status": patch.status, "evidence": patch.evidence})
        applied += 1
    return applied
