"""Deterministic handlers for routes that do not need retrieval.

Handlers only turn analysis data into a structured task result; they never
call the LLM. The final wording is produced once per turn by AnswerComposer.
RETRIEVE has no handler yet, so the scheduler marks it
`handler_not_configured` until retrieval is implemented.
"""

from app.modules.chatbot.schemas.system import (
    Analysis,
    ExecutionTask,
    NormalizedTaskResult,
    SubQueryAnalysis,
    TaskKind,
    TaskStatus,
)

from .scheduler import TaskHandler


def build_task_handlers(analysis: Analysis) -> dict[str, TaskHandler]:
    sub_queries = {sub_query.id: sub_query for sub_query in analysis.sub_queries}

    def sub_query_for(task: ExecutionTask) -> SubQueryAnalysis:
        return sub_queries[task.sub_query_ids[0]]

    def completed(
        task: ExecutionTask,
        status: TaskStatus = TaskStatus.COMPLETED,
        **metadata: str,
    ) -> NormalizedTaskResult:
        return NormalizedTaskResult(
            task_id=task.task_id,
            status=status,
            content=sub_query_for(task).standalone_query,
            metadata={"kind": task.kind.value, **metadata},
        )

    async def handle_direct(task: ExecutionTask) -> NormalizedTaskResult:
        return completed(task)

    async def handle_no_docs(task: ExecutionTask) -> NormalizedTaskResult:
        sub_query = sub_query_for(task)
        models = sub_query.unsupported_models or sub_query.entities.product_models
        return completed(task, unsupported_models=",".join(models))

    async def handle_handoff(task: ExecutionTask) -> NormalizedTaskResult:
        reason = sub_query_for(task).handoff_reason or "human_request"
        return completed(task, TaskStatus.HANDED_OFF, handoff_reason=reason)

    return {
        TaskKind.CHITCHAT.value: handle_direct,
        TaskKind.OUT_OF_SCOPE.value: handle_direct,
        TaskKind.NO_DOCS.value: handle_no_docs,
        TaskKind.HANDOFF.value: handle_handoff,
    }
