"""Execution contracts for the chatbot orchestration layer."""

from enum import StrEnum

from pydantic import Field, model_validator

from ..default import NonEmptyStr, SystemModel
from .retrieval import RetrievalResult


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    HANDED_OFF = "handed_off"


class TaskKind(StrEnum):
    RETRIEVE = "retrieve"
    CLARIFY = "clarify"
    HANDOFF = "handoff"
    CHITCHAT = "chitchat"
    OUT_OF_SCOPE = "out_of_scope"
    NO_DOCS = "no_docs"


class TaskError(SystemModel):
    code: NonEmptyStr
    message: NonEmptyStr


class NormalizedTaskResult(SystemModel):
    task_id: NonEmptyStr
    status: TaskStatus
    content: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    error: TaskError | None = None
    retrieval: RetrievalResult | None = None

    @model_validator(mode="after")
    def validate_error_state(self) -> "NormalizedTaskResult":
        if self.status is TaskStatus.FAILED and self.error is None:
            raise ValueError("failed task result requires error")
        if self.status is not TaskStatus.FAILED and self.error is not None:
            raise ValueError("only failed task result may contain error")
        if self.retrieval is not None and self.retrieval.task_id != self.task_id:
            raise ValueError("retrieval result id must match task id")
        return self


class ExecutionTask(SystemModel):
    task_id: NonEmptyStr
    kind: TaskKind
    sub_query_ids: list[NonEmptyStr] = Field(min_length=1)
    depends_on: list[NonEmptyStr] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: NormalizedTaskResult | None = None

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ExecutionTask":
        if self.task_id in self.depends_on:
            raise ValueError("task cannot depend on itself")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("task dependencies must be unique")
        if self.result is not None and self.result.task_id != self.task_id:
            raise ValueError("task result id must match task id")
        if self.result is not None and self.result.retrieval is not None:
            result_ids = {
                result.sub_query_id
                for result in self.result.retrieval.results
            }
            missing_ids = set(self.result.retrieval.missing_sub_query_ids)
            task_ids = set(self.sub_query_ids)
            if not result_ids <= task_ids or not missing_ids <= task_ids:
                raise ValueError("retrieval result contains unknown sub-query id")
            if result_ids | missing_ids != task_ids:
                raise ValueError(
                    "retrieval result must account for every task sub-query id"
                )
        if self.status is TaskStatus.HANDED_OFF and self.kind is not TaskKind.HANDOFF:
            raise ValueError("only handoff task may be handed off")
        return self


class ExecutionPlan(SystemModel):
    tasks: list[ExecutionTask] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_graph(self) -> "ExecutionPlan":
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("execution task ids must be unique")
        known_ids = set(task_ids)
        for task in self.tasks:
            unknown = set(task.depends_on) - known_ids
            if unknown:
                raise ValueError(f"unknown task dependency: {sorted(unknown)!r}")
        if self._has_cycle():
            raise ValueError("execution task dependencies must be acyclic")
        return self

    def _has_cycle(self) -> bool:
        graph = {task.task_id: set(task.depends_on) for task in self.tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> bool:
            if task_id in visiting:
                return True
            if task_id in visited:
                return False
            visiting.add(task_id)
            if any(visit(dependency) for dependency in graph[task_id]):
                return True
            visiting.remove(task_id)
            visited.add(task_id)
            return False

        return any(visit(task_id) for task_id in graph)

    def status_summary(self) -> set[TaskStatus]:
        """Return the current task statuses without inventing a plan status."""
        return {task.status for task in self.tasks}
