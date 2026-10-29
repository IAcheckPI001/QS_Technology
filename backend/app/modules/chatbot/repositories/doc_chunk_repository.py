import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chatbot.schemas.system import ChunkMatch, ChunkRecord

_MATCH_SQL = text("""
    select * from match_doc_chunks(
        cast(cast(:embedding as text) as vector),
        :query_text,
        :domain,
        cast(:scopes as text[]),
        cast(:models as text[]),
        cast(:control_interface as text[]),
        cast(:spec_attributes as text[]),
        :vector_k,
        :fts_k,
        :rrf_k,
        :spec_boost
    )
""")

_FETCH_SQL = text("""
    select id, parent_id, doc_id, section_title, section_path,
           page_start, page_end, content, assets,
           domain, scopes, control_interface, spec_attributes
    from doc_chunks
    where id = any(cast(:ids as bigint[])) and is_active
""")


def _vector_literal(embedding: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in embedding) + "]"


def _row(row: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(row)
    # text() không gắn kiểu cột nên jsonb có thể về dạng chuỗi tùy driver.
    if isinstance(data.get("assets"), str):
        data["assets"] = json.loads(data["assets"])
    return data


class DocChunkRepository:
    """Truy vấn doc_chunks qua SQL function match_doc_chunks.

    Mỗi lời gọi mở session riêng: các task retrieve chạy song song và một
    AsyncSession không được dùng đồng thời.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None) -> None:
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
        params: dict[str, Any] = {
            "embedding": _vector_literal(embedding),
            "query_text": query_text,
            "domain": domain,
            "scopes": scopes or None,
            "models": models,
            "control_interface": control_interface or None,
            "spec_attributes": spec_attributes or None,
            "vector_k": vector_k,
            "fts_k": fts_k,
            "rrf_k": rrf_k,
            "spec_boost": spec_boost,
        }
        async with self._session() as session:
            result = await session.execute(_MATCH_SQL, params)
            return [ChunkMatch.model_validate(_row(row)) for row in result.mappings()]

    async def fetch_by_ids(self, ids: list[int]) -> list[ChunkRecord]:
        if not ids:
            return []
        async with self._session() as session:
            result = await session.execute(_FETCH_SQL, {"ids": ids})
            return [ChunkRecord.model_validate(_row(row)) for row in result.mappings()]
