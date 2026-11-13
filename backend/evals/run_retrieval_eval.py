"""Đánh giá tra cứu tài liệu luồng web trên Supabase thật (D-009, bước 5). Chỉ đọc database.

Hai chế độ:
- `core`: câu hỏi + bộ lọc cố định (domain, model của câu) → `Retriever` thật + `DocChunkV2Repository` →
  `match_doc_chunks_v2`. So các biến thể của hàm (nhánh mã, bỏ dấu, tìm cả cha). Không gọi LLM ngoài embedding.
- `website`: câu hỏi đi qua `RetrievalPipeline` của luồng web (clarification → analysis LLM → execution) với
  retriever v2, hai lượt: `website` (lượt đầu, chỉ câu hỏi) và `website_ctx` (người dùng đã nêu model ở lượt trước:
  hội thoại có `active_model`). Chấm thêm **định tuyến**: intent (`expected_intent` của câu), route mong đợi (câu cần
  model mà chưa có → `clarify`; đã có → `retrieve`), domain tìm. Registry chưa khai báo F54 có tài liệu kỹ thuật →
  công cụ thêm **trong bộ nhớ tiến trình** coverage cho model đã nạp vào `doc_chunks_v2` (báo cáo ghi rõ).

Mọi biến thể chạy với `p_approved_only = false` (chunk đang là `draft`, D-009). Chunk đúng khớp theo
(`content_hash`, `section_path`) của file câu hỏi. Chỉ số: recall@1/@5 (chunk mong đợi hoặc chấp nhận trong top k
sau ngưỡng `min_similarity`), MRR, `mong_doi@1` (đúng chunk mong đợi ở hạng 1), `ngu_canh` (chunk đúng nằm trong
top `final_chunk_top_k` đưa cho LLM).

Chạy từ `backend/` (cần OPENAI_API_KEY, DATABASE_URL):
    .\\venv\\Scripts\\python.exe evals\\run_retrieval_eval.py [--cases <yaml>] [--mode core|website|all] [Q1 Q2 ...]
Kết quả: `data/retrieval_eval/<thời điểm>/report.md`, `results.json`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_CASES = Path(__file__).with_name("retrieval_cases") / "sample_f54_f86.yaml"
OUTPUT = ROOT.parent / "data" / "retrieval_eval"

GoldKey = tuple[str, tuple[str, ...]]

# Biến thể của match_doc_chunks_v2 (chế độ core). Mọi biến thể: approved_only = false. Khóa = trường của
# MatchV2Options, riêng "use_codes" = truyền mã trích từ câu hỏi.
# `base` = mặc định của MatchV2Options (đã bật làm sạch câu FTS — Toma 2026-11-13); `no_fts_clean` đo song song.
# Đã loại sau đánh giá 2026-11-13: giảm trọng số FTS (fts_weight 0,5 — có hại: Q9 2→21).
VARIANTS: dict[str, dict[str, Any]] = {
    "base": {},
    "no_fts_clean": {"fts_clean": False},
    "codes": {"use_codes": True},
    "unaccent": {"unaccent": True},
    "parents": {"include_parents": True},
    # Scope (thử nghiệm I-46/R-2; chỉ khác base khi câu có `scopes`): bỏ qua scope / cộng điểm thay vì lọc.
    "scope_none": {"scope_mode": "boost", "scope_boost": 0.0},
    "scope_boost0.003": {"scope_mode": "boost", "scope_boost": 0.003},
}
# Biến thể phát lại cho chế độ web (cùng kết quả định tuyến của một lần chạy bước phân tích). Scope: production giữ
# `filter`; `boost` đo song song, chốt sau khi sửa I-46 và có câu hỏi phân biệt theo scope.
WEB_VARIANTS: dict[str, dict[str, Any]] = {
    "base": {},
    "no_fts_clean": {"fts_clean": False},
    "scope_none": {"scope_mode": "boost", "scope_boost": 0.0},
    "scope_boost0.003": {"scope_mode": "boost", "scope_boost": 0.003},
    "scope_boost0.01": {"scope_mode": "boost", "scope_boost": 0.01},
}
# --scope-sweep: dò độ lớn điểm cộng scope (thay WEB_VARIANTS và biến thể scope của core).
SCOPE_SWEEP = (0.001, 0.002, 0.003, 0.005, 0.007, 0.01)


def scope_sweep_variants() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {"base": {}, "scope_none": {"scope_mode": "boost", "scope_boost": 0.0}}
    out.update({f"scope_boost{v}": {"scope_mode": "boost", "scope_boost": v} for v in SCOPE_SWEEP})
    return out


# Biến thể có bảng số đo theo loại câu (tag) trong báo cáo.
TAG_VARIANTS = ("core:base", "core:no_fts_clean", "core:scope_none", "core:scope_boost0.003",
                "web2:base", "web2:scope_none", "web2:scope_boost0.003")


# Biến thể in chi tiết top 5 trong báo cáo (bảng tổng và bảng hạng vẫn có mọi biến thể).
DETAIL_VARIANTS = ("core:base", "core:no_fts_clean", "core:scope_none", "web2:base", "web2:scope_boost0.003")


def _options(spec: dict[str, Any], codes: list[str]) -> Any:
    from app.modules.chatbot.repositories.doc_chunk_v2_repository import MatchV2Options

    fields = {k: v for k, v in spec.items() if k != "use_codes"}
    return MatchV2Options(approved_only=False, codes=tuple(codes) if spec.get("use_codes") else (), **fields)


# ----------------------------------------------------------------------------- câu hỏi, chấm điểm (hàm thuần)
@dataclass(frozen=True)
class Case:
    id: str
    question: str
    domain: str
    models: tuple[str, ...]
    tags: tuple[str, ...]
    expected: frozenset[GoldKey]
    acceptable: frozenset[GoldKey]
    expected_keys: tuple[str, ...]
    expected_intents: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()          # scope đúng của câu; chế độ core lọc theo scope này (rỗng = không lọc)
    route_override: str | None = None     # route mong đợi cố định (handoff, chitchat…); None = theo luật model
    domain_override: str | None = None    # domain mong đợi của định tuyến (vd product_catalog); None = `domain`

    @property
    def gold(self) -> frozenset[GoldKey]:
        return self.expected | self.acceptable

    @property
    def routing_only(self) -> bool:
        """Câu không có chunk tài liệu đúng (tư vấn sản phẩm, giá, chào hỏi): chỉ chấm định tuyến."""
        return not self.expected

    @property
    def expected_domain(self) -> str:
        return self.domain_override or self.domain

    @property
    def model_in_question(self) -> bool:
        text = self.question.lower()
        return any(m.lower() in text for m in self.models)

    def expected_route(self, with_context: bool) -> str:
        """Câu hướng dẫn cần model: lượt đầu không nêu model → hỏi lại (đúng thiết kế); đã có model → tìm."""
        if self.route_override:
            return self.route_override
        return "retrieve" if with_context or self.model_in_question else "clarify"


def _gold(items: list[dict[str, Any]] | None) -> frozenset[GoldKey]:
    return frozenset((i["content_hash"], tuple(i["section_path"])) for i in items or [])


def load_cases(path: Path, only: list[str] | None = None) -> list[Case]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = [Case(id=c["id"], question=c["question"], domain=c.get("domain", "technical_docs"),
                  models=tuple(c.get("models") or ()), tags=tuple(c.get("tags") or ()),
                  expected=_gold(c.get("expected")), acceptable=_gold(c.get("acceptable")),
                  expected_keys=tuple(i["chunk_key"] for i in c.get("expected") or []),
                  expected_intents=tuple(c.get("expected_intent") or ()),
                  scopes=tuple(c.get("scopes") or ()),
                  route_override=c.get("expected_route"), domain_override=c.get("expected_domain"))
             for c in data["cases"]]
    for c in cases:
        if c.routing_only and not c.expected_intents:
            raise ValueError(f"{c.id}: không có chunk đúng thì phải có expected_intent (câu chỉ chấm định tuyến)")
    return [c for c in cases if not only or c.id in only]


@dataclass(frozen=True)
class ChunkInfo:
    chunk_key: str
    content_hash: str
    section_path: tuple[str, ...]
    chunk_role: str
    chunk_type: str
    section_title: str
    scopes: tuple[str, ...] = ()

    @property
    def gold_key(self) -> GoldKey:
        return (self.content_hash, self.section_path)

    @property
    def short(self) -> str:
        return self.chunk_key.rsplit(":", 1)[-1]


@dataclass(frozen=True)
class Candidate:
    """Một dòng ứng viên theo thứ tự hàm tìm trả về (fused giảm dần)."""

    chunk_id: int
    vector: float
    fused: float
    relevant: bool                                   # qua ngưỡng min_similarity
    ranks: tuple[int | None, int | None, int | None] = (None, None, None)   # vector, FTS, mã


@dataclass
class CaseResult:
    case_id: str
    variant: str
    rank_gold: int | None              # hạng (1-based, trong ứng viên qua ngưỡng) của chunk đúng đầu tiên
    rank_expected: int | None          # hạng của chunk mong đợi
    in_context: bool                   # chunk đúng có trong ngữ cảnh đưa LLM (hits)
    relevant: int                      # số ứng viên qua ngưỡng
    expected_vector: float | None      # độ giống vector của chunk mong đợi (nếu có trong ứng viên)
    best_wrong_vector: float | None    # độ giống vector cao nhất của chunk sai
    top: list[dict[str, Any]] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)
    note: str = ""
    expected_scopes: list[str] = field(default_factory=list)   # scope hiện tại của các chunk mong đợi


def score_case(case: Case, variant: str, candidates: list[Candidate], hit_ids: set[int],
               index: dict[int, ChunkInfo], top_n: int = 5) -> CaseResult:
    relevant = [c for c in candidates if c.relevant]
    rank_gold = rank_expected = None
    expected_vector = best_wrong = None
    for pos, cand in enumerate(relevant, start=1):
        info = index.get(cand.chunk_id)
        key = info.gold_key if info else None
        if key in case.gold and rank_gold is None:
            rank_gold = pos
        if key in case.expected and rank_expected is None:
            rank_expected = pos
    for cand in candidates:
        info = index.get(cand.chunk_id)
        key = info.gold_key if info else None
        if key in case.expected:
            expected_vector = max(expected_vector or 0.0, cand.vector)
        elif key not in case.gold:
            best_wrong = max(best_wrong or 0.0, cand.vector)
    in_context = any(index.get(i) and index[i].gold_key in case.gold for i in hit_ids)
    top = []
    for pos, cand in enumerate(relevant[:top_n], start=1):
        info = index.get(cand.chunk_id)
        mark = "MONG_DOI" if info and info.gold_key in case.expected else (
            "CHAP_NHAN" if info and info.gold_key in case.acceptable else "")
        top.append({"rank": pos, "chunk": info.short if info else str(cand.chunk_id),
                    "role": info.chunk_role if info else "", "type": info.chunk_type if info else "",
                    "section": info.section_title[:60] if info else "", "vector": round(cand.vector, 3),
                    "fused": round(cand.fused, 4), "r_vec": cand.ranks[0], "r_fts": cand.ranks[1],
                    "r_code": cand.ranks[2], "gold": mark})
    expected_scopes = sorted({s for info in index.values() if info.gold_key in case.expected for s in info.scopes})
    return CaseResult(case.id, variant, rank_gold, rank_expected, in_context, len(relevant),
                      None if expected_vector is None else round(expected_vector, 3),
                      None if best_wrong is None else round(best_wrong, 3), top,
                      expected_scopes=expected_scopes)


@dataclass
class RoutingResult:
    """Quyết định của bước phân tích cho một câu (chế độ website)."""

    case_id: str
    variant: str
    intents: list[str]
    routes: list[str]
    domains: list[str]                 # domain của targets các sub-query có retrieve
    models: list[str]
    clarify_reason: str | None
    expected_intents: list[str]
    expected_route: str
    expected_domain: str

    @property
    def intent_ok(self) -> bool:
        return not self.expected_intents or any(i in self.expected_intents for i in self.intents)

    @property
    def route_ok(self) -> bool:
        return self.expected_route in self.routes

    @property
    def domain_ok(self) -> bool:
        """Lượt cần tìm: phải tìm ở domain đúng; lượt cần hỏi lại: không xét domain."""
        return self.expected_route != "retrieve" or self.expected_domain in self.domains


def routing_result(case: Case, variant: str, analysis: Any, with_context: bool) -> RoutingResult:
    subs = list(analysis.sub_queries) if analysis is not None else []
    domains = [t.domain for sq in subs if sq.retrieval_scope is not None for t in sq.retrieval_scope.targets]
    reason = next((sq.clarification.reason for sq in subs if sq.clarification is not None), None)
    return RoutingResult(case.id, variant, [sq.intent or "" for sq in subs], [sq.route.value for sq in subs],
                         list(dict.fromkeys(domains)),
                         list(dict.fromkeys(m for sq in subs for m in sq.entities.product_models)), reason,
                         list(case.expected_intents), case.expected_route(with_context), case.expected_domain)


def summarize_routing(results: list[RoutingResult]) -> dict[str, float]:
    n = len(results) or 1
    return {"intent_dung": round(sum(r.intent_ok for r in results) / n, 3),
            "route_dung": round(sum(r.route_ok for r in results) / n, 3),
            "domain_dung": round(sum(r.domain_ok for r in results) / n, 3),
            "tat_ca_dung": round(sum(r.intent_ok and r.route_ok and r.domain_ok for r in results) / n, 3)}


def summarize_by_tag(cases: list[Case], results: list[CaseResult], variant: str) -> dict[str, dict[str, float]]:
    """Số đo của một biến thể theo từng tag câu hỏi (một câu có nhiều tag thì tính vào mỗi tag)."""
    by_case = {r.case_id: r for r in results if r.variant == variant}
    out: dict[str, dict[str, float]] = {}
    for tag in sorted({t for c in cases for t in c.tags}):
        rows = [by_case[c.id] for c in cases if tag in c.tags and c.id in by_case]
        if rows:
            out[tag] = {"n": len(rows), **summarize(rows)}
    return out


def summarize(results: list[CaseResult]) -> dict[str, float]:
    n = len(results) or 1
    return {
        "recall@1": round(sum(1 for r in results if r.rank_gold == 1) / n, 3),
        "recall@5": round(sum(1 for r in results if r.rank_gold is not None and r.rank_gold <= 5) / n, 3),
        "mrr": round(sum(1 / r.rank_gold for r in results if r.rank_gold) / n, 3),
        "mong_doi@1": round(sum(1 for r in results if r.rank_expected == 1) / n, 3),
        "ngu_canh": round(sum(1 for r in results if r.in_context) / n, 3),
    }


# ----------------------------------------------------------------------------- chạy trên DB thật
class CachedEmbedder:
    """Embed mỗi câu hỏi một lần cho mọi biến thể."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider
        self._cache: dict[str, list[float]] = {}

    async def embed(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            for text, vector in zip(missing, await self._provider.embed(missing)):
                self._cache[text] = vector
        return [self._cache[t] for t in texts]


class RecordingRepository:
    """Bọc repository v2, giữ các dòng hàm tìm trả về (có hạng từng nhánh) để báo cáo."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.matches: list[Any] = []

    async def match(self, **kwargs: Any) -> list[Any]:
        rows = await self.inner.match(**kwargs)
        self.matches.extend(rows)
        return rows

    async def fetch_by_ids(self, ids: list[int]) -> list[Any]:
        return await self.inner.fetch_by_ids(ids)


async def load_index() -> tuple[dict[int, ChunkInfo], list[str]]:
    from sqlalchemy import text

    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as session:
        rows = (await session.execute(text(
            "select id, chunk_key, content_hash, section_path, chunk_role, chunk_type, section_title, scopes "
            "from doc_chunks_v2 where is_active"))).fetchall()
        models = (await session.execute(text(
            "select distinct unnest(product_models) from doc_chunks_v2 where is_active"))).scalars().all()
    index = {r[0]: ChunkInfo(r[1], r[2], tuple(r[3]), r[4], r[5], r[6], tuple(r[7] or ())) for r in rows}
    return index, sorted(models)


def _candidates(trace: Any, matches_by_id: dict[int, Any]) -> list[Candidate]:
    out = []
    for cand in trace.candidates:
        match = matches_by_id.get(int(cand.chunk_id))
        ranks = (match.vector_rank, match.keyword_rank, match.code_rank) if match is not None else (None, None, None)
        out.append(Candidate(int(cand.chunk_id), cand.scores.vector or 0.0, cand.scores.fused or 0.0,
                             cand.reject_reason != "below_similarity", ranks))
    return out


async def run_core(cases: list[Case], index: dict[int, ChunkInfo], embedder: CachedEmbedder,
                   settings: Any) -> list[CaseResult]:
    from app.modules.chatbot.repositories.doc_chunk_v2_repository import DocChunkV2Repository
    from app.modules.chatbot.retrieval import Retriever, RetrieverConfig
    from app.modules.chatbot.retrieval.codes import extract_codes
    from app.modules.chatbot.schemas.system import RetrievalQuery, RetrievalRequest

    config = RetrieverConfig.from_settings(settings)
    results = []
    for case in cases:
        if case.routing_only:
            continue                      # không có chunk đúng: chỉ chấm định tuyến ở chế độ web
        codes = extract_codes(case.question, exclude=case.models)
        for name, spec in VARIANTS.items():
            repo = RecordingRepository(DocChunkV2Repository(_options(spec, codes)))
            retriever = Retriever(embedder, repo, config)
            request = RetrievalRequest(
                task_id=f"eval-{case.id}", domain=case.domain, scopes=list(case.scopes),
                model_filter=list(case.models) or None,
                queries=[RetrievalQuery(sub_query_id=case.id, query=case.question, answer_mode="full")])
            result = await retriever.search([request])
            by_id = {m.id: m for m in repo.matches}
            candidates = [c for trace in result.traces for c in _candidates(trace, by_id)]
            hit_ids = {int(i) for hit in result.hits for i in hit.matched_chunk_ids}
            scored = score_case(case, f"core:{name}", candidates, hit_ids, index)
            scored.codes = codes if spec.get("use_codes") else []
            results.append(scored)
        print(f"  core {case.id}: " + ", ".join(
            f"{r.variant}={r.rank_gold or '-'}" for r in results if r.case_id == case.id), flush=True)
    return results


def _patch_coverage(models: list[str]) -> list[str]:
    """Thêm coverage technical_docs cho model đã có trong doc_chunks_v2 (chỉ trong tiến trình eval)."""
    from app.modules.chatbot.extraction.registry import REGISTRY

    technical = REGISTRY["coverage"]["technical_docs"]
    caps = REGISTRY["capabilities"]["control_interface"]
    added = [m for m in models if m in caps and m not in technical]
    for m in added:
        technical[m] = list(caps[m])
    return added


def _website_state(question: str, context_model: str | None = None) -> Any:
    """RunState của một lượt chat web. `context_model`: giả lập lượt trước người dùng đã nêu model (hội thoại có
    2 tin nhắn, `active_model` = model đó) — đường thật khi bot đã hỏi lại model và người dùng trả lời."""
    from app.modules.chatbot.schemas.default import ChannelType
    from app.modules.chatbot.schemas.inbound import (
        ChannelInfo, InboundRequest, MessageUser, ResourceRefs, SessionInfo,
    )
    from app.modules.chatbot.schemas.security.principal import PrincipalContext, RequestContext
    from app.modules.chatbot.schemas.system import (
        Conversation, ConversationMessage, ConversationState, QueryInfo, RetrievalScope, RunContext, RunState,
    )

    inbound = InboundRequest(message=MessageUser(message_id=str(uuid4()), text=question),
                             session=SessionInfo(session_id=str(uuid4())),
                             channel=ChannelInfo(type=ChannelType.WEBSITE), resources=ResourceRefs())
    state = RunState(
        input=inbound,
        principal=PrincipalContext(subject_id="retrieval_eval", principal_type="service", tenant_id="qs_technology",
                                   authn_method="service_key", credential_id="eval0000eval0000"),
        request_context=RequestContext(request_id=f"eval-{uuid4().hex[:8]}", channel=ChannelType.WEBSITE,
                                       received_at=datetime.now(UTC)))
    history: list[Any] = []
    conversation = ConversationState()
    if context_model:
        history = [ConversationMessage(role="user", content=f"Tôi đang dùng bộ điều khiển {context_model}.",
                                       message_id=uuid4().hex),
                   ConversationMessage(role="assistant", content=f"Bạn cần hỗ trợ gì về bộ điều khiển {context_model}?",
                                       message_id=uuid4().hex)]
        conversation = ConversationState(active_model=context_model, last_models=[context_model])
    state.context = RunContext(
        conversation=Conversation(history=history, state=conversation),
        query=QueryInfo(origin=question),
        retrieval_scope=RetrievalScope(collections=["crm-technical", "crm-sale"]))
    state.context_status = "pruned"
    return state


async def run_website(cases: list[Case], index: dict[int, ChunkInfo], embedder: CachedEmbedder, provider: Any,
                      settings: Any, with_context: bool = False) -> tuple[list[CaseResult], list[RoutingResult]]:
    from app.modules.chatbot.repositories.doc_chunk_v2_repository import DocChunkV2Repository, MatchV2Options
    from app.modules.chatbot.retrieval import Retriever, RetrieverConfig
    from app.modules.chatbot.stages.analysis_stage import AnalysisStage
    from app.modules.chatbot.stages.clarification_resume_stage import ClarificationResumeStage
    from app.modules.chatbot.stages.execution_stage import ExecutionStage
    from app.modules.chatbot.stages.retrieval_pipeline import RetrievalPipeline

    turn = "web2" if with_context else "web1"
    config = RetrieverConfig.from_settings(settings)
    results, routing = [], []
    for case in cases:
        # 1) Một lần chạy pipeline thật: lấy định tuyến và các lệnh tìm (targets, fallback) mà execution phát ra.
        recorder = RecordingRetriever(Retriever(embedder, DocChunkV2Repository(MatchV2Options(approved_only=False)),
                                                config))
        pipeline = RetrievalPipeline(ClarificationResumeStage(), AnalysisStage(provider),
                                     ExecutionStage(retriever=recorder))
        state = _website_state(case.question, case.models[0] if with_context and case.models else None)
        await pipeline.run(state)
        route = routing_result(case, turn, state.analysis, with_context)
        routing.append(route)
        note = (f"intent={route.intents} route={route.routes} domain={route.domains} models={route.models}"
                + (f" hỏi_lại={route.clarify_reason}" if route.clarify_reason else ""))
        # 2) Phát lại đúng các lệnh tìm đó với từng biến thể (cùng định tuyến → so sánh công bằng).
        line = []
        for name, spec in ({} if case.routing_only else WEB_VARIANTS).items():
            candidates: list[Candidate] = []
            hit_ids: set[int] = set()
            for targets, fallback in recorder.calls:
                repo = RecordingRepository(DocChunkV2Repository(_options(spec, [])))
                result = await Retriever(embedder, repo, config).search(targets, fallback)
                by_id = {m.id: m for m in repo.matches}
                candidates += [c for trace in result.traces for c in _candidates(trace, by_id)]
                hit_ids |= {int(i) for hit in result.hits for i in hit.matched_chunk_ids}
            # Nhiều lần tìm (sub-query/target/fallback): xếp chung theo fused, bỏ trùng giữ điểm cao nhất.
            best: dict[int, Candidate] = {}
            for c in candidates:
                if c.chunk_id not in best or c.fused > best[c.chunk_id].fused:
                    best[c.chunk_id] = c
            merged = sorted(best.values(), key=lambda c: c.fused, reverse=True)
            scored = score_case(case, f"{turn}:{name}", merged, hit_ids, index)
            scored.note = note
            results.append(scored)
            line.append(f"{name}={scored.rank_gold or '-'}")
        ok = route.intent_ok and route.route_ok and route.domain_ok
        print(f"  {turn} {case.id}: {', '.join(line) or '(chỉ định tuyến)'} | định tuyến={'đúng' if ok else 'SAI'} | "
              f"{note}", flush=True)
    return results, routing


class RecordingRetriever:
    """Bọc Retriever: ghi lại (targets, fallback_targets) mỗi lần execution gọi tìm để phát lại theo biến thể."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls: list[tuple[list[Any], list[Any] | None]] = []

    async def search(self, targets: list[Any], fallback_targets: list[Any] | None = None) -> Any:
        self.calls.append((list(targets), list(fallback_targets) if fallback_targets else None))
        return await self.inner.search(targets, fallback_targets)


# ----------------------------------------------------------------------------- báo cáo
def render_routing(cases: list[Case], routing: list[RoutingResult]) -> list[str]:
    if not routing:
        return []
    variants = list(dict.fromkeys(r.variant for r in routing))
    lines = ["## Định tuyến (bước phân tích của luồng web)", "",
             "`web1` = lượt đầu, chỉ có câu hỏi; `web2` = lượt sau khi người dùng đã nêu model (hội thoại có "
             "`active_model`). Route mong đợi: câu hướng dẫn chưa có model → `clarify` (hỏi lại, đúng thiết kế); đã "
             "có model → `retrieve` ở `technical_docs`. Bước phân tích chạy một lần mỗi câu mỗi lượt; các biến thể "
             "tìm kiếm `web1:*`/`web2:*` phát lại đúng các lệnh tìm của lần đó.", "",
             "| Chế độ | intent đúng | route đúng | domain đúng | đúng cả ba |", "|---|---|---|---|---|"]
    for v in variants:
        s = summarize_routing([r for r in routing if r.variant == v])
        lines.append(f"| {v} | {s['intent_dung']} | {s['route_dung']} | {s['domain_dung']} | {s['tat_ca_dung']} |")
    by = {(r.case_id, r.variant): r for r in routing}
    for v in variants:
        lines += ["", f"### {v}", "", "| Câu | intent (mong đợi) | route (mong đợi) | domain | model | hỏi lại | đúng |",
                  "|---|---|---|---|---|---|---|"]
        for c in cases:
            r = by.get((c.id, v))
            if r is None:
                continue
            ok = "✔" if r.intent_ok and r.route_ok and r.domain_ok else "✘ " + ", ".join(
                n for n, good in (("intent", r.intent_ok), ("route", r.route_ok), ("domain", r.domain_ok)) if not good)
            lines.append(f"| {c.id} | {', '.join(r.intents)} ({' / '.join(r.expected_intents)}) | "
                         f"{', '.join(r.routes)} ({r.expected_route}) | {', '.join(r.domains) or '—'} | "
                         f"{', '.join(r.models) or '—'} | {r.clarify_reason or '—'} | {ok} |")
    return lines + [""]


def render(cases: list[Case], results: list[CaseResult], meta: dict[str, Any],
           routing: list[RoutingResult] | None = None) -> str:
    variants = list(dict.fromkeys(r.variant for r in results))
    by = {(r.case_id, r.variant): r for r in results}
    lines = ["# Đánh giá tra cứu (luồng web) trên Supabase", "",
             f"- Thời điểm: {meta['at']} · file câu hỏi: `{meta['cases']}` · {len(cases)} câu",
             f"- Bảng/hàm: `doc_chunks_v2` / `match_doc_chunks_v2`, `p_approved_only = false` (chunk draft)",
             f"- Retriever: {meta['retriever']}",
             f"- Coverage thêm trong bộ nhớ (chế độ website): {meta.get('coverage_patch') or '—'}",
             "- 8–10 câu chỉ để kiểm công cụ và xem xu hướng; chưa đủ để chốt tham số.", "",
             *render_routing(cases, routing or []),
             "## Tìm kiếm", "",
             "`core:*` = bộ lọc cố định (không qua bước phân tích); `web1:*`/`web2:*` = qua bước phân tích thật. "
             "`base` = mặc định production dự kiến (làm sạch câu FTS bật, scope lọc cứng); `no_fts_clean` = tắt làm "
             "sạch (đo song song R-4); `scope_boost*` = scope cộng điểm thay vì lọc (R-2, chốt sau I-46).", "",
             "| Biến thể | recall@1 | recall@5 | MRR | mong_doi@1 | ngu_canh |", "|---|---|---|---|---|---|"]
    for v in variants:
        s = summarize([r for r in results if r.variant == v])
        lines.append(f"| {v} | {s['recall@1']} | {s['recall@5']} | {s['mrr']} | {s['mong_doi@1']} | {s['ngu_canh']} |")
    tag_variants = [v for v in TAG_VARIANTS if v in variants]
    if tag_variants:
        lines += ["", "## Theo loại câu (tag): recall@5 / MRR", "",
                  "| Tag | n | " + " | ".join(tag_variants) + " |", "|---|---|" + "---|" * len(tag_variants)]
        per = {v: summarize_by_tag(cases, results, v) for v in tag_variants}
        for tag in sorted({t for c in cases for t in c.tags}):
            n = next((per[v][tag]["n"] for v in tag_variants if tag in per[v]), 0)
            cells = [f"{per[v][tag]['recall@5']} / {per[v][tag]['mrr']}" if tag in per[v] else "" for v in tag_variants]
            lines.append(f"| {tag} | {n} | " + " | ".join(cells) + " |")
    lines += ["", "## Hạng của chunk đúng theo câu (`-` = không có trong ứng viên qua ngưỡng)", "",
              "| Câu | Câu hỏi | " + " | ".join(variants) + " |", "|---|---|" + "---|" * len(variants)]
    for c in cases:
        cells = []
        for v in variants:
            r = by.get((c.id, v))
            cells.append("" if r is None else f"{r.rank_gold or '-'}{'' if r.in_context else '*'}")
        lines.append(f"| {c.id} | {c.question} | " + " | ".join(cells) + " |")
    detail = [v for v in variants if v in DETAIL_VARIANTS] or variants
    lines += ["", "`*` = chunk đúng không nằm trong ngữ cảnh đưa LLM (ngoài top `final_chunk_top_k`).", "",
              f"## Chi tiết (biến thể: {', '.join(detail)})", ""]
    for c in cases:
        any_result = next((r for r in results if r.case_id == c.id), None)
        scope_note = ""
        if c.scopes:
            scope_note = (f" · scope đúng của câu: {', '.join(c.scopes)} · scope hiện tại của chunk mong đợi: "
                          f"{', '.join(any_result.expected_scopes) if any_result else '?'}")
        lines += [f"### {c.id}. {c.question}", "",
                  f"Mong đợi: {', '.join(k.rsplit(':', 1)[-1] for k in c.expected_keys)} · tags: {', '.join(c.tags)}"
                  f"{scope_note}", ""]
        for v in detail:
            r = by.get((c.id, v))
            if r is None:
                continue
            extra = f" · mã: {r.codes}" if r.codes else ""
            extra += f" · {r.note}" if r.note else ""
            lines += [f"**{v}**: hạng chunk đúng {r.rank_gold or '-'}, chunk mong đợi {r.rank_expected or '-'}, "
                      f"ứng viên qua ngưỡng {r.relevant}, vector chunk mong đợi {r.expected_vector}, "
                      f"vector cao nhất của chunk sai {r.best_wrong_vector}{extra}", "",
                      "| # | chunk | vai trò | loại | mục | vector | fused | hạng vec/FTS/mã | đúng |",
                      "|---|---|---|---|---|---|---|---|---|"]
            for t in r.top:
                ranks = "/".join(str(x) if x is not None else "-" for x in (t["r_vec"], t["r_fts"], t["r_code"]))
                lines.append(f"| {t['rank']} | {t['chunk']} | {t['role']} | {t['type']} | {t['section']} | "
                             f"{t['vector']} | {t['fused']} | {ranks} | {t['gold']} |")
            lines.append("")
    return "\n".join(lines)


async def main_async(args: argparse.Namespace) -> Path:
    from app.core.config import settings
    from app.db.engine import engine
    from app.modules.chatbot.providers.openai import OpenAIProvider

    if not settings.openai_api_key:
        raise SystemExit("thiếu OPENAI_API_KEY")
    cases = load_cases(args.cases, args.ids)
    provider = OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model,
                              embedding_model=settings.embedding_model)
    embedder = CachedEmbedder(provider)
    meta: dict[str, Any] = {
        "at": datetime.now().strftime("%Y-%m-%d %H:%M"), "cases": str(args.cases.relative_to(ROOT)),
        "label": args.label,
        "retriever": (f"vector_k={settings.retrieval_vector_candidate_k}, fts_k={settings.retrieval_fts_candidate_k}, "
                      f"rrf_k={settings.retrieval_rrf_k}, top_k={settings.retrieval_final_chunk_top_k}, "
                      f"min_similarity={settings.retrieval_min_similarity}, embedding={settings.embedding_model}, "
                      f"analysis={settings.openai_model}")}
    try:
        index, models = await load_index()
        results: list[CaseResult] = []
        routing: list[RoutingResult] = []
        if args.mode in ("core", "all"):
            results += await run_core(cases, index, embedder, settings)
        if args.mode in ("website", "all"):
            meta["coverage_patch"] = ", ".join(f"technical_docs+{m}" for m in _patch_coverage(models))
            for with_context in (False, True):
                found, routed = await run_website(cases, index, embedder, provider, settings, with_context)
                results += found
                routing += routed
    finally:
        await engine.dispose()
    out = OUTPUT / (datetime.now().strftime("%Y%m%d-%H%M%S") + (f"-{args.label}" if args.label else ""))
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render(cases, results, meta, routing), encoding="utf-8")
    payload = {"meta": meta, "results": [asdict(r) for r in results],
               "routing": [{**asdict(r), "intent_ok": r.intent_ok, "route_ok": r.route_ok, "domain_ok": r.domain_ok}
                           for r in routing]}
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Đánh giá tra cứu luồng web trên doc_chunks_v2")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--mode", choices=("core", "website", "all"), default="all")
    parser.add_argument("--label", default="", help="hậu tố tên thư mục kết quả (vd scope_test cho bản thử nghiệm)")
    parser.add_argument("--scope-sweep", action="store_true",
                        help=f"chỉ đo biến thể scope: lọc, bỏ qua, cộng điểm {list(SCOPE_SWEEP)}")
    parser.add_argument("ids", nargs="*", help="chỉ chạy các câu này (vd Q1 Q4)")
    args = parser.parse_args(argv)
    args.cases = args.cases.resolve()
    if args.scope_sweep:
        sweep = scope_sweep_variants()
        VARIANTS.clear()
        VARIANTS.update(sweep)
        WEB_VARIANTS.clear()
        WEB_VARIANTS.update(sweep)
    if sys.platform == "win32":   # psycopg async không chạy trên ProactorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    out = asyncio.run(main_async(args))
    print(f"Báo cáo: {out / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
