"""Luật định tuyến bằng code có phiên bản (R-1 giai đoạn B): `registry.ROUTING_RULES`,
`validate_registry.resolve_sub_query(routing_version=…)`, điểm cộng target khi gộp kết quả. Không gọi LLM, không DB.

F86 có cả catalog lẫn tài liệu kỹ thuật trong registry; F10T chỉ có catalog.
"""

import pytest

from app.modules.chatbot.analysis.analyzer import build_analysis
from app.modules.chatbot.extraction.registry import (
    ROUTING_CODE_PATTERN, ROUTING_RULES, ROUTING_TARGET_BOOST, ROUTING_VERSION, RegistryError, routing_rules,
)
from app.modules.chatbot.extraction.validate_registry import resolve_sub_query
from app.modules.chatbot.orchestration.handlers import build_retrieval_requests
from app.modules.chatbot.orchestration.planner import build_execution_plan, held_sub_query_ids
from app.modules.chatbot.retrieval.retriever import Retriever, _SearchRun
from app.modules.chatbot.schemas.system import ChunkMatch, RetrievalQuery, RetrievalRequest, TaskKind

CATALOG, DOCS = {"domain": "product_catalog"}, {"domain": "technical_docs"}
CATALOG_FIRST = [{**CATALOG, "boost": ROUTING_TARGET_BOOST}, DOCS]
DOCS_FIRST = [{**DOCS, "boost": ROUTING_TARGET_BOOST}, CATALOG]


def _sq(query: str, intent: str, models=(), unresolved=()) -> dict:
    return {"standalone_query": query, "intent": intent, "product_models": list(models),
            "unresolved_mentions": list(unresolved), "control_interface": [], "excluded_control_interface": [],
            "interface_match": "all", "unmapped_conditions": [], "spec_attributes": [], "handoff_reason": None,
            "history_conflict": False, "model_dependency": "model_specific"}


def _targets(sq: dict, version: str | None) -> list[dict]:
    return resolve_sub_query(sq, routing_version=version)["retrieval_scope"]["targets"]


def _rules(resolved: dict) -> list[str]:
    return [w.split(":", 1)[1] for w in resolved["warnings"] if w.startswith("routing_rule:")]


SAMPLES = [
    _sq("Thông số của F86", "lookup.product_info", ["F86"]),
    _sq("Tham số #12100 trên F86 là gì", "lookup.product_info", ["F86"]),
    _sq("Cách đấu board 08_RLTR với F86", "guide.installation", ["F86"], ["08_RLTR"]),
    _sq("So sánh F86 và F54", "compare.product_models", ["F86", "F54"]),
    _sq("Có những dòng nào hỗ trợ EtherCAT", "lookup.product_catalog"),
    _sq("Địa chỉ công ty", "lookup.company_info"),
    _sq("Giá F86", "handoff.human", ["F86"]),
]


def test_production_version_is_r0_and_changes_nothing():
    assert ROUTING_VERSION == "r0" and ROUTING_RULES["r0"] == frozenset()
    for sq in SAMPLES:
        default = resolve_sub_query(sq)
        assert default == resolve_sub_query(sq, routing_version="r0")
        assert not _rules(default)
        if default["retrieval_scope"]:
            assert all("boost" not in t for t in default["retrieval_scope"]["targets"])
    assert _targets(SAMPLES[0], None) == [CATALOG]


def test_unknown_routing_version_is_rejected():
    assert routing_rules("RT-1+RT-3b") == frozenset({"RT-1", "RT-3b"})
    with pytest.raises(RegistryError):
        routing_rules("r99")
    with pytest.raises(RegistryError):
        resolve_sub_query(SAMPLES[0], routing_version="RT-1+RT-9")


def test_rt1_catalog_lookup_with_documented_model_also_searches_technical_docs():
    info = resolve_sub_query(SAMPLES[0], routing_version="r1")
    assert info["retrieval_scope"]["targets"] == CATALOG_FIRST and _rules(info) == ["RT-1"]
    assert info["retrieval_scope"]["model_filter"] == ["F86"] and info["route"] == "retrieve"
    # Theo điều kiện, không theo tên intent: lookup.product_catalog có model cũng tìm cả hai (K09, D39).
    with_model = _sq("Có những board I/O link nào cho F86", "lookup.product_catalog", ["F86"])
    assert _targets(with_model, "r1") == CATALOG_FIRST
    # Không áp: model chỉ có catalog, không có model, so sánh, intent không tra catalog.
    assert _targets(_sq("Thông số của F10T", "lookup.product_info", ["F10T"]), "r1") == [CATALOG]
    assert _targets(SAMPLES[4], "r1") == [CATALOG]
    assert _targets(SAMPLES[3], "r1") == [CATALOG]
    assert _targets(SAMPLES[5], "r1") == [{"domain": "company_info"}]
    guide = _sq("Cách đấu nguồn F86", "guide.installation", ["F86"])
    assert _targets(guide, "r1") == [{"domain": "technical_docs", "scopes": ["installation"]}]


@pytest.mark.parametrize("query", [
    "Tham số #12100 trên F86 là gì",
    "Cổng CN10 trên F86 dùng để làm gì?",
    "Chân X40 trên F86 là tín hiệu gì?",
    "toc do toi da truc khi chay G00 tren F86",
    "Tham số M1920 trên F86 có ý nghĩa gì?",
    "F86 báo mã lỗi E05 là gì",
])
def test_rt2_technical_code_makes_technical_docs_the_primary_target(query):
    resolved = resolve_sub_query(_sq(query, "lookup.product_info", ["F86"]), routing_version="r1")
    assert resolved["retrieval_scope"]["targets"] == DOCS_FIRST and _rules(resolved) == ["RT-1", "RT-2"]


@pytest.mark.parametrize("query", [
    "F86 có cổng RS485 không?", "F86 có mấy cổng USB2", "F86 dùng nguồn 24VDC phải không",
    "Astro 10iV và F86 khác gì", "Màn hình F86 bao nhiêu inch",
])
def test_rt2_does_not_fire_on_port_names_or_model_codes(query):
    assert ROUTING_CODE_PATTERN.search(query) is None
    assert _targets(_sq(query, "lookup.product_info", ["F86"]), "r1") == CATALOG_FIRST


def test_rt3_known_board_name_is_not_an_unknown_model():
    board = SAMPLES[2]
    old = resolve_sub_query(board)
    assert old["clarification"]["reason"] == "unknown_product_model" and not old["clarification"]["blocking"]
    assert old["entities"]["unresolved_mentions"] == ["08_RLTR"]
    # r0: sub-query không chặn nhưng bị planner giữ lại → không có task tra cứu (lỗi D26).
    held = build_analysis([board])
    assert held_sub_query_ids(held) == {"q1"}
    assert [t.kind for t in build_execution_plan(held).tasks] == [TaskKind.CLARIFY]

    new = resolve_sub_query(board, routing_version="r1")
    assert new["clarification"] is None and new["entities"]["unresolved_mentions"] == []
    assert new["route"] == "retrieve" and "non_model_mention:08_RLTR" in new["warnings"]
    assert _rules(new) == ["RT-3"]
    searched = build_analysis([board], routing_version="r1")
    assert held_sub_query_ids(searched) == set()
    assert [t.kind for t in build_execution_plan(searched).tasks] == [TaskKind.RETRIEVE]

    # Model gõ sai vẫn là model lạ; tên hãng khác không có trong danh sách thì RT-3 không xử lý.
    typo = resolve_sub_query(_sq("So sánh F86 với F84", "compare.product_models", ["F86"], ["F84"]),
                             routing_version="r1")
    assert typo["clarification"]["reason"] == "unknown_product_model"
    other = _sq("F86 nối với driver Yaskawa Sigma-7 được không", "lookup.product_info", ["F86"], ["Yaskawa Sigma-7"])
    assert resolve_sub_query(other, routing_version="r1")["clarification"]["reason"] == "unknown_product_model"


def test_rt3b_mention_without_any_similar_model_is_not_an_unknown_model():
    version = "RT-1+RT-2+RT-3b"
    other = _sq("F86 nối với driver Yaskawa Sigma-7 được không", "lookup.product_info", ["F86"], ["Yaskawa Sigma-7"])
    resolved = resolve_sub_query(other, routing_version=version)
    assert resolved["clarification"] is None and resolved["entities"]["unresolved_mentions"] == []
    assert "non_model_mention:Yaskawa Sigma-7" in resolved["warnings"] and "RT-3b" in _rules(resolved)
    board = resolve_sub_query(SAMPLES[2], routing_version=version)
    assert board["clarification"] is None and board["route"] == "retrieve"
    # "F84" có model gần giống (F86, F54) → vẫn hỏi lại, không âm thầm bỏ.
    typo = resolve_sub_query(_sq("Đấu nguồn F84 thế nào", "guide.installation", [], ["F84"]), routing_version=version)
    assert typo["clarification"]["reason"] == "unknown_product_model" and typo["clarification"]["blocking"]
    assert typo["clarification"]["candidates"]["F84"]
    # Không có model nào: cụm lạ bị bỏ → hỏi model như câu thiếu model, không báo "model lạ".
    no_model = resolve_sub_query(_sq("Driver servo QS đấu thế nào", "guide.installation", [], ["driver servo QS"]),
                                 routing_version=version)
    assert no_model["clarification"]["reason"] == "missing_product_model"


@pytest.mark.parametrize("query", [
    "công thức tính tỷ số truyền điện tử F86",
    "toc do toi da truc cai o dau tren F86",
    "Giới hạn hành trình mềm trục Y trên F86 đặt ở đâu?",
    "How do I set the electronic gear ratio on the F86?",
])
def test_rt4_configuration_wording_is_primary_only_in_r2(query):
    sq = _sq(query, "lookup.product_info", ["F86"])
    assert _targets(sq, "r1") == CATALOG_FIRST
    resolved = resolve_sub_query(sq, routing_version="r2")
    assert resolved["retrieval_scope"]["targets"] == DOCS_FIRST and _rules(resolved) == ["RT-1", "RT-4"]
    assert _targets(_sq("F86 có mấy trục", "lookup.product_info", ["F86"]), "r2") == CATALOG_FIRST


def test_target_boost_reaches_retrieval_requests():
    analysis = build_analysis([SAMPLES[1]], routing_version="r1")
    targets, fallback = build_retrieval_requests("task-1", analysis.sub_queries[0])
    assert [(r.domain, r.boost) for r in targets] == [("technical_docs", ROUTING_TARGET_BOOST),
                                                      ("product_catalog", 0.0)]
    assert fallback == []
    default = build_retrieval_requests("task-1", build_analysis([SAMPLES[1]]).sub_queries[0])[0]
    assert [(r.domain, r.boost) for r in default] == [("product_catalog", 0.0)]


def _match(chunk_id: int, fused: float) -> ChunkMatch:
    return ChunkMatch.model_validate({
        "id": chunk_id, "parent_id": None, "chunk_key": f"d:B{chunk_id}", "chunk_role": "standalone",
        "chunk_type": "table", "doc_id": "d", "section_title": "S", "section_path": ["A"], "page_start": 1,
        "page_end": 1, "content": "c", "assets": [], "vector_score": 0.6, "keyword_score": None, "code_score": None,
        "vector_rank": 1, "keyword_rank": None, "code_rank": None, "fused_score": fused,
    })


def _run(domain: str, boost: float, matches: list[ChunkMatch]) -> _SearchRun:
    request = RetrievalRequest(task_id="t", domain=domain, boost=boost,
                               queries=[RetrievalQuery(sub_query_id="q1", query="q", answer_mode="full")])
    return _SearchRun(request=request, models=None, matches=matches, latency_ms=0)


def test_merge_adds_target_boost_when_ranking_across_targets():
    retriever = Retriever(embedder=None, repository=None)  # type: ignore[arg-type]
    catalog = [_match(1, 0.0320), _match(2, 0.0300)]
    docs = [_match(11, 0.0328), _match(12, 0.0310)]
    # Không cộng điểm: xếp thuần theo fused (hành vi cũ).
    plain = retriever._merge([_run("product_catalog", 0.0, catalog), _run("technical_docs", 0.0, docs)])
    assert [m.id for m in plain] == [11, 1, 12, 2]
    # Catalog là target chính (+0,003): chunk catalog lên trước, chunk manual vẫn vào danh sách.
    boosted = retriever._merge([_run("product_catalog", 0.003, catalog), _run("technical_docs", 0.0, docs)])
    assert [m.id for m in boosted] == [1, 2, 11, 12]
    assert boosted[0].fused_score == 0.0320            # điểm của chunk không bị sửa
