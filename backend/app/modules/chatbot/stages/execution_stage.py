from app.modules.chatbot.orchestration import (
    ExecutionScheduler,
    build_execution_plan,
    build_task_handlers,
)
from app.modules.chatbot.schemas.system import RunState


class ExecutionError(RuntimeError):
    """The execution plan could not be built or run."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ExecutionStage:
    name = "execution_stage"

    def __init__(self, max_concurrency: int = 4) -> None:
        self._max_concurrency = max_concurrency

    async def execute(self, state: RunState) -> RunState:
        if state.analysis is None:
            raise ExecutionError("analysis_missing", "Execution requires an analysis plan.")

        plan = build_execution_plan(state.analysis)
        scheduler = ExecutionScheduler(
            build_task_handlers(state.analysis),
            max_concurrency=self._max_concurrency,
        )
        state.plan = await scheduler.run(plan)
        return state
