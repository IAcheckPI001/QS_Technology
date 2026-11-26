"""Schema API đọc của màn "Tài liệu & chunk" (B6 phần đọc, 2026-11-26). Contract: docs/ai/api_guidelines.md."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Trạng thái rút gọn cho người dùng không chuyên (mock 5 v4):
# live: mọi đoạn đã duyệt · review: có đoạn chờ duyệt · work: đã tải PDF, chưa có đoạn · idle: chưa đưa vào chatbot.
DocumentStatus = Literal["live", "review", "work", "idle"]


class DocumentSummary(BaseModel):
    crm_id: str
    doc_id: str | None = None
    name: str
    model: str | None = None
    document_type: str | None = None
    language: str | None = None
    version: str | None = None
    file_size: int | None = None
    crm_updated_at: str | None = None
    on_crm: bool = True
    status: DocumentStatus
    chunk_count: int = 0
    approved_count: int = 0
    pending_count: int = 0


class DocumentFolder(BaseModel):
    name: str
    documents: list[DocumentSummary] = Field(default_factory=list)


class DocumentBranch(BaseModel):
    name: str
    # Nhánh có tài liệu đang đồng bộ cho chatbot (sổ nguồn); nhánh khác chỉ để xem.
    used_by_chatbot: bool
    document_count: int
    folders: list[DocumentFolder] = Field(default_factory=list)


class DocumentTreeResponse(BaseModel):
    branches: list[DocumentBranch]
    document_count: int
    # Lần đồng bộ gần nhất với CRM (max last_seen_at); null khi chưa đồng bộ với cây.
    synced_at: str | None = None


class DocumentDetail(DocumentSummary):
    branch: str
    folder: str | None = None
    connection_types: list[str] = Field(default_factory=list)
    doc_title: str | None = None
    doc_version: str | None = None      # phiên bản trong doc_chunks_v2 (bản đang dùng)
    page_count: int | None = None
    image_chunk_count: int = 0


class OutlineNode(BaseModel):
    title: str
    path: list[str]
    chunk_count: int
    children: list["OutlineNode"] = Field(default_factory=list)


class OutlineResponse(BaseModel):
    doc_id: str
    total: int
    nodes: list[OutlineNode]


class ChunkImage(BaseModel):
    url: str
    page: int | None = None
    printed_page: int | None = None


class ChunkItem(BaseModel):
    id: int
    chunk_key: str
    chunk_index: int
    chunk_type: str
    section_path: list[str] = Field(default_factory=list)
    section_title: str
    page_start: int | None = None
    page_end: int | None = None
    printed_page_start: int | None = None
    printed_page_end: int | None = None
    content: str
    summary_vi: str | None = None
    keywords: list[str] = Field(default_factory=list)
    review_status: Literal["draft", "approved"]
    image_count: int = 0
    # URL ký ngắn hạn (ASSET_URL_TTL_S); rỗng khi CHAT_SOURCES_ENABLED tắt.
    images: list[ChunkImage] = Field(default_factory=list)


class ChunkPage(BaseModel):
    doc_id: str
    total: int
    offset: int
    limit: int
    items: list[ChunkItem]
