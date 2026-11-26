"""Dựng response cho màn "Tài liệu & chunk" từ dữ liệu repository (hàm thuần + ký URL ảnh)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.modules.chatbot.schemas.system import ChunkAsset
from app.modules.documents.repository import ChunkStats
from app.modules.documents.schemas import (
    ChunkImage,
    ChunkItem,
    DocumentBranch,
    DocumentDetail,
    DocumentFolder,
    DocumentSummary,
    DocumentTreeResponse,
    OutlineNode,
)

# Nhóm "Chưa xác định mục": đoạn mất cấp PART (lỗi in số mục của PDF, T-07) để cây không bị một gốc lạ mỗi đoạn.
UNKNOWN_SECTION = "Chưa xác định mục"


def status_of(row: Mapping[str, Any], stats: ChunkStats | None) -> str:
    if not row.get("doc_id"):
        return "idle"
    if stats is None or stats.chunks == 0:
        return "work" if row.get("sync_state") else "idle"
    return "live" if stats.approved >= stats.chunks else "review"


def summary(row: Mapping[str, Any], stats: ChunkStats | None) -> DocumentSummary:
    chunks = stats.chunks if stats else 0
    approved = stats.approved if stats else 0
    return DocumentSummary(
        crm_id=row["crm_id"], doc_id=row.get("doc_id"), name=row["name"], model=row.get("model"),
        document_type=row.get("document_type"), language=row.get("language"), version=row.get("version"),
        file_size=row.get("file_size"), crm_updated_at=row.get("crm_updated_at"), on_crm=bool(row.get("on_crm", True)),
        status=status_of(row, stats), chunk_count=chunks, approved_count=approved, pending_count=chunks - approved)


def tree(rows: Sequence[Mapping[str, Any]], stats: Mapping[str, ChunkStats]) -> DocumentTreeResponse:
    branches: dict[str, dict[str, list[DocumentSummary]]] = {}
    used: set[str] = set()
    for row in rows:
        folder = row.get("folder") or row["branch"]
        branches.setdefault(row["branch"], {}).setdefault(folder, []).append(
            summary(row, stats.get(row["doc_id"]) if row.get("doc_id") else None))
        if row.get("sync_mode") in ("build", "run_only") or row.get("doc_id"):
            used.add(row["branch"])
    out = [
        DocumentBranch(
            name=name, used_by_chatbot=name in used, document_count=sum(len(docs) for docs in folders.values()),
            folders=[DocumentFolder(name=folder, documents=docs) for folder, docs in folders.items()])
        for name, folders in branches.items()
    ]
    # Nhánh chatbot dùng lên đầu, sau đó theo tên.
    out.sort(key=lambda b: (not b.used_by_chatbot, b.name))
    seen = [row.get("last_seen_at") for row in rows if row.get("last_seen_at")]
    return DocumentTreeResponse(branches=out, document_count=len(rows), synced_at=max(seen) if seen else None)


def detail(row: Mapping[str, Any], stats: ChunkStats | None) -> DocumentDetail:
    base = summary(row, stats).model_dump()
    return DocumentDetail(
        **base, branch=row["branch"], folder=row.get("folder"), connection_types=list(row.get("connection_types") or []),
        doc_title=stats.doc_title if stats else None, doc_version=stats.doc_version if stats else None,
        page_count=stats.page_count if stats else None, image_chunk_count=stats.image_chunks if stats else 0)


def outline(paths: Sequence[tuple[list[str], int]]) -> list[OutlineNode]:
    """Cây mục từ section_path của các đoạn (giữ thứ tự xuất hiện); đếm đoạn cộng dồn lên mục cha."""
    roots: list[OutlineNode] = []
    index: dict[tuple[str, ...], OutlineNode] = {}
    for raw, count in paths:
        path = [p for p in raw if p] or [UNKNOWN_SECTION]
        if not path[0].upper().startswith("PART") and len(path) > 1:
            path = [UNKNOWN_SECTION, *path]
        for depth in range(1, len(path) + 1):
            key = tuple(path[:depth])
            node = index.get(key)
            if node is None:
                node = OutlineNode(title=path[depth - 1], path=list(key), chunk_count=0)
                index[key] = node
                (index[key[:-1]].children if depth > 1 else roots).append(node)
            node.chunk_count += count
    return roots


def _assets(raw: Any) -> list[ChunkAsset]:
    out = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, Mapping):
            try:
                out.append(ChunkAsset.model_validate(item))
            except ValueError:
                continue
    return out


async def chunk_items(rows: Sequence[Mapping[str, Any]], signer: Any, *, max_images: int = 3) -> list[ChunkItem]:
    """Đoạn của một trang, ảnh ký URL mới trong một lần gọi Storage (signer None → không có ảnh)."""
    per_row = [_assets(row.get("assets")) for row in rows]
    wanted = [asset for assets in per_row for asset in assets[:max_images]]
    signed: dict[tuple[str, str], str] = {}
    if signer is not None and wanted:
        try:
            signed = await signer.sign(wanted)
        except Exception:   # ký lỗi: trả đoạn không ảnh
            signed = {}
    items = []
    for row, assets in zip(rows, per_row):
        images = [ChunkImage(url=signed[(a.bucket, a.path)], page=a.page, printed_page=a.printed_page)
                  for a in assets[:max_images] if (a.bucket, a.path) in signed]
        items.append(ChunkItem(
            id=row["id"], chunk_key=row["chunk_key"], chunk_index=row["chunk_index"], chunk_type=row["chunk_type"],
            section_path=list(row.get("section_path") or []), section_title=row["section_title"],
            page_start=row.get("page_start"), page_end=row.get("page_end"),
            printed_page_start=row.get("printed_page_start"), printed_page_end=row.get("printed_page_end"),
            content=row["content"], summary_vi=row.get("summary_vi"), keywords=list(row.get("keywords") or []),
            review_status=row["review_status"], image_count=len(assets), images=images))
    return items
