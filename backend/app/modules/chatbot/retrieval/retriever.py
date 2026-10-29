"""Filtered hybrid retrieval cho một sub-query.

Retriever điều phối: embedding câu hỏi, tra cứu từng target, fallback khi
không có chunk liên quan, tách theo model khi so sánh, hợp nhất + cắt top-k
và mở rộng chunk con sang chunk cha. Filter, vector, FTS và RRF nằm trong SQL
function match_doc_chunks; Retriever không biết SQL hay task.
"""

from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Protocol, Sequence
from uuid import uuid4

from app.modules.chatbot.schemas.default import SourceMetadata
from app.modules.chatbot.schemas.system import (
    Candidate,
    ChunkHit,
    ChunkMatch,
    ChunkRecord,
    RetrievalFilters,
    RetrievalParams,
    RetrievalRequest,
    RetrievalSubQueryResult,
    RetrievalTrace,
    Scores,
)

if TYPE_CHECKING:
    from app.core.config import Settings

METHOD = "hybrid_rrf"
REJECT_BELOW_SIMILARITY = "below_similarity"
REJECT_BELOW_TOP_K = "below_top_k"
REJECT_CONTEXT_LIMIT = "context_limit"


class QueryEmbedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChunkSearchRepository(Protocol):
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
    ) -> list[ChunkMatch]: ...

    async def fetch_by_ids(self, ids: list[int]) -> list[ChunkRecord]: ...


@dataclass(frozen=True)
class RetrieverConfig:
    vector_candidate_k: int = 20
    fts_candidate_k: int = 20
    rrf_k: int = 60
    final_chunk_top_k: int = 6
    max_context_parents: int = 5
    min_similarity: float = 0.25
    spec_boost: float = 0.005

    @classmethod
    def from_settings(cls, settings: "Settings") -> "RetrieverConfig":
        return cls(
            vector_candidate_k=settings.retrieval_vector_candidate_k,
            fts_candidate_k=settings.retrieval_fts_candidate_k,
            rrf_k=settings.retrieval_rrf_k,
            final_chunk_top_k=settings.retrieval_final_chunk_top_k,
            max_context_parents=settings.retrieval_max_context_parents,
            min_similarity=settings.retrieval_min_similarity,
            spec_boost=settings.retrieval_spec_boost,
        )


@dataclass
class _SearchRun:
    request: RetrievalRequest
    models: list[str] | None
    matches: list[ChunkMatch]
    latency_ms: int


class Retriever:
    def __init__(
        self,
        embedder: QueryEmbedder,
        repository: ChunkSearchRepository,
        config: RetrieverConfig | None = None,
    ) -> None:
        self._embedder = embedder
        self._repository = repository
        self._config = config or RetrieverConfig()

    async def search(
        self,
        targets: list[RetrievalRequest],
        fallback_targets: list[RetrievalRequest] | None = None,
    ) -> RetrievalSubQueryResult:
        """Tra cứu một sub-query; mọi request phải mang cùng một câu hỏi."""
        if not targets:
            raise ValueError("retrieval requires at least one target")
        query = targets[0].queries[0]
        embedding = (await self._embedder.embed([query.query]))[0]

        runs = await self._search_targets(targets, embedding)
        ranked = self._merge(runs)
        used_fallback = False
        if not ranked and fallback_targets:
            fallback_runs = await self._search_targets(fallback_targets, embedding)
            runs.extend(fallback_runs)
            ranked = self._merge(fallback_runs)
            used_fallback = True

        kept = ranked[: self._config.final_chunk_top_k]
        hits = await self._expand_parents(kept)
        context_child_ids = {chunk_id for hit in hits for chunk_id in hit.matched_chunk_ids}
        kept_ids = {str(match.id) for match in kept}

        metadata: dict[str, str] = {}
        if not hits:
            metadata["no_hits"] = "true"
        if used_fallback:
            metadata["fallback"] = "true"
        return RetrievalSubQueryResult(
            sub_query_id=query.sub_query_id,
            hits=hits,
            traces=[
                self._trace(run, iteration, kept_ids, context_child_ids)
                for iteration, run in enumerate(runs)
            ],
            metadata=metadata,
        )

    async def _search_targets(
        self,
        targets: list[RetrievalRequest],
        embedding: list[float],
    ) -> list[_SearchRun]:
        runs: list[_SearchRun] = []
        for request in targets:
            models = request.model_filter
            # So sánh: tra cứu riêng từng model để một model không chiếm hết top-k.
            if request.product_scope_mode == "comparison" and models and len(models) > 1:
                for model in models:
                    runs.append(await self._search_one(request, embedding, [model]))
            else:
                runs.append(await self._search_one(request, embedding, models))
        return runs

    async def _search_one(
        self,
        request: RetrievalRequest,
        embedding: list[float],
        models: list[str] | None,
    ) -> _SearchRun:
        started = perf_counter()
        matches = await self._repository.match(
            embedding=embedding,
            query_text=request.queries[0].query,
            domain=request.domain,
            scopes=request.scopes,
            models=models,
            control_interface=request.control_interface,
            spec_attributes=request.spec_attributes,
            vector_k=self._config.vector_candidate_k,
            fts_k=self._config.fts_candidate_k,
            rrf_k=self._config.rrf_k,
            spec_boost=self._config.spec_boost,
        )
        return _SearchRun(
            request=request,
            models=models,
            matches=matches,
            latency_ms=int((perf_counter() - started) * 1000),
        )

    def _relevant(self, match: ChunkMatch) -> bool:
        return match.vector_score >= self._config.min_similarity

    def _merge(self, runs: list[_SearchRun]) -> list[ChunkMatch]:
        """Gộp kết quả các lần tra cứu, dedupe theo id và giữ điểm fused cao nhất.

        Các lần tra cứu theo từng model được xen kẽ (round-robin) để top-k chia
        đều giữa các model khi so sánh.
        """
        per_run = [
            sorted(
                (match for match in run.matches if self._relevant(match)),
                key=lambda match: match.fused_score,
                reverse=True,
            )
            for run in runs
        ]
        if len(runs) > 1 and all(
            run.request.product_scope_mode == "comparison" for run in runs
        ):
            ordered: list[ChunkMatch] = []
            for position in range(max((len(items) for items in per_run), default=0)):
                ordered.extend(items[position] for items in per_run if position < len(items))
        else:
            ordered = sorted(
                (match for items in per_run for match in items),
                key=lambda match: match.fused_score,
                reverse=True,
            )

        seen: set[int] = set()
        merged: list[ChunkMatch] = []
        for match in ordered:
            if match.id in seen:
                continue
            seen.add(match.id)
            merged.append(match)
        return merged

    async def _expand_parents(self, kept: list[ChunkMatch]) -> list[ChunkHit]:
        """Gom chunk con theo chunk cha, giữ thứ tự xếp hạng của chunk con tốt nhất."""
        groups: dict[int, list[ChunkMatch]] = {}
        for match in kept:
            context_id = match.parent_id if match.parent_id is not None else match.id
            if context_id not in groups and len(groups) >= self._config.max_context_parents:
                continue
            groups.setdefault(context_id, []).append(match)

        # Fetch cả chunk context không có cha: match_doc_chunks không trả
        # domain/scopes/control_interface/spec_attributes của chunk.
        fetch_ids = list(dict.fromkeys(
            [*groups.keys(), *(matches[0].id for matches in groups.values())]
        ))
        records = {
            record.id: record
            for record in await self._repository.fetch_by_ids(fetch_ids)
        }

        hits: list[ChunkHit] = []
        for context_id, matches in groups.items():
            best = matches[0]
            # Chunk cha không còn active: dùng chính chunk con tốt nhất.
            record: ChunkRecord = records.get(context_id) or records.get(best.id, best)
            hits.append(ChunkHit(
                chunk_id=str(record.id),
                matched_chunk_ids=[str(match.id) for match in matches],
                doc_id=record.doc_id,
                section_title=record.section_title,
                section_path=record.section_path,
                page_start=record.page_start,
                page_end=record.page_end,
                content=record.content,
                assets=record.assets,
                domain=record.domain,
                scopes=record.scopes,
                control_interface=record.control_interface,
                spec_attributes=record.spec_attributes,
                score=best.fused_score,
            ))
        return hits

    def _trace(
        self,
        run: _SearchRun,
        iteration: int,
        kept_ids: set[str],
        context_child_ids: set[str],
    ) -> RetrievalTrace:
        request = run.request
        candidates = []
        for match in run.matches:
            chunk_id = str(match.id)
            if not self._relevant(match):
                reject_reason: str | None = REJECT_BELOW_SIMILARITY
            elif chunk_id not in kept_ids:
                reject_reason = REJECT_BELOW_TOP_K
            elif chunk_id not in context_child_ids:
                reject_reason = REJECT_CONTEXT_LIMIT
            else:
                reject_reason = None   # được chọn; ExecutionStage gán source_id
            candidates.append(Candidate(
                chunk_id=chunk_id,
                scores=Scores(
                    keyword=match.keyword_score,
                    vector=match.vector_score,
                    fused=match.fused_score,
                ),
                metadata=source_metadata(match),
                reject_reason=reject_reason,
            ))
        return RetrievalTrace(
            retrieval_id=uuid4().hex,
            iteration=iteration,
            query=request.queries[0].query,
            method=METHOD,
            params=RetrievalParams(
                top_k=self._config.vector_candidate_k,
                rerank_top_n=self._config.final_chunk_top_k,
                filters=RetrievalFilters(
                    domain=request.domain,
                    scopes=request.scopes,
                    product_models=run.models,
                    control_interface=request.control_interface,
                    spec_attributes=request.spec_attributes,
                ),
            ),
            candidates=candidates,
            latency_ms=run.latency_ms,
        )


def source_metadata(record: ChunkRecord | ChunkHit) -> SourceMetadata:
    page = record.page_start if record.page_start and record.page_start >= 1 else None
    section = " › ".join(record.section_path) if record.section_path else record.section_title
    return SourceMetadata(
        doc_id=record.doc_id,
        version=1,
        title=record.section_title,
        page=page,
        section=section,
    )
