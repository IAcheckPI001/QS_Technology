import asyncio
import json
import re

from app.modules.chatbot.extraction.validate_registry import plan_turn, resolve
from app.modules.chatbot.orchestration import build_execution_plan
from app.modules.chatbot.retrieval import Retriever, RetrieverConfig
from app.modules.chatbot.schemas.system import (
    Analysis,
    ChunkMatch,
    ChunkRecord,
    Conversation,
    QueryInfo,
    RetrievalQuery,
    RetrievalRequest,
    RetrievalScope,
    RunContext,
    RunState,
    TaskKind,
    TaskStatus,
)
from app.modules.chatbot.stages.answer_composer import AnswerComposer
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from tests.chatbot.builders import make_run_state


class FakeEmbedder:
    def __init__(self):
        self.calls: list[list[str]] = []

    async def embed(self, texts):
        self.calls.append(list(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeRepository:
    """Trả kết quả theo (domain, scopes, models); ghi lại mọi lời gọi."""

    def __init__(self, results=None, parents=(), error=None):
        self.results = results or {}
        self.parents = {record.id: record for record in parents}
        self.error = error
        self.calls: list[dict] = []

    async def match(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)
        key = (kwargs["domain"], tuple(kwargs["scopes"]), tuple(kwargs["models"] or ()))
        return list(self.results.get(key, []))

    async def fetch_by_ids(self, ids):
        return [self.parents[i] for i in ids if i in self.parents]


def _match(chunk_id, *, vector=0.6, fused=0.03, parent_id=None, keyword=None):
    return ChunkMatch(
        id=chunk_id,
        parent_id=parent_id,
        doc_id="f86_installation",
        section_title=f"Section {chunk_id}",
        section_path=["Part 1", f"Section {chunk_id}"],
        page_start=chunk_id,
        content=f"content {chunk_id}",
        assets=[{"bucket": "f86-docs", "path": f"p{chunk_id:03}.jpg", "page": chunk_id, "extra": 1}],
        vector_score=vector,
        keyword_score=keyword,
        fused_score=fused,
    )


def _parent(chunk_id):
    return ChunkRecord(
        id=chunk_id,
        doc_id="f86_installation",
        section_title=f"Parent {chunk_id}",
        content=f"parent content {chunk_id}",
    )


def _request(domain="technical_docs", scopes=("installation",), models=("F86",), mode="single"):
    return RetrievalRequest(
        task_id="task-retrieve-q1",
        domain=domain,
        scopes=list(scopes),
        model_filter=list(models) if models is not None else None,
        product_scope_mode=mode,
        queries=[RetrievalQuery(sub_query_id="q1", query="Lắp đặt F86", answer_mode="full")],
    )


def _sub_query(query, intent, models=(), spec=()):
    return {
        "standalone_query": query,
        "intent": intent,
        "product_models": list(models),
        "unresolved_mentions": [],
        "control_interface": [],
        "spec_attributes": list(spec),
        "handoff_reason": None,
        "history_conflict": False,
    }


def _analysis(*sub_queries) -> Analysis:
    return Analysis.from_plan(plan_turn(resolve({"sub_queries": list(sub_queries)})))


def _state(query, analysis) -> RunState:
    state = make_run_state(query, message_id="request-1")
    state.context = RunContext(
        conversation=Conversation(history=[]),
        query=QueryInfo(origin=query),
        retrieval_scope=RetrievalScope(collections=["crm-technical"]),
    )
    state.analysis = analysis
    return state


def _retriever(repository, **config):
    return Retriever(FakeEmbedder(), repository, RetrieverConfig(**config))


def test_planner_creates_one_retrieve_task_per_sub_query():
    analysis = _analysis(
        _sub_query("Cách lắp đặt F86", "guide.installation", ["F86"]),
        _sub_query("F86 báo lỗi E05", "troubleshoot.error", ["F86"]),
        _sub_query("Thông số F54", "lookup.product_info", ["F54"]),
    )

    plan = build_execution_plan(analysis)

    assert [task.task_id for task in plan.tasks] == [
        "task-retrieve-q1", "task-retrieve-q2", "task-retrieve-q3",
    ]
    assert all(task.kind is TaskKind.RETRIEVE for task in plan.tasks)
    assert [task.sub_query_ids for task in plan.tasks] == [["q1"], ["q2"], ["q3"]]


def test_each_intent_is_searched_with_its_own_filter():
    repository = FakeRepository()
    analysis = _analysis(
        _sub_query("Cách lắp đặt F86", "guide.installation", ["F86"]),
        _sub_query("F86 báo lỗi E05", "troubleshoot.error", ["F86"]),
        _sub_query("Kích thước F54", "lookup.product_info", ["F54"], spec=["dimension"]),
    )
    state = _state("Lắp đặt F86, lỗi E05 và kích thước F54", analysis)

    asyncio.run(ExecutionStage(retriever=_retriever(repository)).execute(state))

    searched = sorted(
        (call["domain"], tuple(call["scopes"]), tuple(call["models"] or ()), tuple(call["spec_attributes"]))
        for call in repository.calls
    )
    assert ("technical_docs", ("installation",), ("F86",), ()) in searched
    assert ("technical_docs", ("maintenance",), ("F86",), ()) in searched
    assert ("product_catalog", (), ("F54",), ("dimension",)) in searched
    # Không có lần tra cứu nào dùng scopes hợp nhất của batch.
    assert all(len(scopes) <= 1 for _, scopes, _, _ in searched)


def test_fallback_target_is_used_when_primary_has_no_relevant_chunk():
    repository = FakeRepository({
        ("technical_docs", ("maintenance",), ("F86",)): [_match(1, vector=0.1)],
        ("technical_docs", (), ("F86",)): [_match(2, vector=0.7)],
    })
    retriever = _retriever(repository, min_similarity=0.25)

    result = asyncio.run(retriever.search(
        [_request(scopes=("maintenance",))],
        [_request(scopes=())],
    ))

    assert [hit.chunk_id for hit in result.hits] == ["2"]
    assert result.metadata == {"fallback": "true"}
    assert [len(trace.candidates) for trace in result.traces] == [1, 1]
    assert result.traces[0].candidates[0].reject_reason == "below_similarity"


def test_no_relevant_chunk_reports_no_hits():
    repository = FakeRepository({
        ("technical_docs", ("installation",), ("F86",)): [_match(1, vector=0.05)],
    })

    result = asyncio.run(_retriever(repository).search([_request()]))

    assert result.hits == []
    assert result.metadata == {"no_hits": "true"}


def test_children_expand_to_parent_and_respect_limits():
    repository = FakeRepository(
        {("technical_docs", ("installation",), ("F86",)): [
            _match(11, fused=0.050, parent_id=10),
            _match(12, fused=0.040, parent_id=10),
            _match(21, fused=0.030),
            _match(31, fused=0.020, parent_id=30),
            _match(41, fused=0.010),
        ]},
        parents=[_parent(10)],   # parent 30 không còn active
    )
    retriever = _retriever(repository, final_chunk_top_k=4, max_context_parents=2)

    result = asyncio.run(retriever.search([_request()]))

    assert [hit.chunk_id for hit in result.hits] == ["10", "21"]
    assert result.hits[0].matched_chunk_ids == ["11", "12"]
    assert result.hits[0].content == "parent content 10"
    assert result.hits[1].assets[0].path == "p021.jpg"
    reasons = {c.chunk_id: c.reject_reason for c in result.traces[0].candidates}
    assert reasons == {
        "11": None, "12": None, "21": None,
        "31": "context_limit", "41": "below_top_k",
    }


def test_hits_carry_chunk_metadata_from_doc_chunks():
    parent = _parent(10).model_copy(update={
        "domain": "technical_docs",
        "scopes": ["installation", "maintenance"],
        "control_interface": ["pulse_train", "EtherCAT"],
        "spec_attributes": ["io", "max_axis"],
    })
    standalone = ChunkRecord(
        id=21,
        doc_id="f86_installation",
        section_title="Section 21",
        content="content 21",
        domain="technical_docs",
        scopes=["operation"],
    )
    repository = FakeRepository(
        {("technical_docs", ("installation",), ("F86",)): [
            _match(11, fused=0.050, parent_id=10),
            _match(21, fused=0.030),
        ]},
        parents=[parent, standalone],
    )

    result = asyncio.run(_retriever(repository).search([_request()]))

    # Metadata lấy từ chính chunk, không phải từ filter của request.
    assert result.hits[0].scopes == ["installation", "maintenance"]
    assert result.hits[0].control_interface == ["pulse_train", "EtherCAT"]
    assert result.hits[1].scopes == ["operation"]
    assert result.metadata == {}


def test_inactive_parent_falls_back_to_child():
    repository = FakeRepository({
        ("technical_docs", ("installation",), ("F86",)): [_match(31, parent_id=30)],
    })

    result = asyncio.run(_retriever(repository).search([_request()]))

    assert [hit.chunk_id for hit in result.hits] == ["31"]


def test_comparison_searches_each_model_and_interleaves():
    repository = FakeRepository({
        ("product_catalog", (), ("F86",)): [_match(1, fused=0.09), _match(2, fused=0.08)],
        ("product_catalog", (), ("F54",)): [_match(3, fused=0.02), _match(4, fused=0.01)],
    })
    retriever = _retriever(repository, final_chunk_top_k=2, compare_per_model=1)

    result = asyncio.run(retriever.search([
        _request(domain="product_catalog", scopes=(), models=("F86", "F54"), mode="comparison"),
    ]))

    assert [call["models"] for call in repository.calls] == [["F86"], ["F54"]]
    assert [hit.chunk_id for hit in result.hits] == ["1", "3"]


def test_comparison_gives_each_model_its_own_quota():
    """Đợt 1 gói E: model có điểm thấp vẫn được đủ hạn mức, không bị model kia chiếm top-k chung."""
    repository = FakeRepository({
        ("product_catalog", (), ("F86",)): [_match(i, fused=0.09 - i / 1000) for i in range(1, 5)],
        ("product_catalog", (), ("F54",)): [_match(i, fused=0.02 - i / 1000) for i in range(11, 15)],
    })
    retriever = _retriever(repository, final_chunk_top_k=2, max_context_parents=2, compare_per_model=3)

    result = asyncio.run(retriever.search([
        _request(domain="product_catalog", scopes=(), models=("F86", "F54"), mode="comparison"),
    ]))

    ids = [hit.chunk_id for hit in result.hits]
    assert ids == ["1", "11", "2", "12", "3", "13"]


def test_comparison_keeps_each_models_own_chunks_before_shared_tables():
    """Kiểm thật 2026-11-20: bảng chọn model (khớp cả hai model, điểm cao) chiếm hết hạn mức nên
    thiếu chunk tổng quan có số trục. Chunk chung giờ có hạn mức riêng, sau chunk riêng của từng model."""
    table_a, table_b, table_c = _match(90, fused=0.2), _match(91, fused=0.19), _match(92, fused=0.18)
    repository = FakeRepository({
        ("product_catalog", (), ("F86",)): [table_a, table_b, table_c, _match(1, fused=0.05), _match(2, fused=0.04)],
        ("product_catalog", (), ("F54",)): [table_a, table_b, table_c, _match(11, fused=0.03)],
    })
    retriever = _retriever(repository, compare_per_model=2, compare_shared=1)

    result = asyncio.run(retriever.search([
        _request(domain="product_catalog", scopes=(), models=("F86", "F54"), mode="comparison"),
    ]))

    # Riêng: F86 2 chunk, F54 1 chunk (thiếu 1 suất) → chung: 1 + 1 suất chưa dùng = 2 bảng.
    assert [hit.chunk_id for hit in result.hits] == ["1", "11", "2", "90", "91"]


SELECTION_TABLE = "\n".join([
    "MOTION CONTROLLER",
    "General",
    "| Specification | F54 | F86 | F10T | ASTRO-10S |",
    "|---|---|---|---|---|",
    "| Max. PLC Axis control | 0 | 6 | 6 | 14 |",
    "| Max.Spindle Simultaneous Control | 2 | 4 | 4 | 4 |",
])


def test_comparison_trims_selection_tables_to_compared_models():
    """Kiểm thật 2026-11-20: cột F54 bị đọc thành giá trị của F86 khi so F86–F10T."""
    table = _match(90, fused=0.2).model_copy(update={"content": SELECTION_TABLE})
    repository = FakeRepository({
        ("product_catalog", (), ("F86",)): [table, _match(1, fused=0.05)],
        ("product_catalog", (), ("F10T",)): [table, _match(11, fused=0.04)],
    })

    result = asyncio.run(_retriever(repository).search([
        _request(domain="product_catalog", scopes=(), models=("F86", "F10T"), mode="comparison"),
    ]))

    content = next(hit.content for hit in result.hits if hit.chunk_id == "90")
    assert "| Specification | F86 | F10T |" in content
    assert "| Max. PLC Axis control | 6 | 6 |" in content
    assert "F54" not in content and "ASTRO" not in content
    assert content.startswith("MOTION CONTROLLER\nGeneral")


def test_non_comparison_keeps_tables_untouched():
    table = _match(90, fused=0.2).model_copy(update={"content": SELECTION_TABLE})
    repository = FakeRepository({("product_catalog", (), ("F86",)): [table]})

    result = asyncio.run(_retriever(repository).search([_request(domain="product_catalog", scopes=(), models=("F86",))]))

    assert result.hits[0].content == SELECTION_TABLE


def test_trim_model_columns_keeps_non_model_columns_and_odd_tables():
    from app.modules.chatbot.extraction.validate_registry import models_in_text
    from app.modules.chatbot.retrieval.table_columns import trim_model_columns

    with_unit = "| Item | Unit | F54 | F86 |\n|---|---|---|---|\n| Voltage | V | 24 | 24 |"
    assert trim_model_columns(with_unit, {"F86"}, models_in_text) == (
        "| Item | Unit | F86 |\n| --- | --- | --- |\n| Voltage | V | 24 |"
    )
    # Bảng không có cột của model được hỏi: giữ nguyên.
    assert trim_model_columns(with_unit, {"F10T"}, models_in_text) == with_unit
    # Dòng lệch số cột: không đoán, giữ nguyên.
    ragged = "| Item | F54 | F86 |\n|---|---|---|\n| A | 1 |"
    assert trim_model_columns(ragged, {"F86"}, models_in_text) == ragged


def test_default_comparison_quota_is_two_own_and_four_shared():
    from app.modules.chatbot.retrieval import RetrieverConfig

    assert (RetrieverConfig().compare_per_model, RetrieverConfig().compare_shared) == (2, 4)


def test_non_comparison_keeps_global_top_k():
    repository = FakeRepository({
        ("product_catalog", (), ("F86",)): [_match(i, fused=0.09 - i / 1000) for i in range(1, 5)],
    })
    retriever = _retriever(repository, final_chunk_top_k=2, compare_per_model=3)

    result = asyncio.run(retriever.search([_request(domain="product_catalog", scopes=(), models=("F86",))]))

    assert [hit.chunk_id for hit in result.hits] == ["1", "2"]


def test_retrieval_error_marks_task_failed():
    repository = FakeRepository(error=RuntimeError("db down"))
    state = _state("Cách lắp đặt F86", _analysis(
        _sub_query("Cách lắp đặt F86", "guide.installation", ["F86"]),
    ))

    asyncio.run(ExecutionStage(retriever=_retriever(repository)).execute(state))

    task = state.plan.tasks[0]
    assert task.status is TaskStatus.FAILED
    assert task.result.error.code == "retrieval_error"


def test_source_ids_are_stable_and_shared_across_sub_queries():
    shared = _match(5, fused=0.05)
    repository = FakeRepository({
        ("technical_docs", ("installation",), ("F86",)): [_match(1, fused=0.06), shared],
        ("technical_docs", ("operation",), ("F86",)): [shared, _match(7, fused=0.01)],
    })
    state = _state("Lắp đặt và vận hành F86", _analysis(
        _sub_query("Cách lắp đặt F86", "guide.installation", ["F86"]),
        _sub_query("Cách vận hành F86", "guide.operation", ["F86"]),
    ))

    asyncio.run(ExecutionStage(retriever=_retriever(repository)).execute(state))

    hits = [
        [(hit.chunk_id, hit.source_id) for hit in task.result.retrieval.results[0].hits]
        for task in state.plan.tasks
    ]
    assert hits == [[("1", "S1"), ("5", "S2")], [("5", "S2"), ("7", "S3")]]
    assert sorted(state.sources()) == ["S1", "S2", "S3"]
    assert all(task.status is TaskStatus.COMPLETED for task in state.plan.tasks)


def test_answer_prompt_contains_sources_per_sub_query():
    repository = FakeRepository({
        ("technical_docs", ("installation",), ("F86",)): [_match(1)],
    })
    state = _state("Cách lắp đặt F86", _analysis(
        _sub_query("Cách lắp đặt F86", "guide.installation", ["F86"]),
    ))
    asyncio.run(ExecutionStage(retriever=_retriever(repository)).execute(state))

    content = AnswerComposer(provider=None, source_char_limit=5).build_messages(state)[-1]["content"]

    match = re.search(r"<sources>(.*)</sources>", content)
    assert match is not None
    assert json.loads(match.group(1)) == [{
        "query": "Cách lắp đặt F86",
        "answer_mode": "full",
        "sources": [{
            "source_id": "S1",
            "section": "Part 1 › Section 1",
            "pages": "1",
            "content": "conte",
        }],
    }]
