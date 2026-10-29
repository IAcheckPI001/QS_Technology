import logging

from app.modules.chatbot.schemas.system import RunState, RunContext
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.analysis.analyzer import AnalysisError, QueryAnalyzer, build_analysis
from app.modules.chatbot.analysis.prompt.registry_render import _j
from app.modules.chatbot.clarification import patch_pending
from app.modules.chatbot.extraction.validate_registry import guard_extracted_models

logger = logging.getLogger(__name__)


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
        if state and state.for_llm():
            parts.append(f"<state>{_j(state.for_llm())}</state>")
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

        context = state.context
        last_models = context.conversation.state.last_models
        active_model = context.conversation.state.active_model
        data = await self.analyzer.analyze_raw(self.build_context_analysis(context))
        evidence = "\n".join([
            context.query.origin,
            *(message.content for message in context.conversation.history),
            *last_models,
        ])
        raw_sub_queries = guard_extracted_models(list(data["sub_queries"]), evidence)
        pending = context.conversation.state.pending
        answer = data.get("pending_answer") if pending else None
        if pending and answer:
            # Held sub-queries first so they survive the MAX_SUB_QUERIES cap.
            raw_sub_queries = [*patch_pending(pending, answer), *raw_sub_queries]
        elif pending and not raw_sub_queries and not pending.blocking:
            # "ok cảm ơn" after a general answer: an acknowledgement, not a choice.
            raw_sub_queries = [_acknowledgement(context.query.origin)]
        elif pending and not raw_sub_queries:
            # Reply to the clarification that answers nothing (e.g. "ok" with
            # several candidates): keep the held sub-queries and ask again.
            # resumed=True counts the attempt so the loop stops at the limit.
            held = list(pending.llm_raw.get("sub_queries") or [])
            if held:
                state.analysis = build_analysis(
                    held, resumed=True, last_models=last_models, active_model=active_model,
                )
                state.analysis.language = _language(data.get("language"))
                return state
        if not raw_sub_queries:
            # LLM không tách được ý nào và không còn ý đang chờ (nhận xét, "ok", "cảm ơn"…):
            # trả lời như chitchat thay vì báo analysis_invalid_output cho khách.
            logger.info("analysis returned no sub-query; treating as acknowledgement")
            raw_sub_queries = [_acknowledgement(context.query.origin)]
        state.analysis = build_analysis(
            raw_sub_queries,
            pending_answer=answer or None,
            resumed=bool(pending and answer),
            last_models=last_models,
            active_model=active_model,
        )
        state.analysis.language = _language(data.get("language"))
        return state


def _language(value: object) -> str | None:
    """ISO 639-1 từ output LLM ("en", "EN", "en-US" -> "en"); giá trị lạ -> None."""
    if not isinstance(value, str):
        return None
    code = value.strip().lower().replace("_", "-").split("-", 1)[0]
    return code if len(code) == 2 and code.isascii() and code.isalpha() else None


def _acknowledgement(query: str) -> dict:
    """Chitchat sub-query for a reply that neither answers nor asks anything."""
    return {
        "standalone_query": query,
        "intent": "other.chitchat",
        "product_models": [],
        "unresolved_mentions": [],
        "control_interface": [],
        "spec_attributes": [],
        "handoff_reason": None,
        "history_conflict": False,
        "model_dependency": "general",
    }
