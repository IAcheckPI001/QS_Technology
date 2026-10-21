"""Derive the persisted conversation state after a bot turn."""

from typing import Literal

from app.modules.chatbot.schemas.system import (
    MAX_LAST_MODELS,
    ConversationState,
    PendingClarification,
    RunState,
    TaskKind,
    TaskStatus,
)

PENDING_TTL = 2


def update_conversation_state(state: RunState) -> ConversationState:
    if state.context is None or state.analysis is None or state.plan is None:
        raise ValueError("conversation state update requires context, analysis and plan")

    current = state.context.conversation.state
    analysis = state.analysis
    held_ids = [
        sub_query_id
        for task in state.plan.tasks
        if task.kind is TaskKind.CLARIFY and task.status is TaskStatus.BLOCKED
        for sub_query_id in task.sub_query_ids
    ]
    held_raws = [
        analysis.raw_sub_queries[sub_query_id]
        for sub_query_id in held_ids
        if sub_query_id in analysis.raw_sub_queries
    ]

    if held_raws:
        pending = _pending(state, held_ids, held_raws)
        attempts = current.clarify_attempts + 1 if analysis.resumed else 1
    elif analysis.resumed or current.pending is None:
        pending, attempts = None, 0
    else:
        # A new question while a clarification is pending: keep it for a while.
        ttl = current.pending.ttl - 1
        pending = current.pending.model_copy(update={"ttl": ttl}) if ttl > 0 else None
        attempts = current.clarify_attempts if pending else 0

    models = [
        model
        for sub_query in analysis.sub_queries
        for model in sub_query.entities.product_models
    ]
    last_models = list(dict.fromkeys(models))[-MAX_LAST_MODELS:] or current.last_models
    return current.model_copy(update={
        "pending": pending,
        "clarify_attempts": attempts,
        "last_models": last_models,
        "last_intent": analysis.sub_queries[0].intent,
    })


def _pending(
    state: RunState,
    held_ids: list[str],
    held_raws: list[dict],
) -> PendingClarification:
    analysis = state.analysis
    assert analysis is not None
    sub_queries = {sub_query.id: sub_query for sub_query in analysis.sub_queries}
    clarification = analysis.clarification
    if clarification is None or clarification.sub_query_id not in held_ids:
        clarification = next(
            (
                sub_queries[sub_query_id].clarification
                for sub_query_id in held_ids
                if sub_queries[sub_query_id].clarification is not None
            ),
            None,
        )
    reason = clarification.reason if clarification else "unclear_query"
    mentions = list(clarification.mentions) if clarification else []
    focus = mentions[0] if mentions else reason

    known_models = {
        model
        for sub_query_id in held_ids
        for model in sub_queries[sub_query_id].entities.product_models
    }
    candidates = [
        candidate
        for candidate in (clarification.candidates.get(focus, []) if clarification else [])
        if candidate not in known_models
    ]
    question_type: Literal["confirm", "choose", "open"] = (
        "confirm" if len(candidates) == 1 else "choose" if candidates else "open"
    )
    return PendingClarification(
        focus=focus,
        question_type=question_type,
        candidates=candidates,
        llm_raw={"sub_queries": held_raws, "mentions": mentions, "reason": reason},
        ttl=PENDING_TTL,
    )
