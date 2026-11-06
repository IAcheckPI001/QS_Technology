"""Phân loại nhãn Docling: phần tử nào pipeline giữ, phần tử nào chưa hỗ trợ (không bỏ im lặng).

Bảng nhãn là từ vựng của Docling, không phải tri thức miền. T-16: `document_index` (mục
lục) giữ nguyên cell, không vào bảng logic, không chunk.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.normalize.recorder import Recorder

HANDLED_LABELS = frozenset({"table", "document_index", "picture", "page_header", "page_footer"})
# Giữ nguyên văn, chuẩn hóa ở BL-07…BL-10.
PENDING_S1_LABELS = frozenset({"title", "section_header", "text", "list_item", "caption", "footnote"})


@dataclass
class ElementCoverage:
    kept: list[RawItem] = field(default_factory=list)        # phần tử body pipeline giữ lại
    toc: list[RawItem] = field(default_factory=list)         # T-16
    unsupported: list[RawItem] = field(default_factory=list)


def classify_items(items: Sequence[RawItem], rec: Recorder) -> ElementCoverage:
    result = ElementCoverage()
    for item in items:
        if item.is_furniture:
            continue
        if item.label in HANDLED_LABELS or item.label in PENDING_S1_LABELS:
            result.kept.append(item)
            if item.label == "document_index":
                result.toc.append(item)
                rec.add_log("T-16", item.element_id, "document_index kept as table of contents; not chunked",
                            after={"normalized_type": "toc", "cells": len(item.cells)})
            continue
        result.unsupported.append(item)
        excerpt = item.text[:80] if item.text else f"{len(item.cells)} cell"
        rec.add_review(item.element_id, "unsupported_element", f"label {item.label!r}: {excerpt}",
                       target=item.element_id, suggested_action="add handling for this label or confirm it can be dropped")
        rec.add_log("label_check", item.element_id, f"label {item.label!r} has no normalizer; flagged for review")
    return result
