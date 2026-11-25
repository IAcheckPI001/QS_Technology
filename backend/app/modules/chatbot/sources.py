"""Nguồn đã trích dẫn của một lượt trả lời, kèm ảnh (D-014 giai đoạn B, event SSE `sources`).

Ảnh do backend đính kèm theo chunk mà câu trả lời thực sự trích dẫn (`[S#]`); model không sinh URL. URL ký ngắn hạn
được cấp lúc dựng event, không lưu vào lịch sử.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from app.modules.chatbot.providers.supabase_storage import AssetSigner
from app.modules.chatbot.schemas.system import ChunkHit

logger = logging.getLogger(__name__)

_BRACKET = re.compile(r"\[([^\[\]]*\bS\d+\b[^\[\]]*)\]")
_SOURCE_ID = re.compile(r"\bS(\d+)\b")


class SourceImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    page: int | None = None
    printed_page: int | None = None


class SourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str
    doc_id: str
    pages: str | None = None
    images: list[SourceImage] = []


def cited_source_ids(answer: str) -> list[str]:
    """Mã nguồn có trong câu trả lời theo thứ tự xuất hiện, không trùng; hiểu `[S1]`, `[S1, S2]`."""
    found: list[str] = []
    for bracket in _BRACKET.findall(answer):
        for number in _SOURCE_ID.findall(bracket):
            source_id = f"S{int(number)}"
            if source_id not in found:
                found.append(source_id)
    return found


def _pages(hit: ChunkHit) -> str | None:
    if hit.page_start is None:
        return None
    if hit.page_end is None or hit.page_end == hit.page_start:
        return str(hit.page_start)
    return f"{hit.page_start}-{hit.page_end}"


async def build_sources(
    hits: Sequence[ChunkHit],
    answer: str,
    signer: AssetSigner | None,
    *,
    max_images: int = 3,
) -> list[SourceItem]:
    """Nguồn được trích dẫn trong `answer`. `signer` None → không có ảnh (vẫn trả danh sách nguồn)."""
    by_id: dict[str, ChunkHit] = {}
    for hit in hits:
        if hit.source_id and hit.source_id not in by_id:
            by_id[hit.source_id] = hit
    selected = [by_id[source_id] for source_id in cited_source_ids(answer) if source_id in by_id]
    if not selected:
        return []

    wanted = {hit.source_id: hit.assets[:max_images] for hit in selected} if max_images > 0 else {}
    signed = await signer.sign(a for assets in wanted.values() for a in assets) if signer and wanted else {}
    items = []
    for hit in selected:
        images = [
            SourceImage(url=signed[(a.bucket, a.path)], page=a.page, printed_page=a.printed_page)
            for a in wanted.get(hit.source_id, [])
            if (a.bucket, a.path) in signed
        ]
        items.append(SourceItem(
            source_id=hit.source_id or "", title=hit.section_title, doc_id=hit.doc_id,
            pages=_pages(hit), images=images))
    return items
