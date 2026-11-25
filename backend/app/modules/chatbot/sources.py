"""Nguồn đã trích dẫn của một lượt trả lời, kèm ảnh (D-014 giai đoạn B, event SSE `sources`; WU-17 đợt 2).

Ảnh do backend đính kèm theo chunk mà câu trả lời thực sự trích dẫn (`[S#]`); model không sinh URL. Lượt chỉ lưu
tham chiếu ảnh (bucket, path, trang) trong `retrieval_snapshot.chunks[].assets`; URL ký ngắn hạn được cấp lúc dựng
event và lại cấp mới mỗi lần đọc lịch sử (`/history`, `/retrieval`), không bao giờ lưu.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.modules.chatbot.providers.supabase_storage import AssetKey, AssetSigner
from app.modules.chatbot.schemas.history import (
    ChatHistoryItem,
    ChunkResult,
    RetrievalSnapshotResponse,
    SourceImage,
    SourceItem,
)
from app.modules.chatbot.schemas.system import ChunkAsset, ChunkHit

logger = logging.getLogger(__name__)

__all__ = [
    "SourceImage", "SourceItem", "attach_chunk_images", "attach_history_sources", "build_sources", "chunk_assets", "cited_source_ids", "sign_chunk_images",
    "sign_turn_sources", "snapshot_sources",
]

_BRACKET = re.compile(r"\[([^\[\]]*\bS\d+\b[^\[\]]*)\]")
_SOURCE_ID = re.compile(r"\bS(\d+)\b")


@dataclass
class _Source:
    """Nguồn trước khi ký ảnh: từ ChunkHit (lượt đang chạy) hoặc từ chunk đã lưu trong snapshot."""

    source_id: str
    title: str
    doc_id: str
    pages: str | None
    assets: list[ChunkAsset] = field(default_factory=list)


def cited_source_ids(answer: str) -> list[str]:
    """Mã nguồn có trong câu trả lời theo thứ tự xuất hiện, không trùng; hiểu `[S1]`, `[S1, S2]`."""
    found: list[str] = []
    for bracket in _BRACKET.findall(answer or ""):
        for number in _SOURCE_ID.findall(bracket):
            source_id = f"S{int(number)}"
            if source_id not in found:
                found.append(source_id)
    return found


def _page_range(start: int | None, end: int | None) -> str | None:
    if start is None:
        return None
    if end is None or end == start:
        return str(start)
    return f"{start}-{end}"


def chunk_assets(raw: Any) -> list[ChunkAsset]:
    """Tham chiếu ảnh đã lưu trong snapshot; bỏ phần tử sai dạng (bản ghi cũ hoặc hỏng)."""
    assets = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, Mapping):
            try:
                assets.append(ChunkAsset.model_validate(item))
            except ValueError:
                continue
    return assets


def _cited(sources: Iterable[_Source], answer: str) -> list[_Source]:
    by_id: dict[str, _Source] = {}
    for source in sources:
        if source.source_id and source.source_id not in by_id:
            by_id[source.source_id] = source
    return [by_id[source_id] for source_id in cited_source_ids(answer) if source_id in by_id]


def _items(selected: Sequence[_Source], signed: Mapping[AssetKey, str], max_images: int) -> list[SourceItem]:
    items = []
    for source in selected:
        images = [
            SourceImage(url=signed[(asset.bucket, asset.path)], page=asset.page, printed_page=asset.printed_page)
            for asset in source.assets[:max(max_images, 0)]
            if (asset.bucket, asset.path) in signed
        ]
        items.append(SourceItem(
            source_id=source.source_id, title=source.title, doc_id=source.doc_id, pages=source.pages, images=images))
    return items


async def _sign(signer: AssetSigner | None, assets: Iterable[ChunkAsset]) -> dict[AssetKey, str]:
    wanted = list(assets)
    if signer is None or not wanted:
        return {}
    try:
        return await signer.sign(wanted)
    except Exception as error:   # ký lỗi: trả nguồn không ảnh, không làm hỏng response
        logger.warning("asset signing failed error=%s", type(error).__name__)
        return {}


async def build_sources(
    hits: Sequence[ChunkHit],
    answer: str,
    signer: AssetSigner | None,
    *,
    max_images: int = 3,
) -> list[SourceItem]:
    """Nguồn được trích dẫn trong `answer`. `signer` None → không có ảnh (vẫn trả danh sách nguồn)."""
    selected = _cited(
        (_Source(hit.source_id or "", hit.section_title, hit.doc_id, _page_range(hit.page_start, hit.page_end),
                 list(hit.assets)) for hit in hits),
        answer,
    )
    if not selected:
        return []
    signed = await _sign(signer, (a for source in selected for a in source.assets[:max(max_images, 0)]))
    return _items(selected, signed, max_images)


def snapshot_sources(snapshot: Any, answer: str | None) -> list[_Source]:
    """Nguồn được trích dẫn của một lượt đã lưu (chưa ký ảnh). Lượt cũ thiếu `source_id`/tiêu đề → rỗng."""
    chunks = snapshot.get("chunks") if isinstance(snapshot, Mapping) else None
    candidates = []
    for chunk in chunks if isinstance(chunks, list) else []:
        if not isinstance(chunk, Mapping):
            continue
        source_id, title, doc_id = chunk.get("source_id"), chunk.get("section_title"), chunk.get("doc_id")
        if not (isinstance(source_id, str) and isinstance(title, str) and isinstance(doc_id, str)):
            continue
        candidates.append(_Source(source_id, title, doc_id, _page_range(chunk.get("page_start"), chunk.get("page_end")),
                                  chunk_assets(chunk.get("assets"))))
    return _cited(candidates, answer or "")


async def sign_turn_sources(
    turns: Mapping[Any, list[_Source]], signer: AssetSigner | None, *, max_images: int = 3,
) -> dict[Any, list[SourceItem]]:
    """Ký ảnh cho nguồn của nhiều lượt bằng một lần gọi (theo bucket) và trả SourceItem theo khoá của lượt."""
    signed = await _sign(signer, (
        a for sources in turns.values() for source in sources for a in source.assets[:max(max_images, 0)]))
    return {key: _items(sources, signed, max_images) for key, sources in turns.items()}


async def attach_history_sources(
    items: Sequence[ChatHistoryItem], rows: Sequence[Any], signer: AssetSigner | None, *, max_images: int = 3,
) -> list[ChatHistoryItem]:
    """GET /history: gắn nguồn được trích dẫn (kèm ảnh ký mới) vào từng lượt; `rows` cùng thứ tự với `items`."""
    turns = {
        item.id: snapshot_sources(getattr(row, "retrieval_snapshot", None), item.answer)
        for item, row in zip(items, rows)
        if item.answer
    }
    turns = {key: sources for key, sources in turns.items() if sources}
    if not turns:
        return list(items)
    signed = await sign_turn_sources(turns, signer, max_images=max_images)
    return [item.model_copy(update={"cited_sources": signed[item.id]}) if item.id in signed else item for item in items]


async def attach_chunk_images(
    response: RetrievalSnapshotResponse, row: Any, signer: AssetSigner | None, *, max_images: int = 3,
) -> RetrievalSnapshotResponse:
    """GET /retrieval: gắn ảnh (URL ký mới) vào các đoạn của lượt."""
    if signer is None or not response.chunks:
        return response
    chunks = await sign_chunk_images(
        response.chunks, getattr(row, "retrieval_snapshot", None), signer, max_images=max_images)
    return response.model_copy(update={"chunks": chunks})


async def sign_chunk_images(
    chunks: Sequence[ChunkResult], snapshot: Any, signer: AssetSigner | None, *, max_images: int = 3,
) -> list[ChunkResult]:
    """Gắn ảnh (URL ký mới) vào từng đoạn của GET /retrieval theo `assets` đã lưu cùng thứ tự trong snapshot."""
    raw = snapshot.get("chunks") if isinstance(snapshot, Mapping) else None
    raw_chunks = raw if isinstance(raw, list) else []
    per_chunk = [
        chunk_assets(item.get("assets"))[:max(max_images, 0)] if isinstance(item, Mapping) else []
        for item in raw_chunks
    ]
    signed = await _sign(signer, (a for assets in per_chunk for a in assets))
    if not signed:
        return list(chunks)
    out = []
    for index, chunk in enumerate(chunks):
        assets = per_chunk[index] if index < len(per_chunk) else []
        images = [
            SourceImage(url=signed[(a.bucket, a.path)], page=a.page, printed_page=a.printed_page)
            for a in assets if (a.bucket, a.path) in signed
        ]
        out.append(chunk.model_copy(update={"images": images}) if images else chunk)
    return out
