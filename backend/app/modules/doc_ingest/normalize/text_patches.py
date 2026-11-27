"""T-22: vá chữ của một dòng Docling và phát hiện tiêu đề bị OCR hỏng (Giai đoạn 1b, 2026-11-25).

Tiêu đề trang quét bị OCR đọc hỏng (vd. 3.4.2 của F86, 6AVE, 10iV thành `ES    S    EM`) làm chunk gắn nhầm mục. Chỉ báo:
tiêu đề (section_header) trên trang OCR có vùng chữ rất rộng so với số ký tự (≥ `heading_garbled_pt_per_char`, trung vị
của tiêu đề thường là 6,5 pt/ký tự) và có chuỗi khoảng trắng liên tiếp giữa các mảnh. Tiêu đề bìa chữ lớn (20–30 pt/ký tự)
không có chuỗi khoảng trắng nên không bị bắt. Dòng bị bắt thành review chặn chunk `heading_garbled`; sửa bằng một vá
`text_patches` (file `table_patches/<doc_id>.yaml`) có đối chiếu OCR lại vùng tiêu đề và ảnh trang. Vá không khớp đúng một
dòng thành review chặn `text_patch_unmatched`, không im lặng bỏ qua. Chạy trước T-20 và trước khi dựng mục.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Sequence

from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.schemas.table_patch import TextPatch

_GAP = re.compile(r"\S\s{2,}\S")


def _norm(text: str) -> str:
    return " ".join(text.split())


def apply_text_patches(items: Sequence[RawItem], patches: Sequence[TextPatch], rec: Recorder) -> list[RawItem]:
    out = list(items)
    for patch in patches:
        hits = [i for i, item in enumerate(out) if item.page == patch.page and _norm(item.text) == _norm(patch.find)]
        if len(hits) != 1:
            anchor = out[hits[0]].element_id if hits else f"patch:{patch.patch_id}"
            rec.add_review(anchor, "text_patch_unmatched",
                           f"{patch.patch_id}: {len(hits)} lines {patch.find!r} on page {patch.page}",
                           suggested_action="re-check the text patch against the current raw output")
            continue
        item = out[hits[0]]
        out[hits[0]] = dataclasses.replace(item, text=patch.replace)
        rec.add_log("T-22", item.element_id, patch.reason, before={"text": item.text},
                    after={"text": patch.replace, "patch_id": patch.patch_id, "status": patch.status,
                           "evidence": patch.evidence})
    return out


def flag_garbled_headings(items: Sequence[RawItem], ocr_pages: set[int] | frozenset[int], pt_per_char: float,
                          rec: Recorder) -> int:
    count = 0
    for item in items:
        text = item.text.strip()
        if (item.label != "section_header" or item.parent_id is not None or item.bbox is None
                or item.page not in ocr_pages or len(text) < 2 or not _GAP.search(text)):
            continue
        if (item.bbox.x1 - item.bbox.x0) / len(text) < pt_per_char:
            continue
        rec.add_review(item.element_id, "heading_garbled",
                       f"heading text {text!r} spans {item.bbox.x1 - item.bbox.x0:.0f} pt for {len(text)} characters",
                       suggested_action="re-OCR the heading region and add a text patch (table_patches/<doc_id>.yaml)")
        count += 1
    return count
