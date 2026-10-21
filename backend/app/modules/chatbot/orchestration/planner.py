from app.modules.chatbot.schemas.system import (
    Analysis,
    ExecutionPlan,
    ExecutionTask,
    TaskKind,
    TaskStatus,
    Route,
)


def held_sub_query_ids(analysis: Analysis) -> set[str]:
    """Sub-queries waiting for the turn clarification.

    A sub-query is held when its own clarification is blocking, or when it
    shares an unresolved mention with the turn clarification (e.g. "F84 vs
    F54" must not be answered with F54 only while F84 is being clarified).
    """
    mentions = set(analysis.clarification.mentions) if analysis.clarification else set()
    return {
        sub_query.id
        for sub_query in analysis.sub_queries
        if (sub_query.clarification is not None and sub_query.clarification.blocking)
        or (mentions and mentions & set(sub_query.entities.unresolved_mentions))
    }


def build_execution_plan(analysis: Analysis) -> ExecutionPlan:
    """Create route tasks, grouping retrieval sub-queries by analysis batches."""
    tasks: list[ExecutionTask] = []
    sub_queries = {sub_query.id: sub_query for sub_query in analysis.sub_queries}
    held = held_sub_query_ids(analysis)
    retrieval_groups = {
        sub_query_id: (index, [
            batch_id for batch_id in batch.sub_query_ids
            if batch_id in sub_queries and batch_id not in held
        ])
        for index, batch in enumerate(analysis.batches)
        for sub_query_id in batch.sub_query_ids
        if sub_query_id in sub_queries
        and sub_query_id not in held
        and sub_queries[sub_query_id].route is Route.RETRIEVE
    }
    created_retrieval_tasks: set[int] = set()

    for sub_query in analysis.sub_queries:
        if sub_query.id in held:
            tasks.append(ExecutionTask(
                task_id=f"task-{sub_query.id}",
                kind=TaskKind.CLARIFY,
                sub_query_ids=[sub_query.id],
                status=TaskStatus.BLOCKED,
            ))
            continue
        if sub_query.route is Route.RETRIEVE and sub_query.id in retrieval_groups:
            batch_index, batch_ids = retrieval_groups[sub_query.id]
            if batch_index in created_retrieval_tasks:
                continue
            created_retrieval_tasks.add(batch_index)
            tasks.append(ExecutionTask(
                task_id=f"task-retrieve-{batch_index + 1}",
                kind=TaskKind.RETRIEVE,
                sub_query_ids=batch_ids,
            ))
            continue
        tasks.append(ExecutionTask(
            task_id=f"task-{sub_query.id}",
            kind=TaskKind(sub_query.route.value),
            sub_query_ids=[sub_query.id],
        ))
    return ExecutionPlan(tasks=tasks)
