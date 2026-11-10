"""Adapter `DraftChunk` → dòng bảng `doc_chunks` hiện tại (`backend/sql/doc_chunks.sql`, contract C2 §1, §4, §13).

Bảng hiện tại là **mốc**: trường ứng viên (§13) chưa có cột được gói vào `metadata`. Schema đổi → thêm adapter
v2, không build lại. Không có `id`, `embedding`, `fts` (DB sinh/tính khi nạp); `parent_key` để loader đổi thành
`parent_id`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.modules.doc_ingest.schemas.chunk import DraftChunk
from app.modules.doc_ingest.schemas.manifest import SCOPE_ORDER

SCHEMA = "doc_chunks_v1"
DOMAINS = ("technical_docs", "company_info", "product_catalog")


def to_row(chunk: DraftChunk) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "chunk_key": chunk.chunk_key, "parent_key": chunk.parent_key, "chunk_role": chunk.chunk_role,
        "source": chunk.source, "doc_title": chunk.doc_title, "doc_version": chunk.doc_version,
        "element_ids": chunk.element_ids, "printed_page_start": chunk.printed_page_start,
        "printed_page_end": chunk.printed_page_end, "extraction": chunk.extraction,
        "logical_table_id": chunk.logical_table_id, "row_ids": chunk.row_ids,
        "param_codes": [r.model_dump(mode="json") for r in chunk.param_refs], "io_codes": chunk.io_codes,
        "applicability_notes": [c.model_dump(mode="json") for c in chunk.applicability],
        "applies_to_models": chunk.applies_to_models,
        "figure_labels": [lb.model_dump(mode="json") for lb in chunk.figure_labels],
        "related_chunk_keys": chunk.related_chunk_keys, "review_blockers": chunk.review_blockers,
        "review_notes": chunk.review_notes, "flags": chunk.flags,
        "enrichment": {"status": chunk.enrichment_status}, "faq_vi": chunk.faq_vi,
    }
    return {
        "parent_key": chunk.parent_key,
        "domain": chunk.domain, "scopes": list(chunk.scopes), "product_models": list(chunk.product_models),
        "control_interface": list(chunk.control_interface), "spec_attributes": list(chunk.spec_attributes),
        "chunk_type": chunk.chunk_type, "is_active": chunk.is_active, "doc_id": chunk.doc_id,
        "doc_type": chunk.doc_type, "lang": chunk.lang, "section_id": chunk.section_id,
        "section_path": list(chunk.section_path), "section_title": chunk.section_title,
        "page_start": chunk.page_start, "page_end": chunk.page_end, "chunk_index": chunk.chunk_index,
        "assets": [{"bucket": a.bucket, "path": a.path, "page": a.page, "printed_page": a.printed_page}
                   for a in chunk.assets],
        "metadata": {k: v for k, v in metadata.items() if v not in (None, [], {})},
        "content": chunk.content, "summary_vi": chunk.summary_vi, "keywords": list(chunk.keywords),
        "embed_text": chunk.embed_text, "token_count": chunk.token_count, "content_hash": chunk.content_hash,
    }


def row_errors(row: dict[str, Any], models: Sequence[str]) -> list[str]:
    """Ràng buộc của bảng `doc_chunks` (check constraint, NOT NULL) mà một dòng phải thỏa."""
    errors = []
    key = row.get("metadata", {}).get("chunk_key", f"#{row.get('chunk_index')}")
    if row["domain"] not in DOMAINS:
        errors.append(f"{key}: domain lạ {row['domain']}")
    if not set(row["scopes"]) <= set(SCOPE_ORDER):
        errors.append(f"{key}: scopes ngoài {SCOPE_ORDER}")
    if (row["domain"] == "technical_docs") != (len(row["scopes"]) > 0):
        errors.append(f"{key}: technical_docs phải có scopes không rỗng")
    if row["domain"] == "technical_docs" and not row["product_models"]:
        errors.append(f"{key}: technical_docs phải có product_models")
    if not set(row["product_models"]) <= set(models):
        errors.append(f"{key}: product_models ngoài registry: {sorted(set(row['product_models']) - set(models))}")
    for column in ("section_title", "content", "embed_text", "content_hash", "doc_id", "doc_type", "chunk_type"):
        if not row.get(column):
            errors.append(f"{key}: {column} rỗng")
    return errors


def export_rows(chunks: Sequence[DraftChunk], models: Sequence[str]) -> tuple[list[dict[str, Any]], list[str]]:
    rows = [to_row(c) for c in chunks]
    errors = [e for row in rows for e in row_errors(row, models)]
    indexes = [r["chunk_index"] for r in rows]
    if len(set(indexes)) != len(indexes):
        errors.append("chunk_index trùng (vi phạm unique(doc_id, chunk_index))")
    return rows, errors
