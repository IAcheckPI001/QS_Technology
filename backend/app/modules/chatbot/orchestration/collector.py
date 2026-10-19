from app.modules.chatbot.schemas.system import (
    ExecutionPlan,
    NormalizedTaskResult,
    TaskStatus,
)


def collect_results(plan: ExecutionPlan) -> list[NormalizedTaskResult]:
    """Return task results in plan order for deterministic answer composition."""
    results: list[NormalizedTaskResult] = []
    for task in plan.tasks:
        if task.result is not None:
            results.append(task.result)
            continue
        results.append(NormalizedTaskResult(
            task_id=task.task_id,
            status=task.status,
            metadata={"reason": "task_not_executed"},
        ))
    return results


def summarize_statuses(results: list[NormalizedTaskResult]) -> set[TaskStatus]:
    return {result.status for result in results}
