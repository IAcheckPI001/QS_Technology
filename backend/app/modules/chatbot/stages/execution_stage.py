from app.modules.chatbot.orchestration import (
    ExecutionScheduler,
    build_execution_plan,
    build_task_handlers,
)
from app.modules.chatbot.retrieval import Retriever
from app.modules.chatbot.schemas.system import (
    Candidate,
    RetrievalResult,
    RetrievalSubQueryResult,
    RetrievalTrace,
    RunState,
)


class ExecutionError(RuntimeError):
    """The execution plan could not be built or run."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ExecutionStage:
    name = "execution_stage"

    def __init__(
        self,
        max_concurrency: int = 4,
        retriever: Retriever | None = None,
    ) -> None:
        self._max_concurrency = max_concurrency
        self._retriever = retriever

    async def execute(
        self,
        state: RunState,
        source_allocator: "SourceAllocator | None" = None,
    ) -> RunState:
        if state.analysis is None:
            raise ExecutionError("analysis_missing", "Execution requires an analysis plan.")

        plan = build_execution_plan(state.analysis)
        scheduler = ExecutionScheduler(
            build_task_handlers(state.analysis, self._retriever),
            max_concurrency=self._max_concurrency,
        )
        state.plan = await scheduler.run(plan)
        assign_source_ids(state, source_allocator)
        return state


class SourceAllocator:
    """Cấp S# cho chunk context; chunk đã có S# dùng lại số cũ.

    Một lượt agent gọi tra cứu nhiều lần (có thể song song): dùng chung một
    allocator để S# không trùng giữa các lần gọi. Gán đồng bộ, không await, nên
    an toàn giữa các coroutine của cùng event loop.
    """

    def __init__(self, next_number: int = 1) -> None:
        self._next_number = next_number
        self._assigned: dict[str, str] = {}

    @classmethod
    def for_state(cls, state: RunState) -> "SourceAllocator":
        return cls(int(state.next_source_id()[1:]))

    def source_id(self, chunk_id: str) -> str:
        source_id = self._assigned.get(chunk_id)
        if source_id is None:
            source_id = f"S{self._next_number}"
            self._next_number += 1
            self._assigned[chunk_id] = source_id
        return source_id


def assign_source_ids(state: RunState, allocator: SourceAllocator | None = None) -> None:
    """Gán S# cho chunk context theo thứ tự task, sau khi mọi task chạy xong.

    Task retrieve chạy song song nên không gán trong handler: thứ tự S# phải
    ổn định. Chunk xuất hiện ở nhiều sub-query dùng chung một S#. Candidate
    trong trace được đánh selected khi chunk con của nó nằm trong context.
    """
    if state.plan is None:
        return
    allocator = allocator or SourceAllocator.for_state(state)

    for task in state.plan.tasks:
        result = task.result
        if result is None or result.retrieval is None:
            continue
        sub_results: list[RetrievalSubQueryResult] = []
        for sub_result in result.retrieval.results:
            hits = []
            selected: dict[str, str] = {}
            for hit in sub_result.hits:
                source_id = allocator.source_id(hit.chunk_id)
                hits.append(hit.model_copy(update={"source_id": source_id}))
                selected.update({chunk_id: source_id for chunk_id in hit.matched_chunk_ids})
            traces = [_select_candidates(trace, selected) for trace in sub_result.traces]
            for trace in traces:
                state.add_trace(trace)
            sub_results.append(sub_result.model_copy(update={"hits": hits, "traces": traces}))
        task.result = result.model_copy(update={
            "retrieval": RetrievalResult(
                task_id=result.retrieval.task_id,
                results=sub_results,
                missing_sub_query_ids=result.retrieval.missing_sub_query_ids,
                metadata=result.retrieval.metadata,
            ),
        })


def _select_candidates(trace: RetrievalTrace, selected: dict[str, str]) -> RetrievalTrace:
    candidates = [
        Candidate(
            chunk_id=candidate.chunk_id,
            source_id=selected[candidate.chunk_id],
            selected=True,
            scores=candidate.scores,
            metadata=candidate.metadata,
        )
        if candidate.chunk_id in selected and candidate.reject_reason is None
        else candidate
        for candidate in trace.candidates
    ]
    return trace.model_copy(update={"candidates": candidates})
