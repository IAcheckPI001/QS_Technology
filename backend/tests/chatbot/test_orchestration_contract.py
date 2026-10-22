import pytest
import asyncio
from pydantic import ValidationError

from app.modules.chatbot.orchestration.collector import collect_results
from app.modules.chatbot.orchestration.planner import build_execution_plan
from app.modules.chatbot.orchestration.scheduler import ExecutionScheduler
from app.modules.chatbot.schemas.system import (
    ExecutionPlan,
    ExecutionTask,
    NormalizedTaskResult,
    RetrievalRequest,
    RetrievalResult,
    RetrievalSubQueryResult,
    TaskKind,
    TaskStatus,
)
from app.modules.chatbot.extraction.validate_registry import plan_turn, resolve
from app.modules.chatbot.schemas.system import Analysis


def _analysis(raw: dict) -> Analysis:
    return Analysis.from_plan(plan_turn(resolve(raw)))


def test_execution_plan_preserves_independent_mixed_routes():
    analysis = _analysis({
        "sub_queries": [
            {
                "standalone_query": "Giá F86",
                "intent": "handoff.human",
                "product_models": ["F86"],
                "unresolved_mentions": [],
                "control_interface": [],
                "spec_attribute": [],
                "handoff_reason": "pricing",
                "history_conflict": False,
            },
            {
                "standalone_query": "F86 có cổng USB không?",
                "intent": "lookup.product_info",
                "product_models": ["F86"],
                "unresolved_mentions": [],
                "control_interface": [],
                "spec_attribute": ["ports"],
                "handoff_reason": None,
                "history_conflict": False,
            },
        ],
    })

    plan = build_execution_plan(analysis)

    assert [task.kind for task in plan.tasks] == [
        TaskKind.HANDOFF,
        TaskKind.RETRIEVE,
    ]
    assert all(task.status is TaskStatus.PENDING for task in plan.tasks)


def test_execution_plan_searches_each_retrieval_sub_query_separately():
    analysis = _analysis({
        "sub_queries": [
            {
                "standalone_query": "F86 cấu hình như nào?",
                "intent": "guide.configuration",
                "product_models": ["F86"],
                "unresolved_mentions": [],
                "control_interface": [],
                "spec_attribute": [],
                "handoff_reason": None,
                "history_conflict": False,
            },
            {
                "standalone_query": "F86 cần backup ra sao?",
                "intent": "guide.configuration",
                "product_models": ["F86"],
                "unresolved_mentions": [],
                "control_interface": [],
                "spec_attribute": [],
                "handoff_reason": None,
                "history_conflict": False,
            },
        ],
    })

    plan = build_execution_plan(analysis)

    # Cùng batch (domain, model_filter) vẫn tách task: mỗi sub-query tra cứu bằng
    # target của chính nó; scheduler chạy các task song song.
    retrieve_tasks = [task for task in plan.tasks if task.kind is TaskKind.RETRIEVE]
    assert [task.task_id for task in retrieve_tasks] == ["task-retrieve-q1", "task-retrieve-q2"]
    assert [task.sub_query_ids for task in retrieve_tasks] == [["q1"], ["q2"]]


def test_blocking_clarification_blocks_only_related_task():
    analysis = _analysis({
        "sub_queries": [{
            "standalone_query": "Hướng dẫn đấu nguồn Astro 6A",
            "intent": "guide.installation",
            "product_models": [],
            "unresolved_mentions": ["Astro 6A"],
            "control_interface": [],
            "spec_attribute": [],
            "handoff_reason": None,
            "history_conflict": False,
        }],
    })

    plan = build_execution_plan(analysis)

    assert plan.tasks[0].status is TaskStatus.BLOCKED


def test_execution_plan_rejects_unknown_dependency_and_cycles():
    with pytest.raises(ValidationError):
        ExecutionPlan(tasks=[ExecutionTask(
            task_id="task-a",
            kind=TaskKind.RETRIEVE,
            sub_query_ids=["q1"],
            depends_on=["task-missing"],
        )])

    with pytest.raises(ValidationError):
        ExecutionPlan(tasks=[
            ExecutionTask(task_id="task-a", kind=TaskKind.RETRIEVE, sub_query_ids=["q1"], depends_on=["task-b"]),
            ExecutionTask(task_id="task-b", kind=TaskKind.RETRIEVE, sub_query_ids=["q2"], depends_on=["task-a"]),
        ])


def test_scheduler_runs_independent_tasks_and_collects_in_plan_order():
    plan = ExecutionPlan(tasks=[
        ExecutionTask(task_id="task-a", kind=TaskKind.RETRIEVE, sub_query_ids=["q1"]),
        ExecutionTask(task_id="task-b", kind=TaskKind.HANDOFF, sub_query_ids=["q2"]),
    ])
    running: list[str] = []

    async def handler(task):
        running.append(task.task_id)
        await asyncio.sleep(0)
        return NormalizedTaskResult(task_id=task.task_id, status=(
            TaskStatus.HANDED_OFF if task.kind is TaskKind.HANDOFF else TaskStatus.COMPLETED
        ))

    result = asyncio.run(ExecutionScheduler({
        "retrieve": handler,
        "handoff": handler,
    }).run(plan))

    assert set(running) == {"task-a", "task-b"}
    assert [item.task_id for item in collect_results(result)] == ["task-a", "task-b"]
    assert result.status_summary() == {TaskStatus.COMPLETED, TaskStatus.HANDED_OFF}


def test_scheduler_blocks_dependent_task_after_failure():
    plan = ExecutionPlan(tasks=[
        ExecutionTask(task_id="task-a", kind=TaskKind.RETRIEVE, sub_query_ids=["q1"]),
        ExecutionTask(task_id="task-b", kind=TaskKind.HANDOFF, sub_query_ids=["q2"], depends_on=["task-a"]),
    ])

    async def failing_handler(task):
        raise RuntimeError("internal detail must not leak")

    result = asyncio.run(ExecutionScheduler({"retrieve": failing_handler}).run(plan))

    assert result.tasks[0].status is TaskStatus.FAILED
    assert result.tasks[1].status is TaskStatus.BLOCKED
    assert result.tasks[0].result.error.code == "task_execution_failed"


def test_retrieval_result_maps_each_sub_query_id():
    request = RetrievalRequest(
        task_id="task-retrieve-1",
        domain="technical_docs",
        scopes=["configuration"],
        model_filter=["F86"],
        queries=[
            {"sub_query_id": "q1", "query": "F86 cấu hình như nào?", "answer_mode": "full"},
            {"sub_query_id": "q2", "query": "F86 backup ra sao?", "answer_mode": "full"},
        ],
    )
    result = RetrievalResult(
        task_id=request.task_id,
        results=[
            RetrievalSubQueryResult(sub_query_id="q1"),
            RetrievalSubQueryResult(sub_query_id="q2"),
        ],
    )

    assert [item.sub_query_id for item in result.results] == ["q1", "q2"]


def test_retrieval_result_requires_explicit_partial_ids():
    result = RetrievalResult(
        task_id="task-retrieve-1",
        results=[RetrievalSubQueryResult(sub_query_id="q1")],
        missing_sub_query_ids=["q2"],
    )

    assert result.missing_sub_query_ids == ["q2"]


def test_scheduler_limits_concurrency():
    plan = ExecutionPlan(tasks=[
        ExecutionTask(task_id="task-a", kind=TaskKind.RETRIEVE, sub_query_ids=["q1"]),
        ExecutionTask(task_id="task-b", kind=TaskKind.RETRIEVE, sub_query_ids=["q2"]),
    ])
    active = 0
    max_active = 0

    async def handler(task):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return NormalizedTaskResult(task_id=task.task_id, status=TaskStatus.COMPLETED)

    asyncio.run(ExecutionScheduler({"retrieve": handler}, max_concurrency=1).run(plan))

    assert max_active == 1
