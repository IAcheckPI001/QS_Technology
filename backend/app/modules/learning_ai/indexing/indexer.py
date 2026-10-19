"""Đồng bộ record ĐÃ DUYỆT sang index truy xuất. Idempotent, có thể chạy lại toàn bộ.

Kích hoạt bởi outbox event (record_approved / record_superseded / record_archived / registry_changed
/ embedding_model_changed) — KHÔNG gọi trực tiếp trong request duyệt để tránh dual-write.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence
from uuid import UUID

from ..chunking.chunk_builder import build_chunks
from ..schemas.derived import Chunk
from ..schemas.knowledge_record import KnowledgeRecord, RecordStatus, Visibility
from ..schemas.registry import RegistrySnapshot


class Embedder(Protocol):
    model_id: str                                   # vd "text-embedding-3-large@2024-01"
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class SearchIndex(Protocol):
    """Một index = (chunk, vector theo embedding_model, filters, full-text). Vd Postgres+pgvector+tsvector."""
    def existing_hashes(self, record_id: UUID, embedding_model: str) -> dict[str, str]: ...
    def upsert(self, chunks: Sequence[Chunk], vectors: dict[str, list[float]], embedding_model: str) -> None: ...
    def delete_record(self, record_id: UUID, keep_chunk_ids: set[str] = frozenset()) -> int: ...


@dataclass
class SyncResult:
    record_id: UUID
    upserted: int = 0
    reused: int = 0
    deleted: int = 0
    skipped_reason: str | None = None


def is_indexable(record: KnowledgeRecord) -> str | None:
    if record.lifecycle.status != RecordStatus.APPROVED:
        return f"status={record.lifecycle.status.value}"
    if record.privacy.visibility != Visibility.INTERNAL:
        return "visibility=restricted"
    return None


def sync_record(record: KnowledgeRecord, reg: RegistrySnapshot, index: SearchIndex,
                embedder: Embedder) -> SyncResult:
    res = SyncResult(record.record_id)
    reason = is_indexable(record)
    if reason:
        res.deleted = index.delete_record(record.record_id)
        res.skipped_reason = reason
        return res

    chunks = build_chunks(record, reg)
    have = index.existing_hashes(record.record_id, embedder.model_id)
    stale = [c for c in chunks if have.get(c.chunk_id) != c.embedding_text_hash]
    vectors = dict(zip([c.chunk_id for c in stale], embedder.embed([c.embedding_text for c in stale]))) if stale else {}

    index.upsert(chunks, vectors, embedder.model_id)          # upsert mới trước …
    res.deleted = index.delete_record(record.record_id, keep_chunk_ids={c.chunk_id for c in chunks})  # … rồi dọn cũ
    res.upserted, res.reused = len(stale), len(chunks) - len(stale)
    return res
