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

So sánh phiên bản prompt phân tích: `--prompt-version`, `--intent-desc-version` (mặc định = bản production). Báo cáo
và `results.json` (`meta.analysis_prompt`) ghi phiên bản khung, phiên bản mô tả intent và dấu sha256 của prompt đã gửi.

Đo bước phân tích (R-1):
- `--mode routing`: chỉ chấm định tuyến (pipeline thật, retriever giả trả rỗng; không phát lại biến thể tìm kiếm).
- `--repeat N`: chạy bước phân tích N lần mỗi câu mỗi lượt (LLM dao động dù temperature 0). Số đo = trung bình các
  lần; **ổn định** = tỉ lệ câu cho cùng (intent, route, domain) ở mọi lần.
- `--analysis-model <tên>`: model LLM của bước phân tích (mặc định `OPENAI_MODEL`); báo cáo ghi độ trễ p50/p95 và số
  lần bước phân tích lỗi (timeout, output sai).
- `--split dev|test|all` (mặc định `all`): phần câu hỏi theo trường `split` của câu (câu không ghi thì thuộc `dev`);
  `dev` để sửa luật/prompt, `test` chỉ để đo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
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
# Từ 2026-11-14 (R-2) mặc định là scope cộng điểm 0,003 → `base` = `scope_boost0.003`; hành vi cũ (lọc cứng) đo ở
# `scope_filter`. So với báo cáo trước ngày này: `base` cũ = `scope_filter` mới.
VARIANTS: dict[str, dict[str, Any]] = {
    "base": {},
    "scope_filter": {"scope_mode": "filter", "scope_boost": 0.0},
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
    "scope_filter": {"scope_mode": "filter", "scope_boost": 0.0},
    "no_fts_clean": {"fts_clean": False},
    "scope_none": {"scope_mode": "boost", "scope_boost": 0.0},
    "scope_boost0.003": {"scope_mode": "boost", "scope_boost": 0.003},
    "scope_boost0.01": {"scope_mode": "boost", "scope_boost": 0.01},
    # Điểm cộng cho target chính của luật định tuyến RT-1… (`target_boost` ghi đè `boost` của lệnh tìm; chỉ khác
    # `scope_boost0.003` khi --routing-version bật luật): 0 = không ưu tiên, 0,005 = ưu tiên mạnh hơn mặc định 0,003.
    "sb0.003_tb0": {"scope_mode": "boost", "scope_boost": 0.003, "target_boost": 0.0},
    "sb0.003_tb0.005": {"scope_mode": "boost", "scope_boost": 0.003, "target_boost": 0.005},
}
# Khóa của biến thể không phải trường của MatchV2Options.
_NON_OPTION_KEYS = ("use_codes", "target_boost")
# --scope-sweep: dò độ lớn điểm cộng scope (thay WEB_VARIANTS và biến thể scope của core).
SCOPE_SWEEP = (0.001, 0.002, 0.003, 0.005, 0.007, 0.01)


def scope_sweep_variants() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {"scope_filter": {"scope_mode": "filter", "scope_boost": 0.0},
                                      "scope_none": {"scope_mode": "boost", "scope_boost": 0.0}}
    out.update({f"scope_boost{v}": {"scope_mode": "boost", "scope_boost": v} for v in SCOPE_SWEEP})
    return out


# Biến thể có bảng số đo theo loại câu (tag) trong báo cáo.
TAG_VARIANTS = ("core:base", "core:no_fts_clean", "core:scope_none", "core:scope_boost0.003",
                "web2:base", "web2:scope_none", "web2:scope_boost0.003")


# Biến thể in chi tiết top 5 trong báo cáo (bảng tổng và bảng hạng vẫn có mọi biến thể).
DETAIL_VARIANTS = ("core:base", "core:no_fts_clean", "core:scope_none", "web2:base", "web2:scope_boost0.003")


def _with_target_boost(requests: list[Any] | None, spec: dict[str, Any]) -> list[Any] | None:
    """Biến thể `target_boost`: đổi điểm cộng của các lệnh tìm đang là target chính (boost > 0)."""
    if not requests or "target_boost" not in spec:
        return requests
    return [r.model_copy(update={"boost": spec["target_boost"]}) if r.boost > 0 else r for r in requests]


def _options(spec: dict[str, Any], codes: list[str]) -> Any:
    from app.modules.chatbot.repositories.doc_chunk_v2_repository import MatchV2Options

    fields = {k: v for k, v in spec.items() if k not in _NON_OPTION_KEYS}
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
    split: str = "dev"                    # dev = dùng để sửa luật/prompt; test = chỉ để đo

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


SPLITS = ("dev", "test")


def _domains(value: str | list[str] | None) -> str | None:
    """`expected_domain` của câu: một domain, hoặc danh sách = chấp nhận tìm ở BẤT KỲ domain nào trong đó (câu có
    câu trả lời ở cả catalog lẫn tài liệu kỹ thuật). Lưu dạng "a|b"."""
    if value is None or isinstance(value, str):
        return value
    return "|".join(value)


def load_cases(path: Path, only: list[str] | None = None, split: str | None = None) -> list[Case]:
    """`split`: None hoặc "all" = mọi câu; "dev"/"test" = chỉ phần đó (câu không ghi `split` thuộc `dev`)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = [Case(id=c["id"], question=c["question"], domain=c.get("domain", "technical_docs"),
                  models=tuple(c.get("models") or ()), tags=tuple(c.get("tags") or ()),
                  expected=_gold(c.get("expected")), acceptable=_gold(c.get("acceptable")),
                  expected_keys=tuple(i["chunk_key"] for i in c.get("expected") or []),
                  expected_intents=tuple(c.get("expected_intent") or ()),
                  scopes=tuple(c.get("scopes") or ()),
                  route_override=c.get("expected_route"), domain_override=_domains(c.get("expected_domain")),
                  split=c.get("split", "dev"))
             for c in data["cases"]]
    seen: set[str] = set()
    for c in cases:
        if c.id in seen:
            raise ValueError(f"{c.id}: trùng id")
        seen.add(c.id)
        if c.split not in SPLITS:
            raise ValueError(f"{c.id}: split phải là một trong {SPLITS}")
        if c.routing_only and not c.expected_intents:
            raise ValueError(f"{c.id}: không có chunk đúng thì phải có expected_intent (câu chỉ chấm định tuyến)")
    return [c for c in cases if (not only or c.id in only) and (split in (None, "all") or c.split == split)]


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
    run: int = 1                       # lần chạy bước phân tích (--repeat); core luôn 1


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
    run: int = 1                       # lần chạy bước phân tích (--repeat)
    error: str | None = None           # mã AnalysisError nếu bước phân tích lỗi (timeout, output sai)
    # Execution có phát lệnh tìm không. Sub-query route `retrieve` vẫn có thể bị giữ lại chờ làm rõ
    # (`planner.held_sub_query_ids`, vd. LLM coi tên board là model lạ) → không tìm gì.
    searched: bool = True

    @property
    def signature(self) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], bool]:
        """Quyết định định tuyến của một lần chạy; hai lần chạy cùng signature = ổn định."""
        return tuple(self.intents), tuple(self.routes), tuple(self.domains), self.searched

    @property
    def all_ok(self) -> bool:
        return self.intent_ok and self.route_ok and self.domain_ok

    @property
    def intent_ok(self) -> bool:
        return not self.expected_intents or any(i in self.expected_intents for i in self.intents)

    @property
    def route_ok(self) -> bool:
        """Mong đợi `retrieve` thì phải thực sự có lệnh tìm (route đúng mà bị giữ lại chờ làm rõ = sai)."""
        return self.expected_route in self.routes and (self.expected_route != "retrieve" or self.searched)

    @property
    def domain_ok(self) -> bool:
        """Lượt cần tìm: phải tìm ở domain đúng (`a|b` = một trong các domain); lượt khác: không xét domain."""
        return self.expected_route != "retrieve" or any(d in self.domains for d in self.expected_domain.split("|"))


def routing_result(case: Case, variant: str, analysis: Any, with_context: bool, run: int = 1,
                   error: str | None = None, searched: bool = True) -> RoutingResult:
    """`analysis` None (bước phân tích lỗi) → không intent/route/domain nào: tính là sai. `searched`: execution có
    phát lệnh tìm không."""
    subs = list(analysis.sub_queries) if analysis is not None else []
    domains = [t.domain for sq in subs if sq.retrieval_scope is not None for t in sq.retrieval_scope.targets]
    reason = next((sq.clarification.reason for sq in subs if sq.clarification is not None), None)
    return RoutingResult(case.id, variant, [sq.intent or "" for sq in subs], [sq.route.value for sq in subs],
                         list(dict.fromkeys(domains)),
                         list(dict.fromkeys(m for sq in subs for m in sq.entities.product_models)), reason,
                         list(case.expected_intents), case.expected_route(with_context), case.expected_domain,
                         run=run, error=error, searched=searched)


def summarize_routing(results: list[RoutingResult]) -> dict[str, float]:
    n = len(results) or 1
    return {"intent_dung": round(sum(r.intent_ok for r in results) / n, 3),
            "route_dung": round(sum(r.route_ok for r in results) / n, 3),
            "domain_dung": round(sum(r.domain_ok for r in results) / n, 3),
            "tat_ca_dung": round(sum(r.intent_ok and r.route_ok and r.domain_ok for r in results) / n, 3)}


def routing_stability(results: list[RoutingResult]) -> dict[str, Any]:
    """Độ ổn định giữa các lần chạy (một biến thể): câu ổn định = mọi lần cho cùng (intent, route, domain).
    `bien_tat_ca_dung` = (thấp nhất, cao nhất) của "đúng cả ba" theo từng lần chạy = biên nhiễu của phép đo."""
    by_case: dict[str, list[RoutingResult]] = {}
    for r in results:
        by_case.setdefault(r.case_id, []).append(r)
    unstable = [cid for cid, rows in by_case.items() if len({r.signature for r in rows}) > 1]
    per_run = [summarize_routing([r for r in results if r.run == run])["tat_ca_dung"]
               for run in sorted({r.run for r in results})]
    return {"so_lan": len(per_run), "on_dinh": round(1 - len(unstable) / (len(by_case) or 1), 3),
            "khong_on_dinh": unstable, "bien_tat_ca_dung": (min(per_run, default=0.0), max(per_run, default=0.0)),
            "loi_phan_tich": sum(1 for r in results if r.error)}


def intent_confusion(results: list[RoutingResult]) -> dict[tuple[str, str], list[str]]:
    """(intent mong đợi, intent thực tế) → các câu (mỗi lần chạy sai tính một lần). Chỉ gồm câu có `expected_intent`
    mà intent sai; bước phân tích lỗi ghi là `(lỗi: <mã>)`."""
    out: dict[tuple[str, str], list[str]] = {}
    for r in results:
        if not r.expected_intents or r.intent_ok:
            continue
        actual = f"(lỗi: {r.error})" if r.error else ", ".join(r.intents) or "(không có)"
        out.setdefault((" / ".join(r.expected_intents), actual), []).append(r.case_id)
    return out


def summarize_routing_by_tag(cases: list[Case], results: list[RoutingResult]) -> dict[str, dict[str, float]]:
    """Định tuyến của một biến thể theo tag (tag `cap:<a>~<b>` = cặp intent dễ nhầm); `n` = số câu."""
    out: dict[str, dict[str, float]] = {}
    for tag in sorted({t for c in cases for t in c.tags}):
        ids = {c.id for c in cases if tag in c.tags}
        rows = [r for r in results if r.case_id in ids]
        if rows:
            out[tag] = {"n": len({r.case_id for r in rows}), **summarize_routing(rows)}
    return out


def percentile(values: list[float], p: float) -> float:
    """Phân vị kiểu nearest-rank (p trong 0..100); danh sách rỗng → 0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * p / 100) - 1))]


def summarize_by_tag(cases: list[Case], results: list[CaseResult], variant: str) -> dict[str, dict[str, float]]:
    """Số đo của một biến thể theo từng tag câu hỏi (một câu có nhiều tag thì tính vào mỗi tag); `n` = số câu,
    số đo = trung bình mọi lần chạy."""
    out: dict[str, dict[str, float]] = {}
    for tag in sorted({t for c in cases for t in c.tags}):
        ids = {c.id for c in cases if tag in c.tags}
        rows = [r for r in results if r.variant == variant and r.case_id in ids]
        if rows:
            out[tag] = {"n": len({r.case_id for r in rows}), **summarize(rows)}
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
    """Chỉ mục chunk đang hoạt động + các model có chunk **tài liệu kỹ thuật** (để thêm coverage `technical_docs`;
    model chỉ có chunk catalog không được tính)."""
    from sqlalchemy import text

    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as session:
        rows = (await session.execute(text(
            "select id, chunk_key, content_hash, section_path, chunk_role, chunk_type, section_title, scopes "
            "from doc_chunks_v2 where is_active"))).fetchall()
        models = (await session.execute(text(
            "select distinct unnest(product_models) from doc_chunks_v2 "
            "where is_active and domain = 'technical_docs'"))).scalars().all()
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


async def run_website(cases: list[Case], index: dict[int, ChunkInfo], embedder: CachedEmbedder, analysis_stage: Any,
                      settings: Any, with_context: bool = False, repeat: int = 1, routing_only: bool = False,
                      routing_version: str | None = None) -> tuple[list[CaseResult], list[RoutingResult]]:
    """`repeat`: số lần chạy bước phân tích mỗi câu. `routing_only`: retriever giả, không phát lại biến thể tìm.
    `routing_version`: luật định tuyến cho bước làm rõ (phải trùng với bản của `analysis_stage`)."""
    from app.modules.chatbot.analysis.analyzer import AnalysisError
    from app.modules.chatbot.repositories.doc_chunk_v2_repository import DocChunkV2Repository, MatchV2Options
    from app.modules.chatbot.retrieval import Retriever, RetrieverConfig
    from app.modules.chatbot.stages.clarification_resume_stage import ClarificationResumeStage
    from app.modules.chatbot.stages.execution_stage import ExecutionStage
    from app.modules.chatbot.stages.retrieval_pipeline import RetrievalPipeline

    turn = "web2" if with_context else "web1"
    config = RetrieverConfig.from_settings(settings)
    results, routing = [], []
    for case, run in ((case, run) for case in cases for run in range(1, repeat + 1)):
        # 1) Một lần chạy pipeline thật: lấy định tuyến và các lệnh tìm (targets, fallback) mà execution phát ra.
        recorder = RecordingRetriever(NullRetriever() if routing_only else Retriever(
            embedder, DocChunkV2Repository(MatchV2Options(approved_only=False)), config))
        pipeline = RetrievalPipeline(ClarificationResumeStage(routing_version), analysis_stage,
                                     ExecutionStage(retriever=recorder))
        state = _website_state(case.question, case.models[0] if with_context and case.models else None)
        error = None
        try:
            await pipeline.run(state)
        except AnalysisError as exc:      # timeout, output sai: tính là câu sai, không dừng cả lượt đo
            if exc.code == "analysis_provider_error":
                # Lỗi hạ tầng (hết credit, sai key, mất mạng) không phải chất lượng model: dừng, không ghi số sai lệch.
                raise SystemExit(f"bước phân tích lỗi provider ở câu {case.id}: {exc.__cause__!r}") from exc
            error = exc.code
        route = routing_result(case, turn, state.analysis, with_context, run, error, searched=bool(recorder.calls))
        routing.append(route)
        note = (f"intent={route.intents} route={route.routes} domain={route.domains} models={route.models}"
                + (f" hỏi_lại={route.clarify_reason}" if route.clarify_reason else "")
                + ("" if route.searched or "retrieve" not in route.routes else " KHÔNG_TÌM")
                + (f" LỖI={error}" if error else ""))
        # 2) Phát lại đúng các lệnh tìm đó với từng biến thể (cùng định tuyến → so sánh công bằng).
        line = []
        for name, spec in ({} if case.routing_only or routing_only else WEB_VARIANTS).items():
            candidates: list[Candidate] = []
            hit_ids: set[int] = set()
            for targets, fallback in recorder.calls:
                repo = RecordingRepository(DocChunkV2Repository(_options(spec, [])))
                result = await Retriever(embedder, repo, config).search(
                    _with_target_boost(targets, spec), _with_target_boost(fallback, spec))
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
            scored.run = run
            results.append(scored)
            line.append(f"{name}={scored.rank_gold or '-'}")
        label = f"{case.id}" + (f" (lần {run})" if repeat > 1 else "")
        print(f"  {turn} {label}: {', '.join(line) or '(chỉ định tuyến)'} | "
              f"định tuyến={'đúng' if route.all_ok else 'SAI'} | {note}", flush=True)
    return results, routing


class NullRetriever:
    """Retriever giả cho `--mode routing`: không tìm gì, để pipeline chạy trọn mà không cần embedding/DB."""

    async def search(self, targets: list[Any], fallback_targets: list[Any] | None = None) -> Any:
        from app.modules.chatbot.schemas.system import RetrievalSubQueryResult

        return RetrievalSubQueryResult(sub_query_id=targets[0].queries[0].sub_query_id, hits=[], traces=[],
                                       metadata={"no_hits": "true"})


class TimedProvider:
    """Bọc provider của bước phân tích: đo thời gian mỗi lần gọi `chat_complete_json` (ms)."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.latencies_ms: list[float] = []

    async def chat_complete_json(self, *args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        try:
            return await self._inner.chat_complete_json(*args, **kwargs)
        finally:
            self.latencies_ms.append((perf_counter() - started) * 1000)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def summary(self) -> dict[str, Any]:
        v = self.latencies_ms
        return {"so_lan_goi": len(v), "p50_ms": round(percentile(v, 50)), "p95_ms": round(percentile(v, 95)),
                "max_ms": round(max(v, default=0.0))}


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
             "có model → `retrieve` ở `technical_docs` và execution phải thực sự phát lệnh tìm (sub-query bị giữ "
             "lại chờ làm rõ = route sai, ghi \"không tìm\"). Mỗi lần chạy bước phân tích, các biến thể tìm kiếm "
             "`web1:*`/`web2:*` phát lại đúng các lệnh tìm của lần đó.", "",
             "Nhiều lần chạy (`--repeat`): số đo = trung bình các lần; **ổn định** = tỉ lệ câu cho cùng (intent, route, "
             "domain) ở mọi lần; **biên** = \"đúng cả ba\" thấp nhất–cao nhất theo từng lần (chênh lệch nhỏ hơn biên "
             "này là nhiễu, không phải cải thiện).", "",
             "| Chế độ | số lần | intent đúng | route đúng | domain đúng | đúng cả ba | ổn định | biên đúng cả ba | "
             "lỗi phân tích |", "|---|---|---|---|---|---|---|---|---|"]
    for v in variants:
        rows = [r for r in routing if r.variant == v]
        s, st = summarize_routing(rows), routing_stability(rows)
        low, high = st["bien_tat_ca_dung"]
        lines.append(f"| {v} | {st['so_lan']} | {s['intent_dung']} | {s['route_dung']} | {s['domain_dung']} | "
                     f"{s['tat_ca_dung']} | {st['on_dinh']} | {low}–{high} | {st['loi_phan_tich']} |")

    confusion = {v: intent_confusion([r for r in routing if r.variant == v]) for v in variants}
    if any(confusion.values()):
        lines += ["", "### Nhầm intent (mong đợi → thực tế; số lần = số lần chạy bị nhầm)", "",
                  "| Chế độ | mong đợi | thực tế | số lần | câu |", "|---|---|---|---|---|"]
        for v in variants:
            for (expected, actual), ids in sorted(confusion[v].items(), key=lambda kv: -len(kv[1])):
                lines.append(f"| {v} | {expected} | {actual} | {len(ids)} | {', '.join(dict.fromkeys(ids))} |")

    per_tag = {v: summarize_routing_by_tag(cases, [r for r in routing if r.variant == v]) for v in variants}
    tags = sorted({t for v in variants for t in per_tag[v]})
    if tags:
        lines += ["", "### Định tuyến theo tag: đúng cả ba (intent đúng)", "",
                  "| Tag | n | " + " | ".join(variants) + " |", "|---|---|" + "---|" * len(variants)]
        for tag in tags:
            n = next((per_tag[v][tag]["n"] for v in variants if tag in per_tag[v]), 0)
            cells = [f"{per_tag[v][tag]['tat_ca_dung']} ({per_tag[v][tag]['intent_dung']})" if tag in per_tag[v] else ""
                     for v in variants]
            lines.append(f"| {tag} | {n} | " + " | ".join(cells) + " |")

    by: dict[tuple[str, str], list[RoutingResult]] = {}
    for r in sorted(routing, key=lambda r: r.run):
        by.setdefault((r.case_id, r.variant), []).append(r)
    for v in variants:
        lines += ["", f"### {v} (chi tiết lần 1; cột \"các lần\" = kết quả từng lần chạy)", "",
                  "| Câu | intent (mong đợi) | route (mong đợi) | domain | model | hỏi lại | đúng | các lần |",
                  "|---|---|---|---|---|---|---|---|"]
        unstable: list[str] = []
        for c in cases:
            runs = by.get((c.id, v))
            if not runs:
                continue
            r = runs[0]
            ok = "✔" if r.all_ok else "✘ " + ", ".join(
                n for n, good in (("intent", r.intent_ok), ("route", r.route_ok), ("domain", r.domain_ok)) if not good)
            marks = "".join("✔" if x.all_ok else "✘" for x in runs)
            held = "" if r.searched or "retrieve" not in r.routes else " · không tìm"
            lines.append(f"| {c.id} | {', '.join(r.intents)} ({' / '.join(r.expected_intents)}) | "
                         f"{', '.join(r.routes)}{held} ({r.expected_route}) | {', '.join(r.domains) or '—'} | "
                         f"{', '.join(r.models) or '—'} | {r.clarify_reason or r.error or '—'} | {ok} | {marks} |")
            if len({x.signature for x in runs}) > 1:
                unstable.append(f"- {c.id} \"{c.question}\": " + "; ".join(
                    f"lần {x.run}: {', '.join(x.intents) or x.error or '—'} → {', '.join(x.routes) or '—'}"
                    f" [{', '.join(x.domains) or '—'}]"
                    + ("" if x.searched or "retrieve" not in x.routes else " (không tìm)") for x in runs))
        if unstable:
            lines += ["", f"Câu không ổn định ({v}):", "", *unstable]
    return lines + [""]


def _prompt_label(info: dict[str, Any] | None) -> str:
    if not info:
        return "—"
    return (f"khung `{info['prompt_version']}`, mô tả intent `{info['intent_desc_version']}`, "
            f"n_examples={info['n_examples']}, sha256 `{info['sha256']}`")


def render(cases: list[Case], results: list[CaseResult], meta: dict[str, Any],
           routing: list[RoutingResult] | None = None) -> str:
    variants = list(dict.fromkeys(r.variant for r in results))
    runs_by: dict[tuple[str, str], list[CaseResult]] = {}
    for r in sorted(results, key=lambda r: r.run):
        runs_by.setdefault((r.case_id, r.variant), []).append(r)
    by = {key: rows[0] for key, rows in runs_by.items()}       # chi tiết: lần chạy đầu
    latency = meta.get("analysis_latency")
    lines = ["# Đánh giá tra cứu (luồng web) trên Supabase", "",
             f"- Thời điểm: {meta['at']} · file câu hỏi: `{meta['cases']}` · {len(cases)} câu"
             f" · phần: {meta.get('split') or 'all'} · chế độ: {meta.get('mode') or 'all'}"
             f" · số lần chạy bước phân tích: {meta.get('repeat') or 1}",
             f"- Bảng/hàm: `doc_chunks_v2` / `match_doc_chunks_v2`, `p_approved_only = false` (chunk draft)",
             f"- Retriever: {meta['retriever']}",
             f"- Prompt phân tích (chế độ website): {_prompt_label(meta.get('analysis_prompt'))}",
             "- Luật định tuyến: " + (
                 f"`{meta['routing']['version']}` ({', '.join(meta['routing']['rules']) or 'không luật nào'})"
                 if meta.get("routing") else "—"),
             "- Độ trễ bước phân tích: " + (
                 f"p50 {latency['p50_ms']} ms, p95 {latency['p95_ms']} ms, cao nhất {latency['max_ms']} ms "
                 f"({latency['so_lan_goi']} lần gọi)" if latency else "—"),
             f"- Coverage thêm trong bộ nhớ (chế độ website): {meta.get('coverage_patch') or '—'}",
             "- Bộ câu nhỏ (dưới ~30 câu) chỉ để kiểm công cụ và xem xu hướng; chưa đủ để chốt tham số.", "",
             *render_routing(cases, routing or []),
             "## Tìm kiếm", "",
             "`core:*` = bộ lọc cố định (không qua bước phân tích); `web1:*`/`web2:*` = qua bước phân tích thật. "
             "`base` = mặc định production dự kiến (làm sạch câu FTS bật, scope cộng điểm 0,003 từ 2026-11-14); "
             "`scope_filter` = scope lọc cứng (`base` của các báo cáo trước 2026-11-14); `no_fts_clean` = tắt làm sạch "
             "(R-4); `scope_boost*`/`scope_none` = mức cộng điểm scope khác; `sb0.003_tb*` = điểm cộng cho target "
             "chính của luật định tuyến (chỉ khác khi `--routing-version` bật luật).", "",
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
    if not results:
        return "\n".join(lines)
    lines += ["", "## Hạng của chunk đúng theo câu (`-` = không có trong ứng viên qua ngưỡng)", "",
              "| Câu | Câu hỏi | " + " | ".join(variants) + " |", "|---|---|" + "---|" * len(variants)]
    for c in cases:
        if not any((c.id, v) in runs_by for v in variants):
            continue                       # câu chỉ chấm định tuyến
        cells = []
        for v in variants:
            cells.append("/".join(f"{r.rank_gold or '-'}{'' if r.in_context else '*'}"
                                  for r in runs_by.get((c.id, v), [])))
        lines.append(f"| {c.id} | {c.question} | " + " | ".join(cells) + " |")
    detail = [v for v in variants if v in DETAIL_VARIANTS] or variants
    lines += ["", "`*` = chunk đúng không nằm trong ngữ cảnh đưa LLM (ngoài top `final_chunk_top_k`). Nhiều lần chạy: "
              "hạng từng lần cách nhau bằng `/`.", "",
              f"## Chi tiết (lần chạy đầu; biến thể: {', '.join(detail)})", ""]
    for c in cases:
        if not any((c.id, v) in by for v in variants):
            continue
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
    cases = load_cases(args.cases, args.ids, args.split)
    if not cases:
        raise SystemExit("không có câu hỏi nào khớp (kiểm --split và danh sách id)")
    provider = OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model,
                              embedding_model=settings.embedding_model)
    embedder = CachedEmbedder(provider)
    analysis_model = args.analysis_model or settings.openai_model
    meta: dict[str, Any] = {
        "at": datetime.now().strftime("%Y-%m-%d %H:%M"), "cases": str(args.cases.relative_to(ROOT)),
        "label": args.label, "mode": args.mode, "split": args.split, "repeat": args.repeat,
        "analysis_model": analysis_model,
        "retriever": (f"vector_k={settings.retrieval_vector_candidate_k}, fts_k={settings.retrieval_fts_candidate_k}, "
                      f"rrf_k={settings.retrieval_rrf_k}, top_k={settings.retrieval_final_chunk_top_k}, "
                      f"min_similarity={settings.retrieval_min_similarity}, embedding={settings.embedding_model}, "
                      f"analysis={analysis_model}")}
    try:
        index, models = await load_index()
        results: list[CaseResult] = []
        routing: list[RoutingResult] = []
        if args.mode in ("core", "all"):
            results += await run_core(cases, index, embedder, settings)
        if args.mode in ("website", "routing", "all"):
            from app.modules.chatbot.stages.analysis_stage import AnalysisStage

            meta["coverage_patch"] = ", ".join(f"technical_docs+{m}" for m in _patch_coverage(models))
            timed = TimedProvider(provider if analysis_model == settings.openai_model else OpenAIProvider(
                api_key=settings.openai_api_key, model=analysis_model, embedding_model=settings.embedding_model))
            from app.modules.chatbot.extraction.registry import ROUTING_VERSION, routing_rules

            analysis_stage = AnalysisStage(timed, prompt_version=args.prompt_version,
                                           intent_desc_version=args.intent_desc_version,
                                           routing_version=args.routing_version)
            meta["analysis_prompt"] = analysis_stage.analyzer.prompt_info
            meta["routing"] = {"version": args.routing_version or ROUTING_VERSION,
                               "rules": sorted(routing_rules(args.routing_version))}
            for with_context in (False, True):
                found, routed = await run_website(cases, index, embedder, analysis_stage, settings, with_context,
                                                  repeat=args.repeat, routing_only=args.mode == "routing",
                                                  routing_version=args.routing_version)
                results += found
                routing += routed
            meta["analysis_latency"] = timed.summary()
    finally:
        await engine.dispose()
    out = OUTPUT / (datetime.now().strftime("%Y%m%d-%H%M%S") + (f"-{args.label}" if args.label else ""))
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render(cases, results, meta, routing), encoding="utf-8")
    variants = list(dict.fromkeys(r.variant for r in routing))
    meta["routing_summary"] = {v: {**summarize_routing(rows), **routing_stability(rows)}
                               for v in variants for rows in [[r for r in routing if r.variant == v]]}
    payload = {"meta": meta, "results": [asdict(r) for r in results],
               "routing": [{**asdict(r), "intent_ok": r.intent_ok, "route_ok": r.route_ok, "domain_ok": r.domain_ok}
                           for r in routing]}
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Đánh giá tra cứu luồng web trên doc_chunks_v2")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--mode", choices=("core", "website", "routing", "all"), default="all",
                        help="routing = chỉ chấm định tuyến của bước phân tích (không tìm kiếm)")
    parser.add_argument("--repeat", type=int, default=1, help="số lần chạy bước phân tích mỗi câu mỗi lượt")
    parser.add_argument("--analysis-model", default=None, help="model LLM của bước phân tích (mặc định OPENAI_MODEL)")
    parser.add_argument("--split", choices=(*SPLITS, "all"), default="all",
                        help="phần câu hỏi theo trường `split` của câu (mặc định all)")
    parser.add_argument("--label", default="", help="hậu tố tên thư mục kết quả (vd scope_test cho bản thử nghiệm)")
    parser.add_argument("--scope-sweep", action="store_true",
                        help=f"chỉ đo biến thể scope: lọc, bỏ qua, cộng điểm {list(SCOPE_SWEEP)}")
    parser.add_argument("--prompt-version", default=None,
                        help="phiên bản khung prompt phân tích (mặc định: bản production, PROMPT_VERSION)")
    parser.add_argument("--intent-desc-version", default=None,
                        help="phiên bản mô tả intent (mặc định: bản production, INTENT_DESC_VERSION)")
    parser.add_argument("--routing-version", default=None,
                        help="phiên bản luật định tuyến: r0, r1, r2 hoặc mã luật nối bằng + (vd RT-1+RT-2+RT-3b); "
                             "mặc định: bản production, ROUTING_VERSION")
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
