"""Cổng 2c — duyệt mẫu làm giàu tiếng Việt (contract C2 §10).

- `select_sample`: mẫu ~30 chunk lá phân tầng theo loại + mọi chunk có cờ kiểm làm giàu, bỏ chunk thí điểm;
- `mark_sample`: ghi `enrichment_verdict = pending` (+ phiên bản) vào `chunk_review.json`;
- `sample_counts`: đếm verdict mẫu còn hiệu lực (cùng phiên bản làm giàu hiện tại của chunk);
- `gate_2c`: tự động đạt + 0 lỗi nặng + ≥ `OK_RATIO` mẫu `ok`, không còn mẫu chờ.
Không gọi LLM.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.modules.doc_ingest.build.loader import EnrichKey, enrichment_key
from app.modules.doc_ingest.enrich.runner import stratified
from app.modules.doc_ingest.schemas.chunk import ChunkReviewFile, DraftChunk, EnrichmentRecord

SAMPLE_SIZE = 30
OK_RATIO = 0.9
FLAG_CHECKS = frozenset({"faq_meta", "glossary_term_missing", "summary_preamble", "enrich_code_mismatch"})
FLAG_CHUNK = frozenset({"enrich_trimmed", "enrich_code_mismatch"})


def select_sample(chunks: Sequence[DraftChunk], records: Mapping[EnrichKey, EnrichmentRecord], size: int = SAMPLE_SIZE,
                  exclude: frozenset[EnrichKey] = frozenset()) -> list[DraftChunk]:
    """Chunk lá đã làm giàu, mỗi khóa làm giàu một lần, không thuộc `exclude` (vd. chunk thí điểm). Lấy mọi chunk có
    cờ kiểm (record.checks hoặc cờ chunk), phần còn lại chia phân tầng theo loại chunk (`runner.stratified`)."""
    pool, seen = [], set()
    for c in chunks:
        key = enrichment_key(c.content_hash, c.section_path)
        if c.chunk_role == "parent" or key not in records or key in exclude or key in seen:
            continue
        seen.add(key)
        pool.append(c)
    flagged = [c for c in pool if FLAG_CHECKS & set(records[enrichment_key(c.content_hash, c.section_path)].checks)
               or FLAG_CHUNK & set(c.flags)]
    rest = [c for c in pool if c not in flagged]
    picked = flagged[:size] + stratified(rest, max(0, size - len(flagged)))
    return sorted(picked, key=lambda c: c.chunk_index)


def mark_sample(review: ChunkReviewFile, sample: Sequence[DraftChunk],
                records: Mapping[EnrichKey, EnrichmentRecord]) -> int:
    """Đánh dấu mẫu `pending` (giữ verdict đã có nếu cùng phiên bản). Trả về số mục mới đánh dấu."""
    keys = {c.chunk_key: c for c in sample}
    marked = 0
    for entry in review.reviews:
        chunk = keys.get(entry.chunk_key)
        if chunk is None:
            continue
        version = records[enrichment_key(chunk.content_hash, chunk.section_path)].prompt_version
        if entry.enrichment_verdict in ("ok", "fix") and entry.enrichment_version == version:
            continue
        entry.enrichment_verdict, entry.enrichment_version = "pending", version
        entry.enrichment_note, entry.enrichment_severe = "", False
        marked += 1
    return marked


@dataclass
class SampleCounts:
    sample: int = 0
    ok: int = 0
    fix: list[str] = field(default_factory=list)
    pending: int = 0
    severe: list[str] = field(default_factory=list)


def sample_counts(chunks: Sequence[DraftChunk], review: ChunkReviewFile | None,
                  records: Mapping[EnrichKey, EnrichmentRecord]) -> SampleCounts:
    """Verdict mẫu còn hiệu lực: chunk còn nguyên `content_hash` và cùng phiên bản làm giàu với bản ghi hiện tại."""
    out = SampleCounts()
    if review is None:
        return out
    current = {c.chunk_key: c for c in chunks if c.chunk_role != "parent"}
    for e in review.reviews:
        chunk = current.get(e.chunk_key)
        if e.enrichment_verdict == "none" or chunk is None or chunk.content_hash != e.content_hash:
            continue
        record = records.get(enrichment_key(chunk.content_hash, chunk.section_path))
        if record is None or record.prompt_version != e.enrichment_version:
            continue   # làm giàu đã đổi phiên bản → verdict hết hạn
        out.sample += 1
        if e.enrichment_verdict == "ok":
            out.ok += 1
        elif e.enrichment_verdict == "fix":
            out.fix.append(e.chunk_key)
            if e.enrichment_severe:
                out.severe.append(e.chunk_key)
        else:
            out.pending += 1
    return out


def gate_2c(auto_passed: bool | None, counts: SampleCounts) -> bool | None:
    """None khi chưa làm giàu, chưa có mẫu hoặc mẫu còn chờ duyệt."""
    if auto_passed is None or counts.sample == 0 or counts.pending:
        return None
    return bool(auto_passed and not counts.severe and counts.ok >= OK_RATIO * counts.sample)


def leaf_versions(chunks: Sequence[DraftChunk], records: Mapping[EnrichKey, EnrichmentRecord]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in chunks:
        key = enrichment_key(c.content_hash, c.section_path)
        if c.chunk_role != "parent" and key in records:
            v = records[key].prompt_version
            out[v] = out.get(v, 0) + 1
    return out
