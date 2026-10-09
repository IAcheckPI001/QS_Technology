
"""RunState – object duy nhất đi xuyên qua các stage của một request."""

from pydantic import Field

from ..default import SystemModel, NonNegInt
from ..inbound import InboundRequest
from .analysis import Analysis
from .retrieval import Candidate, RetrievalTrace
from .run_context import RunContext
from .run_stats import RunStats
from .security import SecurityDecision



class RunState(SystemModel):
    input: InboundRequest
    context: RunContext | None = None          # Context stage
    analysis: Analysis | None = None           # Context stage
    retrieval_traces: list[RetrievalTrace] = Field(default_factory=list)  # Tool stage
    stats: RunStats = Field(default_factory=RunStats)
    iteration: NonNegInt = 0
    security: SecurityDecision | None = None

    # --- Source registry: suy ra từ trace, không lưu trùng ---------------
    def sources(self) -> dict[str, Candidate]:
        """source_id → candidate đã được chọn, qua mọi lần retrieval."""
        return {
            c.source_id: c
            for t in self.retrieval_traces
            for c in t.candidates
            if c.selected and c.source_id
        }

    def next_source_id(self) -> str:
        """Cấp ID S# mới, tiếp nối các S# đã dùng trong history và run hiện tại."""
        used = set(self.sources())
        if self.context:
            for m in self.context.conversation.history:
                used.update(c.source_id for c in m.citations)
        n = max((int(s[1:]) for s in used), default=0)
        return f"S{n + 1}"

    def add_trace(self, trace: RetrievalTrace) -> None:
        self.retrieval_traces = [*self.retrieval_traces, trace]