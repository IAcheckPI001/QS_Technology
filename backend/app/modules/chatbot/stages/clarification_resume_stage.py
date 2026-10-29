from app.modules.chatbot.analysis.analyzer import build_analysis
from app.modules.chatbot.clarification import (
    MAX_CLARIFY_ATTEMPTS,
    exhaust_clarification,
    match_confirmation,
    patch_pending,
)
from app.modules.chatbot.schemas.system import RunState


class ClarificationResumeStage:
    """Resume held sub-queries when the reply clearly answers a pending clarification.

    Runs before AnalysisStage. A deterministic match builds the analysis
    without calling the LLM; any other reply is left to AnalysisStage, which
    sees the pending clarification and may report `pending_answer`.
    """

    name = "clarification_resume_stage"

    async def execute(self, state: RunState) -> RunState:
        if state.context is None or state.analysis is not None:
            return state
        pending = state.context.conversation.state.pending
        if pending is None:
            return state

        answer = match_confirmation(state.context.query.origin, pending)
        if answer is None:
            return state
        state.analysis = build_analysis(
            patch_pending(pending, answer),
            pending_answer=answer,
            resumed=True,
            last_models=state.context.conversation.state.last_models,
            active_model=state.context.conversation.state.active_model,
        )
        return state

    def apply_attempt_limit(self, state: RunState) -> RunState:
        """After analysis: stop re-asking once the attempt limit is reached."""
        if state.context is None or state.analysis is None or not state.analysis.resumed:
            return state
        if state.context.conversation.state.clarify_attempts >= MAX_CLARIFY_ATTEMPTS:
            state.analysis = exhaust_clarification(state.analysis)
        return state
