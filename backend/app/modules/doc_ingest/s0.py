"""S0 hồ sơ tài liệu: quyết định OCR theo trang từ số đo (contract §7). Không import pdfium.

Luật chung: trang có ít ký tự text layer hơn `ocr_min_chars`, hoặc tỷ lệ ký tự lỗi vượt
`text_bad_char_max`, thì không đọc được bằng text layer → cần OCR. Text do OCR sinh ra
không có nguồn độc lập để V-01 đối chiếu, nên trang đó luôn có `ocr_required` (chặn chunk
cho tới khi người duyệt xác nhận).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Literal

from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.schemas.profile import Thresholds
from app.modules.doc_ingest.schemas.run import DocumentProfile, PageProfile

OcrMode = Literal["auto", "off", "force"]
OCR_ENGINE = {"engine": "rapidocr", "backend": "torch", "lang": ["en"], "force_full_page_ocr": True}
_HASH = re.compile(r"#\s?(\d*)")


def hash_code_counts(text: str) -> tuple[int, int]:
    """(số token `#`, số token `#` có < 3 chữ số). Mã tham số hợp lệ có ≥ 3 chữ số (`#8090`); text layer mất glyph
    cho `# 9 - # 97` (I-55, 10iV tr.107–110). Thuần Python để test không cần pdfium."""
    found = [len(m.group(1)) for m in _HASH.finditer(text)]
    return len(found), sum(1 for n in found if n < 3)


def decide(metrics: Mapping[str, object], thresholds: Thresholds) -> PageProfile:
    chars = int(metrics["text_chars"])  # type: ignore[arg-type]
    bad = float(metrics["bad_char_ratio"])  # type: ignore[arg-type]
    text_layer = "missing" if chars < thresholds.ocr_min_chars else (
        "poor" if bad > thresholds.text_bad_char_max else "ok")
    # I-55: text layer có chữ nhưng mất glyph (mã `#8090` thành `# 9`) vẫn qua kiểm ký tự lỗi; V-01 đối chiếu cùng
    # text layer nên không thấy. Nhiều mã `#` thiếu chữ số → coi như hỏng, dùng nhánh OCR.
    codes = int(metrics.get("hash_codes", 0))  # type: ignore[call-overload]
    damaged = int(metrics.get("hash_damaged", 0))  # type: ignore[call-overload]
    if (text_layer == "ok" and codes >= thresholds.text_integrity_min_codes
            and damaged / codes > thresholds.text_integrity_damage_max):
        text_layer = "poor"
    return PageProfile(**metrics, text_layer=text_layer, ocr=text_layer != "ok")  # type: ignore[arg-type]


def build_profile(measured: Sequence[Mapping[str, object]], thresholds: Thresholds,
                  ocr_mode: OcrMode) -> DocumentProfile:
    pages = []
    for metrics in measured:
        page = decide(metrics, thresholds)
        applied = ocr_mode == "force" or (ocr_mode == "auto" and page.ocr)
        config = {"do_ocr": applied, **(OCR_ENGINE if applied else {})}
        pages.append(page.model_copy(update={"ocr_applied": applied, "docling_config": config}))
    return DocumentProfile(ocr_mode=ocr_mode, page_labels_present=any(p.page_label for p in pages), pages=pages)


def ocr_pages(profile: DocumentProfile) -> set[int]:
    return {p.page for p in profile.pages if p.ocr_applied}


def s0_review(profile: DocumentProfile, doc_id: str, rec: Recorder) -> None:
    for page in profile.pages:
        if not page.ocr and not page.ocr_applied:
            continue
        target = f"{doc_id}:p{page.page:03d}"
        if page.ocr_applied:
            how = "OCR applied (rapidocr)"
        else:
            how = "OCR not applied (--ocr off): page content is missing"
        reason = f"text layer {page.text_layer} ({page.text_chars} chars)" if page.ocr else "OCR forced"
        if page.ocr and page.hash_damaged:
            reason += f"; {page.hash_damaged}/{page.hash_codes} '#' codes lack digits (damaged text layer)"
        rec.add_review(target, "ocr_required", f"{reason}; {how}", target=target,
                       suggested_action="verify OCR text against the page image before publishing")
