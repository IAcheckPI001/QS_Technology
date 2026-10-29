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
    retriever = _retriever(repository, final_chunk_top_k=2)

    result = asyncio.run(retriever.search([
        _request(domain="product_catalog", scopes=(), models=("F86", "F54"), mode="comparison"),
    ]))

    assert [call["models"] for call in repository.calls] == [["F86"], ["F54"]]
    assert [hit.chunk_id for hit in result.hits] == ["1", "3"]


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
