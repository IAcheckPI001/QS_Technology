"""Adapter `DraftChunk` → dòng bảng `doc_chunks_v2` (`backend/sql/doc_chunks_v2.sql`, D-009).

Thiết kế cột: `docs/ai/reports/p2_doc_chunks_schema_review.md` §10. Khác v1:
- cột riêng cho `doc_version`, `doc_title`, `chunk_key`, `chunk_role`, trang in, `source`, `review_status`,
  `source_run`; `codes` (mã chuẩn hóa để khớp chính xác, S-02);
- `review_status` tính ở đây (nơi có dữ liệu cổng), loader chỉ kiểm: `approved` khi cổng 2b đạt **không tạm**, verdict
  nội dung `ok` cho đúng `content_hash`, không có mã review chặn, và (chunk lá) làm giàu đã duyệt ở cổng 2c;
- không có `id`, `embedding`, `embedding_model`, `fts*`, `loaded_at` (loader/DB sinh); `parent_key` để loader đổi
  thành `parent_id`;
- không kiểm danh sách model (loader kiểm theo registry của dịch vụ chat — một nguồn).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.modules.doc_ingest.schemas.chunk import ChunkQuality, ChunkReviewFile, DraftChunk
from app.modules.doc_ingest.schemas.manifest import SCOPE_ORDER

SCHEMA = "doc_chunks_v2"
DOMAINS = ("technical_docs", "company_info", "product_catalog")
# Mã kỹ thuật dạng chung (không riêng hãng): "#" + số, hoặc 1–4 chữ + số, có thể ".HẬU_TỐ" và dấu +/-.
# Vd. #12010, M1920, X41, CN3, D4000, G54, AX1.ENA, PUL1+. Không nhận mã bắt đầu bằng số (24V) hay không có số (GND).
_CODE = re.compile(r"^(#|[A-Z]{1,4})(\d{1,6})((?:\.[A-Z0-9]+)?[+-]?)$")
MAX_RANGE_CODES = 64   # dải dài hơn chỉ giữ hai đầu (tránh một chunk bảng mang hàng trăm mã)


def normalize_code(text: str) -> str | None:
    """Dạng chuẩn để so khớp: chữ hoa, bỏ khoảng trắng, bỏ số 0 đầu (#0008 → #8). Không phải mã → None."""
    match = _CODE.match("".join(text.split()).upper())
    if match is None:
        return None
    prefix, digits, suffix = match.groups()
    return f"{prefix}{int(digits)}{suffix}"


def chunk_codes(chunk: DraftChunk) -> list[str]:
    """Mã của chunk: tham số (`param_refs`, dải được trải), mã I/O, nhãn hình đã xác minh; bỏ tên model."""
    models = {m.upper() for m in chunk.product_models}
    raw: list[str] = []
    for ref in chunk.param_refs:
        numbers = ref.codes
        if ref.kind == "range" and len(numbers) > MAX_RANGE_CODES:
            numbers = [n for n in (ref.range_start, ref.range_end) if n is not None]
        raw += [f"{ref.prefix}{n}" for n in numbers]
    raw += chunk.io_codes
    raw += [label.text for label in chunk.figure_labels if label.verified]
    out: list[str] = []
    for text in raw:
        code = normalize_code(text)
        if code is not None and code not in models and code not in out:
            out.append(code)
    return out


def _page(value: str | None) -> int | None:
    return int(value) if value is not None and value.strip().isdigit() else None


@dataclass(frozen=True)
class ApprovalContext:
    """Dữ liệu cổng của một lần build. `gate_2b_final`: cổng 2b đạt và không tạm (nhãn đã xác nhận)."""

    gate_2b_final: bool
    ok_hashes: dict[str, str] = field(default_factory=dict)   # chunk_key -> content_hash có verdict `ok`

    @classmethod
    def from_build(cls, quality: ChunkQuality, review: ChunkReviewFile | None) -> ApprovalContext:
        ok = {e.chunk_key: e.content_hash for e in (review.reviews if review else []) if e.verdict == "ok"}
        return cls(gate_2b_final=quality.gate_passed is True and not quality.provisional, ok_hashes=ok)


def review_status(chunk: DraftChunk, ctx: ApprovalContext) -> str:
    if not ctx.gate_2b_final or chunk.review_blockers:
        return "draft"
    if ctx.ok_hashes.get(chunk.chunk_key) != chunk.content_hash:
        return "draft"
    if chunk.chunk_role != "parent" and chunk.enrichment_status != "approved":
        return "draft"
    return "approved"


def to_row(chunk: DraftChunk, ctx: ApprovalContext, source_run: str | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "element_ids": chunk.element_ids, "extraction": chunk.extraction,
        "logical_table_id": chunk.logical_table_id, "row_ids": chunk.row_ids,
        "param_codes": [r.model_dump(mode="json") for r in chunk.param_refs], "io_codes": chunk.io_codes,
        "applicability_notes": [c.model_dump(mode="json") for c in chunk.applicability],
        "figure_labels": [lb.model_dump(mode="json") for lb in chunk.figure_labels],
        "related_chunk_keys": chunk.related_chunk_keys, "review_blockers": chunk.review_blockers,
        "review_notes": chunk.review_notes, "flags": chunk.flags,
        "enrichment": {"status": chunk.enrichment_status}, "faq_vi": chunk.faq_vi,
        # Trang in không phải số (vd. "iv") vẫn giữ nguyên văn ở đây.
        "printed_page_start": chunk.printed_page_start, "printed_page_end": chunk.printed_page_end,
    }
    return {
        "parent_key": chunk.parent_key,
        "doc_id": chunk.doc_id, "doc_version": chunk.doc_version, "doc_title": chunk.doc_title,
        "doc_type": chunk.doc_type, "lang": chunk.lang,
        "chunk_key": chunk.chunk_key, "chunk_index": chunk.chunk_index, "chunk_role": chunk.chunk_role,
        "chunk_type": chunk.chunk_type,
        "domain": chunk.domain, "scopes": list(chunk.scopes), "product_models": list(chunk.product_models),
        "applies_to_models": list(chunk.applies_to_models), "control_interface": list(chunk.control_interface),
        "spec_attributes": list(chunk.spec_attributes),
        "section_id": chunk.section_id, "section_path": list(chunk.section_path), "section_title": chunk.section_title,
        "page_start": chunk.page_start, "page_end": chunk.page_end,
        "printed_page_start": _page(chunk.printed_page_start), "printed_page_end": _page(chunk.printed_page_end),
        "content": chunk.content, "summary_vi": chunk.summary_vi, "keywords": list(chunk.keywords),
        "codes": chunk_codes(chunk),
        "embed_text": chunk.embed_text, "token_count": chunk.token_count, "content_hash": chunk.content_hash,
        "assets": [{"bucket": a.bucket, "path": a.path, "page": a.page, "printed_page": a.printed_page}
                   for a in chunk.assets],
        "metadata": {k: v for k, v in metadata.items() if v not in (None, [], {})},
        "source": chunk.source, "review_status": review_status(chunk, ctx), "is_active": chunk.is_active,
        "source_run": source_run,
    }


def row_errors(row: dict[str, Any]) -> list[str]:
    """Ràng buộc từng dòng của `doc_chunks_v2` (check, NOT NULL) mà adapter kiểm được (trừ danh sách model)."""
    key = row.get("chunk_key") or f"#{row.get('chunk_index')}"
    errors = []
    if row["domain"] not in DOMAINS:
        errors.append(f"{key}: domain lạ {row['domain']}")
    if not set(row["scopes"]) <= set(SCOPE_ORDER):
        errors.append(f"{key}: scopes ngoài {SCOPE_ORDER}")
    if (row["domain"] == "technical_docs") != (len(row["scopes"]) > 0):
        errors.append(f"{key}: technical_docs phải có scopes không rỗng")
    if row["domain"] == "technical_docs" and not row["product_models"]:
        errors.append(f"{key}: technical_docs phải có product_models")
    if row["chunk_role"] == "child" and not row["parent_key"]:
        errors.append(f"{key}: chunk con không có parent_key")
    for column in ("doc_id", "doc_version", "doc_title", "doc_type", "chunk_key", "chunk_type", "section_title",
                   "content", "embed_text", "content_hash"):
        if not row.get(column):
            errors.append(f"{key}: {column} rỗng")
    return errors


def set_errors(rows: Iterable[dict[str, Any]]) -> list[str]:
    """Ràng buộc trên cả bộ dòng: khóa và thứ tự không trùng; `parent_key` trỏ tới một chunk cha trong bộ."""
    rows = list(rows)
    errors = []
    for column in ("chunk_key", "chunk_index"):
        dup = [v for v, n in Counter(r[column] for r in rows).items() if n > 1]
        if dup:
            errors.append(f"{column} trùng (vi phạm unique): {dup[:5]}")
    parents = {r["chunk_key"] for r in rows if r["chunk_role"] == "parent"}
    for r in rows:
        if r["parent_key"] and r["parent_key"] not in parents:
            errors.append(f"{r['chunk_key']}: parent_key {r['parent_key']} không phải chunk cha trong bộ")
    return errors


def export_rows(chunks: Sequence[DraftChunk], ctx: ApprovalContext,
                source_run: str | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    rows = [to_row(c, ctx, source_run) for c in chunks]
    return rows, [e for row in rows for e in row_errors(row)] + set_errors(rows)
