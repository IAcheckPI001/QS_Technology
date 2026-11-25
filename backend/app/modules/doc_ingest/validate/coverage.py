"""V-01 độ phủ text: từ của text layer PDF so với nội dung pipeline giữ lại, theo trang.

Bắt nội dung bị rơi (phần tử bị bỏ, nhãn chưa hỗ trợ, vùng Docling không nhận) và nội
dung bị nhân đôi mà không cần biết nguyên nhân. Đến khi có `NormalizedElement`, phía
"giữ lại" là phần tử Docling được phân loại giữ (`normalize/coverage.py`).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from app.modules.doc_ingest.geometry import BBox
from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.schemas.normalized import ValidationResult
from app.modules.doc_ingest.schemas.profile import Profile

_STRIP = "".join(chr(c) for c in range(0x21, 0x30)) + ":;<=>?@[\\]^_`{|}~“”‘’…·•▪–—"
_SAMPLE = 20
# I-54 (2026-11-20): chuẩn hoá để V-01 không báo động giả. Chỉ số trên tách rời ("1 st") dính lại như text layer ("1st");
# ký tự U+FFFE (font nhúng không có Unicode) bỏ khỏi token; dòng mục lục có chấm dẫn không phải chữ thân (T-16 xếp là
# `toc`, không vào chunk) nên không tính vào mẫu số.
_ORDINAL = re.compile(r"(?<=\d)\s+(st|nd|rd|th)\b", re.IGNORECASE)
_LEADER = re.compile(r"\.{4,}|…{2,}")
GARBLED = "￾"


def tokens(text: str) -> list[str]:
    text = _ORDINAL.sub(r"\1", text.replace(GARBLED, ""))
    out = []
    for raw in text.split():
        token = raw.strip(_STRIP).casefold()
        if token:
            out.append(token)
    return out


def reference_tokens(word: str) -> list[str]:
    """Token của một từ trong text layer dùng làm mẫu số. Từ có U+FFFE (không tin cậy) hoặc dòng chấm dẫn mục lục bỏ."""
    if GARBLED in word or _LEADER.search(word):
        return []
    return tokens(word)


def _inside(box: Mapping[str, float], areas: Sequence[BBox]) -> bool:
    cx, cy = (box["x0"] + box["x1"]) / 2, (box["y0"] + box["y1"]) / 2
    return any(a.x0 <= cx <= a.x1 and a.y0 <= cy <= a.y1 for a in areas)


def _kept_tokens(items: Sequence[RawItem]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        counts.update(tokens(item.text))
        for cell in item.cells:
            counts.update(tokens(cell.text))
    return counts


def text_coverage(doc_id: str, words_by_page: Mapping[int, Sequence[Mapping[str, Any]]],
                  all_items: Sequence[RawItem], kept: Sequence[RawItem], profile: Profile,
                  rec: Recorder, ocr_pages: set[int] | None = None) -> list[ValidationResult]:
    th = profile.thresholds
    results: list[ValidationResult] = []
    for page in sorted(words_by_page):
        target = f"{doc_id}:p{page:03d}"
        if page in (ocr_pages or set()):
            results.append(ValidationResult(check_id="V-01", target=target, score=None,
                                            threshold=th.text_coverage_min, passed=None,
                                            detail={"reason": "OCR page: no independent text layer"}))
            continue
        furniture = [i.bbox for i in all_items if i.page == page and i.is_furniture and i.bbox is not None]
        page_tokens: Counter[str] = Counter()
        for word in words_by_page[page]:
            if not _inside(word["bbox"], furniture):
                page_tokens.update(reference_tokens(word["text"]))
        kept_tokens = _kept_tokens([i for i in kept if i.page == page])
        total, kept_total = sum(page_tokens.values()), sum(kept_tokens.values())
        if total == 0:
            results.append(ValidationResult(check_id="V-01", target=target, score=None,
                                            threshold=th.text_coverage_min, passed=None,
                                            detail={"reason": "no text-layer tokens outside furniture"}))
            continue
        covered = sum((page_tokens & kept_tokens).values())
        duplicate = sum((kept_tokens - page_tokens).values())
        coverage = covered / total
        dup_ratio = duplicate / kept_total if kept_total else 0.0
        missing = sorted((page_tokens - kept_tokens).elements())
        # Chỉ độ phủ thấp mới chặn chunk (nội dung thật bị rơi). Lặp vượt ngưỡng chỉ cảnh báo: 15/17 trang CRM trượt
        # chỉ vì lặp mà độ phủ ≥ 91,6%, do token chỉ số trên, ký tự hỏng, nhãn hình (I-54).
        passed = coverage >= th.text_coverage_min
        duplicate_over = dup_ratio > th.text_duplicate_max
        detail: dict[str, object] = {"page_tokens": total, "kept_tokens": kept_total,
                                     "duplicate_ratio": round(dup_ratio, 4),
                                     "duplicate_max": th.text_duplicate_max, "duplicate_over": duplicate_over,
                                     "missing_sample": missing[:_SAMPLE], "missing_count": len(missing)}
        results.append(ValidationResult(check_id="V-01", target=target, score=round(coverage, 4),
                                        threshold=th.text_coverage_min, passed=passed, detail=detail))
        if not passed:
            rec.add_review(target, "text_coverage_gap",
                           f"coverage {coverage:.1%} (min {th.text_coverage_min:.0%}), duplicate {dup_ratio:.1%} "
                           f"(max {th.text_duplicate_max:.0%}); missing e.g. {missing[:8]}",
                           target=target, suggested_action="find the dropped or duplicated content on this page")
        elif duplicate_over:
            rec.add_review(target, "text_duplicate",
                           f"duplicate {dup_ratio:.1%} (max {th.text_duplicate_max:.0%}) with coverage {coverage:.1%}; "
                           f"extra tokens e.g. {sorted((kept_tokens - page_tokens).elements())[:8]}",
                           target=target, suggested_action="check whether content is repeated or only tokenized differently")
    return results
