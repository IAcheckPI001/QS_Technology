"""Đánh giá chất lượng chunk Bước 2b (contract C2 §10): độ phủ, ranh giới theo nhãn mẫu, so với chunk viết tay.

Không LLM, không embedding. So với chunk viết tay chỉ là báo cáo, không làm cổng.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from app.modules.doc_ingest.build.chunker import Chunker, ChunkPlan
from app.modules.doc_ingest.eval.labels import ChunkLabels
from app.modules.doc_ingest.schemas.chunk import (
    BoundaryMatch, BoundaryScore, ChunkReviewFile, Coverage, DraftChunk, GateItem, ManualComparison, ManualMatch,
    ReviewSummary, CheckResult,
)

_WORD = re.compile(r"[0-9a-z]+")
MANUAL_THRESHOLD = 0.6


def _leaves(chunks: Sequence[DraftChunk]) -> list[DraftChunk]:
    return [c for c in chunks if c.chunk_role != "parent"]


def coverage(chunks: Sequence[DraftChunk], chunker: Chunker, plan: ChunkPlan) -> Coverage:
    """Mọi phần tử cần chunk nằm trong đúng một chunk lá. Bảng kiểm theo dòng (CQ-02), không theo segment."""
    heading_only = set(plan.heading_only)
    excluded = Counter(plan.excluded)
    excluded["heading_only"] = len(heading_only)
    required = [e for e in chunker.elements if chunker.exclusion(e) is None
                and e.normalized_type != "table_segment" and e.element_id not in heading_only]
    count: Counter[str] = Counter(e for c in _leaves(chunks) for e in c.element_ids)
    missing = [e.element_id for e in required if count[e.element_id] == 0]
    duplicated = [e.element_id for e in required if count[e.element_id] > 1]
    chars_total = sum(len(e.text or "") for e in required)
    chars_kept = sum(len(e.text or "") for e in required if count[e.element_id] > 0)
    return Coverage(required=len(required), covered=len(required) - len(missing), missing=missing,
                    duplicated=duplicated, excluded=dict(sorted((k, v) for k, v in excluded.items() if v)),
                    chars_total=chars_total, chars_kept=chars_kept,
                    char_ratio=round(chars_kept / chars_total, 4) if chars_total else None)


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def boundaries(chunks: Sequence[DraftChunk], labels: ChunkLabels) -> BoundaryScore | None:
    pages = list(labels.pages)
    if not pages:
        return None
    leaves = [c for c in _leaves(chunks) if c.logical_table_id is None]   # nhóm dòng bảng không gán nhãn ranh giới
    page_set = {p.page for p in pages}
    details: list[BoundaryMatch] = []
    hits: Counter[str] = Counter()
    for page in pages:
        for exp in page.expected_chunks:
            start, end = _norm(exp.start), _norm(exp.end)
            candidates = [c for c in leaves if start in _norm(c.content) and end in _norm(c.content)]
            # tài liệu có đoạn lặp nguyên văn ở mục khác: ưu tiên chunk bắt đầu trên trang của nhãn
            on_page = [c for c in candidates if c.page_start == page.page]
            best = min(on_page or candidates, key=lambda c: len(c.content), default=None)
            if best is not None:
                hits[best.chunk_key] += 1
            details.append(BoundaryMatch(page=page.page, chunk_type=exp.chunk_type, start=exp.start, end=exp.end,
                                         matched_key=best.chunk_key if best else None,
                                         matched_type=best.chunk_type if best else None))
    exclusive = {k for k, n in hits.items() if n == 1}
    matched = [d for d in details if d.matched_key in exclusive]
    on_pages = [c for c in leaves if c.page_start in page_set]
    chunks_matched = [c for c in on_pages if c.chunk_key in exclusive]
    expected = len(details)
    return BoundaryScore(
        labels_verified=labels.verified, pages=sorted(page_set), expected=expected, matched=len(matched),
        type_correct=sum(1 for d in matched if d.matched_type == d.chunk_type), chunks_on_pages=len(on_pages),
        chunks_matched=len(chunks_matched),
        precision=round(len(chunks_matched) / len(on_pages), 4) if on_pages else None,
        recall=round(len(matched) / expected, 4) if expected else None,
        type_accuracy=round(sum(1 for d in matched if d.matched_type == d.chunk_type) / len(matched), 4)
        if matched else None,
        details=details, unmatched_chunks=[c.chunk_key for c in on_pages if c.chunk_key not in exclusive])


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.casefold()) if len(w) >= 2}


def manual_comparison(chunks: Sequence[DraftChunk], csv_path: Path, doc_id: str) -> ManualComparison | None:
    """Mỗi chunk viết tay ↔ chunk builder (lá) chứa nhiều token của nó nhất."""
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("doc_id") == doc_id]
    if not rows:
        return None
    leaves = _leaves(chunks)
    leaf_words = {c.chunk_key: _words(c.content) for c in leaves}
    matches: list[ManualMatch] = []
    best_keys: set[str] = set()
    for row in rows:
        words = _words(row.get("content", ""))
        page = int(row["page_start"]) if (row.get("page_start") or "").isdigit() else None
        scored = [(len(words & leaf_words[c.chunk_key]) / len(words) if words else 0.0, c) for c in leaves]
        score, best = max(scored, key=lambda x: x[0], default=(0.0, None))
        same_page = set().union(*(leaf_words[c.chunk_key] for c in leaves
                                  if page is not None and c.page_start <= page <= c.page_end)) if leaves else set()
        if best is not None and score > 0:
            best_keys.add(best.chunk_key)
        matches.append(ManualMatch(
            manual_index=int(row.get("chunk_index") or 0), manual_type=row.get("chunk_type", ""),
            manual_title=row.get("section_title", ""), manual_page=page, manual_chars=len(row.get("content", "")),
            best_key=best.chunk_key if best is not None and score > 0 else None,
            best_type=best.chunk_type if best is not None and score > 0 else None, containment=round(score, 3),
            union_containment=round(len(words & same_page) / len(words), 3) if words else 0.0))
    return ManualComparison(
        csv_path=str(csv_path), doc_id=doc_id, manual_chunks=len(rows), builder_chunks=len(leaves),
        covered=sum(1 for m in matches if m.containment >= MANUAL_THRESHOLD), threshold=MANUAL_THRESHOLD,
        matches=matches, builder_unmatched=[c.chunk_key for c in leaves if c.chunk_key not in best_keys],
        manual_types=dict(sorted(Counter(r.get("chunk_type", "") for r in rows).items())),
        builder_types=dict(sorted(Counter(c.chunk_type for c in leaves).items())))


def review_summary(chunks: Sequence[DraftChunk], review: ChunkReviewFile | None) -> ReviewSummary:
    if review is None:
        return ReviewSummary(pending=len(chunks))
    current = {c.chunk_key: c.content_hash for c in chunks}
    summary = ReviewSummary()
    for entry in review.reviews:
        if entry.chunk_key not in current:
            continue
        if entry.verdict != "pending" and current[entry.chunk_key] != entry.content_hash:
            summary.stale += 1
            continue
        if entry.verdict == "ok":
            summary.ok += 1
        elif entry.verdict == "fix":
            summary.fix += 1
            summary.open_fix.append(entry.chunk_key)
        else:
            summary.pending += 1
    reviewed = {e.chunk_key for e in review.reviews}
    summary.pending += sum(1 for key in current if key not in reviewed)
    return summary


def gate(checks: Sequence[CheckResult], cov: Coverage | None, bound: BoundaryScore | None,
         review: ReviewSummary) -> tuple[list[GateItem], bool | None, bool]:
    failed = [c.check_id for c in checks if c.passed is False]
    items = [
        GateItem(name="CQ-01…CQ-10, CQ-RB đạt", value=len(failed), threshold="0 kiểm không đạt",
                 passed=not failed),
        GateItem(name="Độ phủ phần tử", value=cov.char_ratio if cov else None, threshold="= 1,0 và 0 lặp",
                 passed=None if cov is None or cov.char_ratio is None
                 else cov.char_ratio == 1.0 and not cov.missing and not cov.duplicated),
        GateItem(name="Ranh giới: precision", value=bound.precision if bound else None, threshold="≥ 0,9",
                 passed=None if bound is None or bound.precision is None else bound.precision >= 0.9),
        GateItem(name="Ranh giới: recall", value=bound.recall if bound else None, threshold="≥ 0,9",
                 passed=None if bound is None or bound.recall is None else bound.recall >= 0.9),
        GateItem(name="Duyệt tay: lỗi fix còn mở", value=review.fix,
                 threshold="0, và đã có chunk được duyệt ok",
                 passed=False if review.fix else (True if review.ok else None)),
    ]
    values = [i.passed for i in items]
    passed = False if False in values else (True if all(v is True for v in values) else None)
    provisional = bound is None or not bound.labels_verified or review.ok == 0
    return items, passed, provisional
