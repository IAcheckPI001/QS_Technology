
class Stage(Protocol):
    name: str
    async def execute(self, state: RunState) -> StageResult: ...   # CONTINUE | BREAK | ABORT

class Pipeline:
    setup: list[Stage]       # [ContextStage]
    iteration: list[Stage]   # [Prune, Think, Tool, Observe, Checkpoint]
    finalize: list[Stage]    # [FinalizeStage]
    max_iterations: int = 3