"""D-009: trích mã từ câu hỏi, repository `doc_chunks_v2` (tham số SQL, bỏ cột thừa), chấm điểm của
`evals/run_retrieval_eval.py`. Không cần DB."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Any

from app.modules.chatbot.repositories.doc_chunk_v2_repository import DocChunkV2Repository, MatchV2Options
from app.modules.chatbot.retrieval.codes import extract_codes, normalize_code

ROOT = Path(__file__).resolve().parents[2]


def _eval_module():
    spec = importlib.util.spec_from_file_location("run_retrieval_eval", ROOT / "evals" / "run_retrieval_eval.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module          # dataclass cần module có trong sys.modules
    spec.loader.exec_module(module)
    return module


def test_extract_codes() -> None:
    assert extract_codes("Tham số #12010 dùng để làm gì?") == ["#12010"]
    assert extract_codes("Cổng CN10 trên bộ điều khiển F86", exclude=["F86"]) == ["CN10"]
    assert extract_codes("m1920, M1920 và #0008; AX1.ENA, PUL1+") == ["M1920", "#8", "AX1.ENA", "PUL1+"]
    assert extract_codes("đấu dây 24V cho cảm biến NPN trên F54", exclude=["F54"]) == []
    assert extract_codes("cach dau day tay quay MPG co nut EMG") == []
    assert normalize_code("x 41") == "X41"


class _Mappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> list[dict[str, Any]]:
        return self._rows


class _Session:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows, self.calls = rows, []

    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def execute(self, sql: Any, params: dict[str, Any]) -> _Mappings:
        self.calls.append((str(sql), params))
        return _Mappings(self.rows)


ROW = {"id": 7, "parent_id": 3, "chunk_key": "d:B0007", "chunk_role": "child", "chunk_type": "wiring",
       "doc_id": "d", "doc_version": "v1", "doc_title": "Doc", "section_title": "S", "section_path": ["1 A"],
       "page_start": 1, "page_end": 1, "printed_page_start": 1, "printed_page_end": 1, "content": "c",
       "assets": "[]", "vector_score": 0.6, "keyword_score": None, "code_score": 1.0, "vector_rank": 2,
       "keyword_rank": None, "code_rank": 1, "fused_score": 0.03}


def test_v2_repository_params_and_extra_columns() -> None:
    session = _Session([ROW])
    repo = DocChunkV2Repository(MatchV2Options(codes=("#12010",), approved_only=False, unaccent=True),
                                session_factory=lambda: session)
    matches = asyncio.run(repo.match(embedding=[0.1, 0.2], query_text="q", domain="technical_docs", scopes=[],
                                     models=[], control_interface=[], spec_attributes=[], vector_k=20, fts_k=20,
                                     rrf_k=60, spec_boost=0.005))
    sql, params = session.calls[0]
    assert "match_doc_chunks_v2" in sql
    assert params["codes"] == ["#12010"] and params["models"] is None and params["approved_only"] is False
    assert params["unaccent"] is True and params["include_parents"] is False and params["chunk_types"] is None
    match = matches[0]                                    # doc_version, doc_title, trang in bị bỏ, không lỗi
    assert match.chunk_key == "d:B0007" and match.code_rank == 1 and match.assets == []
    asyncio.run(repo.fetch_by_ids([7]))
    fetch_sql, fetch_params = session.calls[1]
    assert "from doc_chunks_v2" in fetch_sql and fetch_params["approved_only"] is False


def test_default_options_are_production_behaviour() -> None:
    o = MatchV2Options()
    assert o.approved_only and not o.include_parents and not o.unaccent and o.codes == () and o.type_boost == 0
    # Toma 2026-11-13: bật làm sạch câu FTS; trọng số giữ 1; scope lọc cứng tới khi sửa I-46.
    assert (o.vector_weight, o.fts_weight, o.code_weight, o.fts_clean) == (1.0, 1.0, 1.0, True)
    assert o.scope_mode == "filter" and o.scope_boost == 0.0
    session = _Session([])
    repo = DocChunkV2Repository(session_factory=lambda: session)
    asyncio.run(repo.match(embedding=[0.1], query_text="Cách đấu cảm biến về home trên bộ điều khiển F54",
                           domain="technical_docs", scopes=[], models=["F54"], control_interface=[],
                           spec_attributes=[], vector_k=20, fts_k=20, rrf_k=60, spec_boost=0.005))
    assert session.calls[0][1]["query_text"] == "đấu cảm biến home"
    off = DocChunkV2Repository(MatchV2Options(fts_clean=False), session_factory=lambda: session)
    asyncio.run(off.match(embedding=[0.1], query_text="Cách đấu F54", domain="technical_docs", scopes=[],
                          models=["F54"], control_interface=[], spec_attributes=[], vector_k=20, fts_k=20,
                          rrf_k=60, spec_boost=0.005))
    assert session.calls[1][1]["query_text"] == "Cách đấu F54"


def test_clean_fts_query() -> None:
    from app.modules.chatbot.retrieval.fts_query import clean_fts_query

    assert clean_fts_query("Cách đấu cảm biến về home trên bộ điều khiển F54", ["F54"]) == "đấu cảm biến home"
    assert clean_fts_query("Tham số #12010 dùng để làm gì?", []) == "Tham số #12010 làm"
    assert clean_fts_query("Hướng dẫn đấu nối Servo trong bộ điều khiển F54", ["F54"]) == "đấu nối Servo"
    assert clean_fts_query("cach dau day tay quay MPG tren bo dieu khien F54", ["F54"]) == "dau day tay quay MPG"
    assert clean_fts_query("như thế nào?", []) == "như thế nào?"                              # rỗng → câu gốc
    # Từ mang nghĩa kỹ thuật được giữ: đầu vào/đầu ra (input/output), "không" (triệu chứng lỗi).
    assert clean_fts_query("Cách đấu tín hiệu đầu vào và đầu ra", []) == "đấu tín hiệu đầu vào đầu ra"
    assert clean_fts_query("Máy không về home", []) == "Máy không home"


def test_v2_repository_r2_r4_params() -> None:
    session = _Session([ROW])
    options = MatchV2Options(fts_clean=True, fts_weight=0.5, scope_mode="boost", scope_boost=0.01)
    repo = DocChunkV2Repository(options, session_factory=lambda: session)
    asyncio.run(repo.match(embedding=[0.1], query_text="Cách đấu cảm biến về home trên bộ điều khiển F54",
                           domain="technical_docs", scopes=["installation"], models=["F54"], control_interface=[],
                           spec_attributes=[], vector_k=20, fts_k=20, rrf_k=60, spec_boost=0.005))
    sql, params = session.calls[0]
    assert "p_scope_mode => :scope_mode" in sql and "fts_weight => :fts_weight" in sql
    assert params["query_text"] == "đấu cảm biến home"          # câu FTS đã làm sạch; embedding không đổi
    assert params["scope_mode"] == "boost" and params["scope_boost"] == 0.01 and params["fts_weight"] == 0.5
    assert params["scopes"] == ["installation"]                 # scope vẫn truyền, hàm SQL quyết lọc hay cộng điểm
    bad = DocChunkV2Repository(MatchV2Options(scope_mode="soft"), session_factory=lambda: session)
    try:
        asyncio.run(bad.match(embedding=[0.1], query_text="q", domain="d", scopes=[], models=None,
                              control_interface=[], spec_attributes=[], vector_k=1, fts_k=1, rrf_k=60, spec_boost=0))
    except ValueError as exc:
        assert "scope_mode" in str(exc)
    else:
        raise AssertionError("scope_mode lạ phải báo lỗi")


def test_eval_scoring(tmp_path: Path) -> None:
    ev = _eval_module()
    cases_file = tmp_path / "c.yaml"
    cases_file.write_text(
        "cases:\n"
        "  - id: Q1\n    question: q\n    models: [F54]\n"
        "    expected:\n      - {chunk_key: d:B1, content_hash: h1, section_path: [A]}\n"
        "    acceptable:\n      - {chunk_key: d:B2, content_hash: h2, section_path: [A]}\n", encoding="utf-8")
    case = ev.load_cases(cases_file)[0]
    index = {1: ev.ChunkInfo("d:B1", "h1", ("A",), "child", "wiring", "S1"),
             2: ev.ChunkInfo("d:B2", "h2", ("A",), "child", "wiring", "S2"),
             3: ev.ChunkInfo("d:B3", "h3", ("B",), "standalone", "figure", "S3")}
    cands = [ev.Candidate(3, 0.7, 0.05, True), ev.Candidate(2, 0.6, 0.04, True), ev.Candidate(1, 0.5, 0.03, True),
             ev.Candidate(9, 0.1, 0.01, False)]
    r = ev.score_case(case, "base", cands, {3, 2}, index)
    assert (r.rank_gold, r.rank_expected, r.in_context, r.relevant) == (2, 3, True, 3)
    assert r.expected_vector == 0.5 and r.best_wrong_vector == 0.7
    assert [t["gold"] for t in r.top] == ["", "CHAP_NHAN", "MONG_DOI"]
    assert case.model_in_question is False
    assert case.expected_route(with_context=False) == "clarify" and case.expected_route(with_context=True) == "retrieve"
    miss = ev.score_case(case, "base", [ev.Candidate(3, 0.7, 0.05, True)], {3}, index)
    s = ev.summarize([r, miss])
    assert s == {"recall@1": 0.0, "recall@5": 0.5, "mrr": 0.25, "mong_doi@1": 0.0, "ngu_canh": 0.5}
    tagged = ev.Case(**{**case.__dict__, "tags": ("dau_day", "tu_khoa")})
    by_tag = ev.summarize_by_tag([tagged], [r], "base")
    assert set(by_tag) == {"dau_day", "tu_khoa"} and by_tag["dau_day"]["n"] == 1 and by_tag["dau_day"]["mrr"] == 0.5


def test_eval_routing(tmp_path: Path) -> None:
    from types import SimpleNamespace as NS

    ev = _eval_module()
    cases_file = tmp_path / "c.yaml"
    cases_file.write_text(
        "cases:\n  - id: Q8\n    question: Cổng CN10 trên F86 dùng để làm gì?\n    models: [F86]\n"
        "    expected_intent: [guide.installation]\n"
        "    expected:\n      - {chunk_key: d:B1, content_hash: h1, section_path: [A]}\n", encoding="utf-8")
    case = ev.load_cases(cases_file)[0]
    assert case.model_in_question and case.expected_route(False) == "retrieve"

    def analysis(intent: str, route: str, domain: str | None) -> NS:
        scope = NS(targets=[NS(domain=domain)]) if domain else None
        return NS(sub_queries=[NS(intent=intent, route=NS(value=route), retrieval_scope=scope, clarification=None,
                                  entities=NS(product_models=["F86"]))])

    wrong = ev.routing_result(case, "website", analysis("lookup.product_info", "retrieve", "product_catalog"), False)
    assert (wrong.intent_ok, wrong.route_ok, wrong.domain_ok) == (False, True, False)
    right = ev.routing_result(case, "website", analysis("guide.installation", "retrieve", "technical_docs"), False)
    assert (right.intent_ok, right.route_ok, right.domain_ok) == (True, True, True)
    assert ev.summarize_routing([wrong, right]) == {"intent_dung": 0.5, "route_dung": 1.0, "domain_dung": 0.5,
                                                    "tat_ca_dung": 0.5}
