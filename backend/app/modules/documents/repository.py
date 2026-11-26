"""Đọc `crm_documents` và `doc_chunks_v2` cho màn "Tài liệu & chunk" (chỉ đọc).

Chỉ đếm và trả chunk đang hoạt động (`is_active`) không phải chunk cha (chunk cha là khung ghép ngữ cảnh, người duyệt
đọc chunk con/độc lập). `doc_chunks_v2` có nhiều phiên bản cùng `doc_id`: lấy phiên bản có chunk đang hoạt động mới
nạp nhất.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LEAF = "is_active and chunk_role <> 'parent'"


@dataclass(frozen=True)
class ChunkStats:
    chunks: int
    approved: int
    doc_title: str | None = None
    doc_version: str | None = None
    page_count: int | None = None
    image_chunks: int = 0


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def documents(self) -> list[dict[str, Any]]:
        result = await self._session.execute(text(
            "select crm_id::text as crm_id, doc_id, name, branch, folder, model, document_type, language, "
            "connection_types, version, file_size, sync_mode, sync_state, "
            "to_char(crm_updated_at at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') as crm_updated_at, "
            "on_crm, to_char(last_seen_at at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') as last_seen_at, "
            "sort_order from public.crm_documents order by branch, folder nulls first, sort_order nulls last, name"))
        return [dict(row._mapping) for row in result]

    async def document(self, doc_id: str) -> dict[str, Any] | None:
        rows = [row for row in await self.documents() if row["doc_id"] == doc_id]
        return rows[0] if rows else None

    async def stats(self, doc_ids: Sequence[str]) -> dict[str, ChunkStats]:
        if not doc_ids:
            return {}
        result = await self._session.execute(text(
            f"with current as ("
            f"  select distinct on (doc_id) doc_id, doc_version from public.doc_chunks_v2"
            f"  where {LEAF} and doc_id = any(cast(:ids as text[])) order by doc_id, loaded_at desc)"
            f" select c.doc_id, c.doc_version, max(d.doc_title) as doc_title, count(*) as chunks,"
            f"  count(*) filter (where d.review_status = 'approved') as approved,"
            f"  max(coalesce(d.page_end, d.page_start)) as page_count,"
            f"  count(*) filter (where jsonb_array_length(d.assets) > 0) as image_chunks"
            f" from current c join public.doc_chunks_v2 d on d.doc_id = c.doc_id and d.doc_version = c.doc_version"
            f" where d.{LEAF.replace(' and ', ' and d.')} group by c.doc_id, c.doc_version"),
            {"ids": list(doc_ids)})
        return {
            row.doc_id: ChunkStats(chunks=row.chunks, approved=row.approved, doc_title=row.doc_title,
                                   doc_version=row.doc_version, page_count=row.page_count,
                                   image_chunks=row.image_chunks)
            for row in result
        }

    async def section_paths(self, doc_id: str, doc_version: str) -> list[tuple[list[str], int]]:
        result = await self._session.execute(text(
            f"select section_path, count(*) as n from public.doc_chunks_v2"
            f" where {LEAF} and doc_id = :d and doc_version = :v group by section_path order by min(chunk_index)"),
            {"d": doc_id, "v": doc_version})
        return [(list(row.section_path or []), row.n) for row in result]

    async def chunks(
        self,
        doc_id: str,
        doc_version: str,
        *,
        offset: int,
        limit: int,
        status: str | None = None,
        has_images: bool = False,
        q: str | None = None,
        section: Sequence[str] | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        conditions = [LEAF, "doc_id = :d", "doc_version = :v"]
        params: dict[str, Any] = {"d": doc_id, "v": doc_version, "offset": offset, "limit": limit}
        if status in ("draft", "approved"):
            conditions.append("review_status = :status")
            params["status"] = status
        if has_images:
            conditions.append("jsonb_array_length(assets) > 0")
        if q:
            # Không phân biệt hoa thường và dấu (cùng hàm với tìm kiếm của chat).
            conditions.append(
                "public.immutable_unaccent(lower(section_title || ' ' || content || ' ' || coalesce(summary_vi, '')))"
                " like '%' || public.immutable_unaccent(lower(:q)) || '%' escape '\\'")
            params["q"] = _escape_like(q)
        if section:
            conditions.append("section_path[1:cardinality(cast(:sec as text[]))] = cast(:sec as text[])")
            params["sec"] = list(section)
        where = " and ".join(conditions)
        total = (await self._session.execute(
            text(f"select count(*) from public.doc_chunks_v2 where {where}"), params)).scalar_one()
        result = await self._session.execute(text(
            "select id, chunk_key, chunk_index, chunk_type, section_path, section_title, page_start, page_end,"
            " printed_page_start, printed_page_end, content, summary_vi, keywords, review_status, assets"
            f" from public.doc_chunks_v2 where {where} order by chunk_index offset :offset limit :limit"), params)
        return int(total), [dict(row._mapping) for row in result]
