"""Truy vấn bảng `doc_chunks_v2` qua `match_doc_chunks_v2` (D-009, `backend/sql/doc_chunks_v2.sql`).

Cùng giao diện `ChunkSearchRepository` với `DocChunkRepository` để `Retriever` dùng được không đổi; tham số riêng
của v2 (mã, loại chunk, cờ biến thể) nằm trong `MatchV2Options` của repository. Hiện chỉ công cụ đánh giá dùng
(`evals/run_retrieval_eval.py`); retriever của dịch vụ chat vẫn dùng bảng cũ cho tới bước chuyển (D-009).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chatbot.repositories.doc_chunk_repository import _row, _vector_literal
from app.modules.chatbot.retrieval.fts_query import clean_fts_query
from app.modules.chatbot.schemas.system import ChunkMatch, ChunkRecord

_MATCH_SQL = text("""
    select * from match_doc_chunks_v2(
        cast(cast(:embedding as text) as vector),
        :query_text,
        :domain,
        p_scopes => cast(:scopes as text[]),
        p_models => cast(:models as text[]),
        p_control_interface => cast(:control_interface as text[]),
        p_spec_attributes => cast(:spec_attributes as text[]),
        p_codes => cast(:codes as text[]),
        p_chunk_types => cast(:chunk_types as text[]),
        vector_k => :vector_k,
        fts_k => :fts_k,
        code_k => :code_k,
        rrf_k => :rrf_k,
        spec_boost => :spec_boost,
        type_boost => :type_boost,
        p_approved_only => :approved_only,
        p_include_parents => :include_parents,
        p_unaccent => :unaccent,
        vector_weight => :vector_weight,
        fts_weight => :fts_weight,
        code_weight => :code_weight,
        p_scope_mode => :scope_mode,
        scope_boost => :scope_boost
    )
""")

_FETCH_SQL = text("""
    select id, parent_id, doc_id, section_title, section_path,
           page_start, page_end, content, assets,
           domain, scopes, control_interface, spec_attributes
    from doc_chunks_v2
    where id = any(cast(:ids as bigint[])) and is_active
      and (not :approved_only or review_status = 'approved')
""")


@dataclass(frozen=True)
class MatchV2Options:
    """Tham số riêng của `match_doc_chunks_v2`. Mặc định = hành vi production dự kiến (chỉ chunk approved, không
    tìm cha, không nhánh mã, không bỏ dấu, không cộng điểm loại, **làm sạch câu FTS**, scope lọc cứng).

    Toma 2026-11-13: bật `fts_clean` (eval 14 câu: MRR core 0,643 → 0,861, không câu nào tụt) nhưng tiếp tục đo song
    song với câu hỏi đa dạng; trọng số giữ 1 (giảm FTS có hại); scope giữ `filter` tới khi sửa I-46 và đo lại
    `filter`/`boost` với câu phân biệt theo scope."""

    codes: tuple[str, ...] = ()
    chunk_types: tuple[str, ...] = ()
    code_k: int = 20
    type_boost: float = 0.0
    approved_only: bool = True
    include_parents: bool = False
    unaccent: bool = False
    # R-4: trọng số từng nhánh khi trộn RRF; làm sạch câu FTS (bỏ model, từ phổ biến — `retrieval/fts_query.py`).
    vector_weight: float = 1.0
    fts_weight: float = 1.0
    code_weight: float = 1.0
    fts_clean: bool = True
    # R-2: "filter" = scope là bộ lọc cứng (như cũ); "boost" = không lọc, cộng `scope_boost` cho chunk đúng scope.
    scope_mode: str = "filter"
    scope_boost: float = 0.0

    def with_(self, **changes: Any) -> MatchV2Options:
        return replace(self, **changes)


class DocChunkV2Repository:
    """Mỗi lời gọi mở session riêng (các task retrieve chạy song song)."""

    def __init__(self, options: MatchV2Options | None = None,
                 session_factory: Callable[[], AsyncSession] | None = None) -> None:
        self.options = options or MatchV2Options()
        self._session_factory = session_factory

    def _session(self) -> AsyncSession:
        if self._session_factory is None:
            from app.db.session import AsyncSessionFactory

            self._session_factory = AsyncSessionFactory
        return self._session_factory()

    async def match(
        self,
        *,
        embedding: Sequence[float],
        query_text: str,
        domain: str,
        scopes: list[str],
        models: list[str] | None,
        control_interface: list[str],
        spec_attributes: list[str],
        vector_k: int,
        fts_k: int,
        rrf_k: int,
        spec_boost: float,
    ) -> list[ChunkMatch]:
        o = self.options
        if o.scope_mode not in ("filter", "boost"):
            raise ValueError(f"scope_mode lạ: {o.scope_mode}")
        params: dict[str, Any] = {
            "embedding": _vector_literal(embedding),
            # Chỉ nhánh FTS dùng query_text; embedding đã tính trên câu gốc.
            "query_text": clean_fts_query(query_text, models or []) if o.fts_clean else query_text,
            "domain": domain,
            "scopes": scopes or None,
            "models": models or None,
            "control_interface": control_interface or None,
            "spec_attributes": spec_attributes or None,
            "codes": list(o.codes) or None,
            "chunk_types": list(o.chunk_types) or None,
            "vector_k": vector_k,
            "fts_k": fts_k,
            "code_k": o.code_k,
            "rrf_k": rrf_k,
            "spec_boost": spec_boost,
            "type_boost": o.type_boost,
            "approved_only": o.approved_only,
            "include_parents": o.include_parents,
            "unaccent": o.unaccent,
            "vector_weight": o.vector_weight,
            "fts_weight": o.fts_weight,
            "code_weight": o.code_weight,
            "scope_mode": o.scope_mode,
            "scope_boost": o.scope_boost,
        }
        async with self._session() as session:
            result = await session.execute(_MATCH_SQL, params)
            # Hàm v2 trả thêm cột (doc_version, doc_title, trang in) mà ChunkMatch chưa dùng: bỏ, không làm hỏng.
            fields = ChunkMatch.model_fields
            return [ChunkMatch.model_validate({k: v for k, v in _row(row).items() if k in fields})
                    for row in result.mappings()]

    async def fetch_by_ids(self, ids: list[int]) -> list[ChunkRecord]:
        if not ids:
            return []
        async with self._session() as session:
            result = await session.execute(_FETCH_SQL, {"ids": ids, "approved_only": self.options.approved_only})
            fields = ChunkRecord.model_fields
            return [ChunkRecord.model_validate({k: v for k, v in _row(row).items() if k in fields})
                    for row in result.mappings()]
