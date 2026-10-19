from app.modules.chatbot.schemas.system import (
    Analysis,
    ExecutionPlan,
    ExecutionTask,
    TaskKind,
    TaskStatus,
    Route,
)


def build_execution_plan(analysis: Analysis) -> ExecutionPlan:
    """Create route tasks, grouping retrieval sub-queries by analysis batches."""
    tasks: list[ExecutionTask] = []
    sub_queries = {sub_query.id: sub_query for sub_query in analysis.sub_queries}
    retrieval_groups = {
        sub_query_id: (index, batch.sub_query_ids)
        for index, batch in enumerate(analysis.batches)
        for sub_query_id in batch.sub_query_ids
        if sub_query_id in sub_queries
        and sub_queries[sub_query_id].route is Route.RETRIEVE
    }
    created_retrieval_tasks: set[int] = set()

    for sub_query in analysis.sub_queries:
        if sub_query.route is Route.RETRIEVE and sub_query.id in retrieval_groups:
            batch_index, batch_ids = retrieval_groups[sub_query.id]
            if batch_index in created_retrieval_tasks:
                continue
            created_retrieval_tasks.add(batch_index)
            tasks.append(ExecutionTask(
                task_id=f"task-retrieve-{batch_index + 1}",
                kind=TaskKind.RETRIEVE,
                sub_query_ids=[
                    sub_query_id
                    for sub_query_id in batch_ids
                    if sub_query_id in sub_queries
                ],
            ))
            continue
        kind = TaskKind(sub_query.route.value)
        status = (
            TaskStatus.BLOCKED
            if sub_query.clarification and sub_query.clarification.blocking
            else TaskStatus.PENDING
        )
        tasks.append(ExecutionTask(
            task_id=f"task-{sub_query.id}",
            kind=kind,
            sub_query_ids=[sub_query.id],
            status=status,
        ))
    return ExecutionPlan(tasks=tasks)
