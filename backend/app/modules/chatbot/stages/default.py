
from enum import StrEnum
from typing import Protocol, TypeVar


class StageAction(StrEnum):
    CONTINUE = "continue"
    BLOCK = "block"
    REVIEW = "review"


StageResultT = TypeVar("StageResultT")
StateT = TypeVar("StateT")


class Stage(Protocol[StateT, StageResultT]):
    name: str

    async def execute(self, state: StateT) -> StageResultT:
        """Execute one pipeline stage without owning transport concerns."""


class Pipeline:
    setup: list[Stage]
    iteration: list[Stage]
    finalize: list[Stage]
    max_iterations: int = 3