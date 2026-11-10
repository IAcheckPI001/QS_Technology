"""Pipeline tra cứu dùng chung cho luồng chat và tool `product_docs_ask` của agent."""

from app.core.tracing import span
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
        # Span chỉ ghi mã định tuyến (intent, route, trạng thái task), không ghi câu hỏi.
        with span("stage.clarification", "stage") as clarification_span:
            await self._clarification_stage.execute(state)
            # pending: phiên đang chờ trả lời câu hỏi lại; resumed: lượt này nối tiếp nó
            # (analysis dựng từ pending, không gọi LLM).
            clarification_span.set(
                pending=_has_pending(state),
                resumed=state.analysis is not None and state.analysis.resumed,
            )
        with span("stage.analysis", "stage") as analysis_span:
            await self._analysis_stage.execute(state)
            self._clarification_stage.apply_attempt_limit(state)
            if state.analysis is not None:
                analysis_span.set(
                    sub_queries=len(state.analysis.sub_queries),
                    intents=[sub_query.intent for sub_query in state.analysis.sub_queries],
                    routes=[sub_query.route.value for sub_query in state.analysis.sub_queries],
                )
        if self._catalog_stage is not None:
            with span("stage.catalog_lookup", "stage") as catalog_span:
                self._catalog_stage.execute(state)
                match = state.catalog_match
                catalog_span.set(matched=match is not None)
                if match is not None:
                    catalog_span.set(next_action=match.next_action, models=len(match.models))
        with span("stage.execution", "stage") as execution_span:
            if source_allocator is None:
                await self._execution_stage.execute(state)
            else:
                await self._execution_stage.execute(state, source_allocator)
            if state.plan is not None:
                execution_span.set(
                    tasks=[f"{task.kind.value}:{task.status.value}" for task in state.plan.tasks],
                )
        return state


def _has_pending(state: RunState) -> bool:
    context = state.context
    return context is not None and context.conversation.state.pending is not None
