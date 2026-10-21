

from app.modules.chatbot.schemas.system import RunState, RunContext
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.analysis.analyzer import AnalysisError, QueryAnalyzer, build_analysis
from app.modules.chatbot.analysis.prompt.registry_render import _j
from app.modules.chatbot.clarification import patch_pending

class AnalysisStage:
    name = "analysis_stage"

    def __init__(
        self,
        provider: OpenAIProvider,
        n_examples: int = 4
    ) -> None:
        self.analyzer = QueryAnalyzer(provider=provider, n_examples=n_examples)

    def build_context_analysis(self, context: RunContext) -> str:
        parts = []
        history = [
            {"role": item.role, "content": item.content}
            for item in context.conversation.history
        ]
        query = context.query.origin
        state = context.conversation.state
        if state and state.last_models:
            parts.append(f"<state>{_j({'last_models': state.last_models})}</state>")
        if history:
            parts.append(f"<history>\n{history}\n</history>")
        if state and state.pending:
            pending = {
                "focus": state.pending.focus,
                "candidates": state.pending.candidates,
                "held_queries": [
                    sub_query.get("standalone_query")
                    for sub_query in state.pending.llm_raw.get("sub_queries") or []
                ],
            }
            parts.append(f"<pending>{_j(pending)}</pending>")
        parts.append(f"<query>{query}</query>")
        return "\n".join(parts)

    async def execute(self, state: RunState) -> RunState:
        if state.context is None:
            raise AnalysisError("analysis_context_missing", "Analysis requires a loaded context.")
        if state.analysis is not None:
            # Already resumed from a pending clarification without the LLM.
            return state

        data = await self.analyzer.analyze_raw(self.build_context_analysis(state.context))
        print(f"AnalysisStage.execute: data={data}")
        raw_sub_queries = list(data["sub_queries"])
        pending = state.context.conversation.state.pending
        answer = data.get("pending_answer") if pending else None
        if pending and answer:
            # Held sub-queries first so they survive the MAX_SUB_QUERIES cap.
            raw_sub_queries = [*patch_pending(pending, answer), *raw_sub_queries]
        state.analysis = build_analysis(
            raw_sub_queries,
            pending_answer=answer or None,
            resumed=bool(pending and answer),
        )
        return state
