from collections.abc import Awaitable, Callable
import asyncio

from app.modules.chatbot.schemas.system import (
    ExecutionPlan,
    ExecutionTask,
    NormalizedTaskResult,
    TaskError,
    TaskStatus,
)

TaskHandler = Callable[[ExecutionTask], Awaitable[NormalizedTaskResult]]


class ExecutionScheduler:
    """Run dependency-ready tasks without knowing route implementation details."""

    def __init__(
        self,
        handlers: dict[str, TaskHandler],
        max_concurrency: int = 4,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self._handlers = handlers
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run(self, plan: ExecutionPlan) -> ExecutionPlan:
        remaining = {task.task_id for task in plan.tasks}
        tasks = {task.task_id: task for task in plan.tasks}

        while remaining:
            ready = [
                tasks[task_id]
                for task_id in remaining
                if tasks[task_id].status is TaskStatus.PENDING
                and all(tasks[dependency].status in {
                    TaskStatus.COMPLETED,
                    TaskStatus.HANDED_OFF,
                } for dependency in tasks[task_id].depends_on)
            ]
            blocked = [
                tasks[task_id]
                for task_id in remaining
                if tasks[task_id].status is TaskStatus.BLOCKED
                or any(tasks[dependency].status in {
                    TaskStatus.BLOCKED,
                    TaskStatus.FAILED,
                } for dependency in tasks[task_id].depends_on)
            ]

            for task in blocked:
                reason = (
                    "task_blocked"
                    if task.status is TaskStatus.BLOCKED
                    else "dependency_not_completed"
                )
                task.status = TaskStatus.BLOCKED
                if task.result is None:
                    task.result = NormalizedTaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.BLOCKED,
                        metadata={"reason": reason},
                    )
                remaining.remove(task.task_id)

            if not ready:
                if remaining:
                    raise RuntimeError("execution plan has no runnable task")
                break

            await asyncio.gather(*(self._run_task(task) for task in ready))
            for task in ready:
                remaining.remove(task.task_id)

        return plan

    async def _run_task(self, task: ExecutionTask) -> None:
        if task.status is TaskStatus.BLOCKED:
            if task.result is None:
                task.result = NormalizedTaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.BLOCKED,
                    metadata={"reason": "task_blocked"},
                )
            return

        handler = self._handlers.get(task.kind.value)
        if handler is None:
            task.status = TaskStatus.FAILED
            task.result = NormalizedTaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=TaskError(
                    code="handler_not_configured",
                    message="No handler configured for execution task.",
                ),
            )
            return

        async with self._semaphore:
            task.status = TaskStatus.RUNNING
            try:
                result = await handler(task)
                if result.task_id != task.task_id:
                    raise ValueError("handler returned mismatched task id")
                task.status = result.status
                task.result = result
            except Exception:
                task.status = TaskStatus.FAILED
                task.result = NormalizedTaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    error=TaskError(
                        code="task_execution_failed",
                        message="Execution task failed.",
                    ),
                )
