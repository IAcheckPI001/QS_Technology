"""Dữ liệu dẫn xuất từ KnowledgeRecord. Có thể xóa và tạo lại bất cứ lúc nào.

Vector KHÔNG nằm trong Chunk: vector được lưu ở vector index với khóa
(chunk_id, embedding_model) để nhiều embedding model có thể cùng tồn tại khi migrate.
"""
from __future__ import annotations

import hashlib
from uuid import UUID

from pydantic import Field

from .common import ApplicabilityScope, StrictModel

CHUNK_BUILDER_VERSION = "cb-1.0"


class ChunkFilters(StrictModel):
    """Metadata phi chuẩn hóa (denormalized) để filter trong hybrid search."""
    knowledge_type: str
    intents: list[str]
    topic: str
    scope: ApplicabilityScope
    product_models: list[str]          # đã mở rộng từ model_family nếu có
    excluded_models: list[str]
    control_interface: list[str]
    spec_attribute: list[str]
    connector_ids: list[str]
    parameter_ids: list[str]
    alarm_codes: list[str]
    registry_version: str


class Chunk(StrictModel):
    chunk_id: str
    record_id: UUID
    revision_id: UUID
    record_version: int
    record_content_hash: str
    builder_version: str = CHUNK_BUILDER_VERSION
    chunk_index: int
    chunk_count: int
    section: str = Field(description="'full' | 'steps:1-6' | 'cause:2' | 'connector:CN1'")
    display_text: str = Field(description="Văn bản đưa vào context trả lời: đã kèm header điều kiện + cảnh báo")
    embedding_text: str
    embedding_text_hash: str
    filters: ChunkFilters
    prev_chunk_id: str | None = None
    next_chunk_id: str | None = None

    @staticmethod
    def make_id(revision_id: UUID, section: str, builder_version: str = CHUNK_BUILDER_VERSION) -> str:
        """Deterministic: cùng revision + cùng section + cùng builder → cùng ID → upsert idempotent."""
        return hashlib.sha1(f"{revision_id}|{section}|{builder_version}".encode()).hexdigest()[:24]

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
