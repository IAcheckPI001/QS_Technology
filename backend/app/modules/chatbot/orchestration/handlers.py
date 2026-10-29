"""Task handlers for each route.

Handlers only turn analysis data into a structured task result; they never
call the LLM. The final wording is produced once per turn by AnswerComposer.
RETRIEVE is handled only when a Retriever is injected; without one the
scheduler marks it `handler_not_configured`.
"""

import logging

from app.modules.chatbot.retrieval import Retriever
from app.modules.chatbot.schemas.system import (
    Analysis,
    ExecutionTask,
    NormalizedTaskResult,
    RetrievalQuery,
    RetrievalRequest,
    RetrievalResult,
    RetrievalTarget,
    SubQueryAnalysis,
    TaskError,
    TaskKind,
    TaskStatus,
)

from .scheduler import TaskHandler

logger = logging.getLogger(__name__)


def build_retrieval_requests(
    task_id: str,
    sub_query: SubQueryAnalysis,
) -> tuple[list[RetrievalRequest], list[RetrievalRequest]]:
    """Map a sub-query's retrieval plan to (targets, fallback targets) requests."""
    plan = sub_query.retrieval_scope
    if plan is None:
        raise ValueError(f"sub-query {sub_query.id} has no retrieval scope")
    query = RetrievalQuery(
        sub_query_id=sub_query.id,
        query=sub_query.standalone_query,
        answer_mode=plan.answer_mode,
    )

    def request(target: RetrievalTarget) -> RetrievalRequest:
        return RetrievalRequest(
            task_id=task_id,
            domain=target.domain,
            scopes=target.scopes,
            model_filter=plan.model_filter,
            product_scope_mode=plan.product_scope_mode,
            control_interface=sub_query.entities.control_interface,
            spec_attributes=sub_query.entities.spec_attributes,
            queries=[query],
        )

    return (
        [request(target) for target in plan.targets],
        [request(target) for target in plan.fallback_targets],
    )


def build_task_handlers(
    analysis: Analysis,
    retriever: Retriever | None = None,
) -> dict[str, TaskHandler]:
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

    async def handle_retrieve(task: ExecutionTask) -> NormalizedTaskResult:
        assert retriever is not None
        sub_query = sub_query_for(task)
        try:
            targets, fallback_targets = build_retrieval_requests(task.task_id, sub_query)
            result = await retriever.search(targets, fallback_targets)
        except Exception:
            logger.exception("retrieval failed for task %s", task.task_id)
            return NormalizedTaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                metadata={"kind": task.kind.value},
                error=TaskError(
                    code="retrieval_error",
                    message="Document retrieval failed.",
                ),
            )
        return NormalizedTaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            content=sub_query.standalone_query,
            metadata={"kind": task.kind.value, **result.metadata},
            retrieval=RetrievalResult(task_id=task.task_id, results=[result]),
        )

    handlers: dict[str, TaskHandler] = {
        TaskKind.CHITCHAT.value: handle_direct,
        TaskKind.OUT_OF_SCOPE.value: handle_direct,
        TaskKind.NO_DOCS.value: handle_no_docs,
        TaskKind.HANDOFF.value: handle_handoff,
    }
    if retriever is not None:
        handlers[TaskKind.RETRIEVE.value] = handle_retrieve
    return handlers
