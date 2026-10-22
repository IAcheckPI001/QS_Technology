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
    """Create one task per sub-query.

    Retrieval sub-queries are not grouped by `analysis.batches`: each one is
    searched with its own targets so that different intents in the same turn
    do not share merged scopes. The scheduler runs them concurrently.
    """
    tasks: list[ExecutionTask] = []
    held = held_sub_query_ids(analysis)

    for sub_query in analysis.sub_queries:
        if sub_query.id in held:
            tasks.append(ExecutionTask(
                task_id=f"task-{sub_query.id}",
                kind=TaskKind.CLARIFY,
                sub_query_ids=[sub_query.id],
                status=TaskStatus.BLOCKED,
            ))
            continue
        if sub_query.route is Route.RETRIEVE:
            tasks.append(ExecutionTask(
                task_id=f"task-retrieve-{sub_query.id}",
                kind=TaskKind.RETRIEVE,
                sub_query_ids=[sub_query.id],
            ))
            continue
        tasks.append(ExecutionTask(
            task_id=f"task-{sub_query.id}",
            kind=TaskKind(sub_query.route.value),
            sub_query_ids=[sub_query.id],
        ))
    return ExecutionPlan(tasks=tasks)
