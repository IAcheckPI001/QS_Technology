"""Route đọc của màn "Tài liệu & chunk" (Support Workspace). Chỉ transport: dữ liệu ở repository, dựng ở service.

Chưa có xác thực: chỉ mount khi `WORKSPACE_DOCUMENTS_API_ENABLED=true` (mặc định tắt, TR-16, DR-05).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session
from app.modules.chatbot.dependencies import get_asset_signer
from app.modules.documents import service
from app.modules.documents.crm_tree import CrmDocumentTree, CrmTreeError
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import ChunkPage, DocumentDetail, DocumentTreeResponse, OutlineResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspace/documents", tags=["workspace-documents"])


def get_document_repository(db: AsyncSession = Depends(get_db_session)) -> DocumentRepository:
    return DocumentRepository(db)


def get_crm_tree(request: Request) -> CrmDocumentTree:
    tree = getattr(request.app.state, "crm_document_tree", None)
    if tree is None:   # app tạo trong test không qua lifespan
        tree = CrmDocumentTree(settings.crm_docs_tree_url, settings.crm_docs_base_url, ttl_s=settings.crm_docs_cache_s)
        request.app.state.crm_document_tree = tree
    return tree


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": {"code": code, "message": message}})


def _db_down(what: str) -> JSONResponse:
    logger.exception("documents %s failed", what)
    return _error(503, "database_unavailable", "Document data could not be loaded. Please try again.")


@router.get("", response_model=DocumentTreeResponse)
async def list_documents(repository: DocumentRepository = Depends(get_document_repository)):
    """Cây nhóm › thư mục › tài liệu với trạng thái rút gọn và số đoạn (đã duyệt / chờ duyệt)."""
    try:
        rows = await repository.documents()
        stats = await repository.stats([row["doc_id"] for row in rows if row.get("doc_id")])
    except SQLAlchemyError:
        return _db_down("list")
    return service.tree(rows, stats)


async def _document(repository: DocumentRepository, doc_id: str):
    row = await repository.document(doc_id)
    if row is None:
        return None, None
    stats = (await repository.stats([doc_id])).get(doc_id)
    return row, stats


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(doc_id: str, repository: DocumentRepository = Depends(get_document_repository)):
    try:
        row, stats = await _document(repository, doc_id)
    except SQLAlchemyError:
        return _db_down("detail")
    if row is None:
        return _error(404, "document_not_found", "No document with this doc_id.")
    return service.detail(row, stats)


@router.get("/{doc_id}/outline", response_model=OutlineResponse)
async def get_outline(doc_id: str, repository: DocumentRepository = Depends(get_document_repository)):
    try:
        row, stats = await _document(repository, doc_id)
        if row is None:
            return _error(404, "document_not_found", "No document with this doc_id.")
        paths = await repository.section_paths(doc_id, stats.doc_version) if stats and stats.doc_version else []
    except SQLAlchemyError:
        return _db_down("outline")
    return OutlineResponse(doc_id=doc_id, total=sum(n for _, n in paths), nodes=service.outline(paths))


@router.get("/{doc_id}/chunks", response_model=ChunkPage)
async def list_chunks(
    doc_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status: Literal["draft", "approved"] | None = Query(default=None),
    has_images: bool = Query(default=False),
    q: str | None = Query(default=None, max_length=200),
    section: list[str] = Query(default=[]),
    repository: DocumentRepository = Depends(get_document_repository),
    signer=Depends(get_asset_signer),
):
    """Đoạn kiến thức theo `chunk_index` (phân trang offset); `section` lặp lại = đường dẫn mục để lọc theo mục."""
    try:
        row, stats = await _document(repository, doc_id)
        if row is None:
            return _error(404, "document_not_found", "No document with this doc_id.")
        if not stats or not stats.doc_version:
            return ChunkPage(doc_id=doc_id, total=0, offset=offset, limit=limit, items=[])
        total, rows = await repository.chunks(
            doc_id, stats.doc_version, offset=offset, limit=limit, status=status, has_images=has_images,
            q=(q or "").strip() or None, section=section or None)
    except SQLAlchemyError:
        return _db_down("chunks")
    items = await service.chunk_items(rows, signer, max_images=settings.source_images_max)
    return ChunkPage(doc_id=doc_id, total=total, offset=offset, limit=limit, items=items)


@router.get("/{doc_id}/pdf")
async def open_pdf(
    doc_id: str,
    mode: Literal["view", "download"] = Query(default="view"),
    repository: DocumentRepository = Depends(get_document_repository),
    crm_tree: CrmDocumentTree = Depends(get_crm_tree),
):
    """Chuyển hướng (307) tới link xem/tải PDF của CRM, xin mới mỗi lần (URL ký không lưu)."""
    try:
        row = await repository.document(doc_id)
    except SQLAlchemyError:
        return _db_down("pdf")
    if row is None:
        return _error(404, "document_not_found", "No document with this doc_id.")
    try:
        url = await crm_tree.pdf_url(row["crm_id"], mode)
    except CrmTreeError:
        return _error(502, "crm_unavailable", "The CRM document service could not be reached.")
    if url is None:
        return _error(404, "pdf_not_found", "This document is no longer available on the CRM.")
    return RedirectResponse(url, status_code=307)
