import asyncio

from app.modules.chatbot.extraction.validate_registry import plan_turn, resolve
from app.modules.chatbot.orchestration import (
    ExecutionScheduler,
    build_execution_plan,
    build_task_handlers,
    collect_results,
)
from app.modules.chatbot.schemas.system import Analysis, TaskKind, TaskStatus


def _sub_query(query, intent, models=(), handoff_reason=None, unresolved=()):
    return {
        "standalone_query": query,
        "intent": intent,
        "product_models": list(models),
        "unresolved_mentions": list(unresolved),
        "control_interface": [],
        "spec_attribute": [],
        "handoff_reason": handoff_reason,
        "history_conflict": False,
    }


def _run(*sub_queries):
    analysis = Analysis.from_plan(plan_turn(resolve({"sub_queries": list(sub_queries)})))
    plan = build_execution_plan(analysis)
    return asyncio.run(ExecutionScheduler(build_task_handlers(analysis)).run(plan))


def test_chitchat_task_completes_without_llm():
    plan = _run(_sub_query("Xin chào", "other.chitchat"))

    task = plan.tasks[0]
    assert task.kind is TaskKind.CHITCHAT
    assert task.status is TaskStatus.COMPLETED
    assert task.result.content == "Xin chào"
    assert task.result.metadata == {"kind": "chitchat"}


def test_out_of_scope_task_completes():
    plan = _run(_sub_query("Viết giúp tôi một bài thơ", "other.out_of_scope"))

    assert plan.tasks[0].kind is TaskKind.OUT_OF_SCOPE
    assert plan.tasks[0].status is TaskStatus.COMPLETED


def test_no_docs_task_reports_unsupported_models():
    plan = _run(_sub_query("F54 báo lỗi alarm", "troubleshoot.error", ["F54"]))

    task = plan.tasks[0]
    assert task.kind is TaskKind.NO_DOCS
    assert task.status is TaskStatus.COMPLETED
    assert task.result.metadata["unsupported_models"] == "F54"


def test_handoff_task_is_handed_off_with_reason():
    plan = _run(_sub_query("Giá F86 bao nhiêu?", "handoff.human", ["F86"], "pricing"))

    task = plan.tasks[0]
    assert task.status is TaskStatus.HANDED_OFF
    assert task.result.metadata["handoff_reason"] == "pricing"


def test_blocking_clarification_is_blocked_without_handler():
    plan = _run(_sub_query(
        "Hướng dẫn đấu nguồn Astro 6A",
        "guide.installation",
        unresolved=["Astro 6A"],
    ))

    task = plan.tasks[0]
    assert task.kind is TaskKind.CLARIFY
    assert task.status is TaskStatus.BLOCKED
    assert task.result.metadata == {"reason": "task_blocked"}


def test_retrieve_task_fails_until_retrieval_handler_exists():
    plan = _run(_sub_query("Hướng dẫn đấu nguồn F54", "guide.installation", ["F54"]))

    task = plan.tasks[0]
    assert task.kind is TaskKind.RETRIEVE
    assert task.status is TaskStatus.FAILED
    assert task.result.error.code == "handler_not_configured"


def test_mixed_turn_collects_results_in_plan_order():
    plan = _run(
        _sub_query("Xin chào", "other.chitchat"),
        _sub_query("Giá F86 bao nhiêu?", "handoff.human", ["F86"], "pricing"),
    )

    results = collect_results(plan)
    assert [result.task_id for result in results] == ["task-q1", "task-q2"]
    assert [result.status for result in results] == [
        TaskStatus.COMPLETED,
        TaskStatus.HANDED_OFF,
    ]
