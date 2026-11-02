"""Pipeline tra cứu dùng chung cho luồng chat và tool `product_docs_ask` của agent."""

from app.modules.chatbot.schemas.system import RunState
from app.modules.chatbot.stages.analysis_stage import AnalysisStage
from app.modules.chatbot.stages.catalog_lookup_stage import CatalogLookupStage
from app.modules.chatbot.stages.clarification_resume_stage import ClarificationResumeStage
from app.modules.chatbot.stages.execution_stage import ExecutionStage, SourceAllocator


class RetrievalPipeline:
    """Clarification resume → analysis → giới hạn hỏi lại → [catalog lookup] → execution.

    Không compose câu trả lời. Catalog lookup chỉ được cấu hình cho tool của agent:
    luồng chat (website) không đổi hành vi.
    """

    def __init__(
        self,
        clarification_stage: ClarificationResumeStage,
        analysis_stage: AnalysisStage,
        execution_stage: ExecutionStage,
        catalog_stage: CatalogLookupStage | None = None,
    ) -> None:
        self._clarification_stage = clarification_stage
        self._analysis_stage = analysis_stage
        self._execution_stage = execution_stage
        self._catalog_stage = catalog_stage

    async def run(
        self,
        state: RunState,
        source_allocator: SourceAllocator | None = None,
    ) -> RunState:
        await self._clarification_stage.execute(state)
        await self._analysis_stage.execute(state)
        self._clarification_stage.apply_attempt_limit(state)
        if self._catalog_stage is not None:
            self._catalog_stage.execute(state)
        if source_allocator is None:
            await self._execution_stage.execute(state)
        else:
            await self._execution_stage.execute(state, source_allocator)
        return state
