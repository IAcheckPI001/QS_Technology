"""Ghi review_queue và normalization_log theo thứ tự deterministic (contract §5, §6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.modules.doc_ingest.schemas.normalized import LogEntry, ReviewCode, ReviewItem

Blocks = Literal["chunk", "fact", "publish", "none"]

# code -> (blocking, chặn bước nào); nguồn: contract §6.
REVIEW_POLICY: dict[ReviewCode, tuple[bool, Blocks]] = {
    "column_count_mismatch": (True, "chunk"),
    "unassigned_cell": (True, "chunk"),
    "unsupported_element": (True, "chunk"),
    "empty_table": (False, "none"),
    "ambiguous_continuation": (True, "chunk"),
    "header_demotion_unsure": (True, "chunk"),
    "header_missing": (True, "fact"),
    "complex_header": (True, "chunk"),
    "orphan_row": (True, "chunk"),
    "ocr_required": (True, "chunk"),
    "furniture_reclassified": (False, "none"),
    "furniture_unconfirmed": (False, "none"),
    "printed_page_conflict": (False, "none"),
    "text_coverage_gap": (True, "chunk"),
    "table_crosscheck_mismatch": (True, "chunk"),
    "column_type_inconsistent": (True, "chunk"),
    "applicability_note": (True, "fact"),
    "applicability_model_unmatched": (True, "fact"),
    "caption_ambiguous": (True, "chunk"),
    "watermark_conflict": (False, "none"),
    "param_unparseable": (True, "fact"),
    "range_too_long": (True, "fact"),
    "param_code_overlap": (True, "fact"),
    "list_orphan": (True, "fact"),
    "per_code_values": (True, "fact"),
    "doc_version_mismatch": (True, "publish"),
    "source_conflict": (True, "fact"),
}


@dataclass
class Recorder:
    review: list[ReviewItem] = field(default_factory=list)
    log: list[LogEntry] = field(default_factory=list)

    def add_review(self, element_id: str, code: ReviewCode, detail: str, *, target: str | None = None,
                   suggested_action: str | None = None) -> ReviewItem:
        blocking, blocks = REVIEW_POLICY[code]
        item = ReviewItem(item_id=f"rq-{len(self.review) + 1:04d}", element_id=element_id, code=code,
                          blocking=blocking, blocks=blocks, target=target, detail=detail,
                          suggested_action=suggested_action)
        self.review.append(item)
        return item

    def add_log(self, rule_id: str, element_id: str, reason: str, *, target: str | None = None,
                before: dict[str, object] | None = None, after: dict[str, object] | None = None) -> None:
        self.log.append(LogEntry(rule_id=rule_id, element_id=element_id, target=target,
                                 before=before or {}, after=after or {}, reason=reason))
