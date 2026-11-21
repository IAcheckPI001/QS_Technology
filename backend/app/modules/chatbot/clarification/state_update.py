"""Derive the persisted conversation state after a bot turn."""

from typing import Literal

from app.modules.chatbot.schemas.system import (
    MAX_LAST_MODELS,
    ConversationState,
    PendingClarification,
    RunState,
    SessionFacts,
    TaskKind,
    TaskStatus,
    ToolMemory,
)
from app.modules.chatbot.schemas.system.facts import FACT_TTL_TURNS, MAX_ENTITIES, MAX_LOOKUPS

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

    general = _general_pending(state)
    if held_raws:
        pending = _pending(state, held_ids, held_raws)
        attempts = current.clarify_attempts + 1 if analysis.resumed else 1
    elif general is not None:
        # The general answer ended by asking for a model: a reply like "F86"
        # re-runs the question for that model. It is not an attempt.
        pending, attempts = general, 0
    elif analysis.resumed or current.pending is None:
        pending, attempts = None, 0
    else:
        # A new question while a clarification is pending: keep it for a while.
        ttl = current.pending.ttl - 1
        pending = current.pending.model_copy(update={"ttl": ttl}) if ttl > 0 else None
        attempts = current.clarify_attempts if pending else 0

    turn_models = [
        model
        for sub_query in analysis.sub_queries
        for model in sub_query.entities.product_models
    ]
    return current.model_copy(update={
        "pending": pending,
        "clarify_attempts": attempts,
        **_model_context(current, turn_models),
        "language": state.context.query.language,
        "last_intent": analysis.sub_queries[0].intent,
    })


def update_agent_conversation_state(state: RunState, turn_models: list[str]) -> ConversationState:
    """State sau một lượt agent: ngữ cảnh model và facts (định danh tool đã trả, Đợt 1 gói A).

    Không PendingClarification (agent hỏi lại qua history, facts.pending_reason) và không handoff. turn_models do
    tool có khái niệm model cung cấp (tra cứu tài liệu: model của các lần tra cứu
    có nguồn, theo thứ tự gọi); lượt chỉ dùng tool khác thì rỗng và ngữ cảnh giữ nguyên.
    """
    if state.context is None:
        raise ValueError("conversation state update requires context")
    current = state.context.conversation.state
    update = _model_context(current, turn_models)
    if state.agent is not None:
        update["facts"] = merge_facts(
            current.facts, state.agent.memory, state.principal.acting_user_id, state.agent.final_reason,
        )
    return current.model_copy(update=update)


# Lượt kết thúc bằng câu hỏi làm rõ hoặc dừng sớm: lượt sau có thể là câu trả lời cho câu hỏi đó.
_PENDING_REASONS = {"ambiguous", "plateau", "budget", "limit"}


def merge_facts(
    current: SessionFacts,
    memory: list[ToolMemory],
    owner: str | None,
    final_reason: str | None,
) -> SessionFacts:
    """facts sau một lượt agent (Đợt 1 gói A, L2). Hàm thuần.

    - Đổi nhân viên của phiên: bỏ facts cũ.
    - Danh sách mới (tool trả list có dòng): xoá ordinal của mọi mục cũ, nên "câu N" luôn là dòng
      N của danh sách gần nhất.
    - Mục trùng (cùng bảng + id, hoặc cùng khoá) được cập nhật và đưa về cuối (mới nhất).
    - Mục không được tool trả lại sau FACT_TTL_TURNS lượt bị bỏ; giữ tối đa MAX_ENTITIES/MAX_LOOKUPS mục mới nhất.
    """
    facts = current if current.owner in (None, owner) else SessionFacts()
    turn = facts.turn + 1
    entities = list(facts.entities)
    lookups = list(facts.lookups)
    for item in memory:
        if item.is_list and item.entities:
            entities = [entity.model_copy(update={"ordinal": None}) for entity in entities]
        for new in item.entities:
            old = next((entity for entity in entities if entity.same_as(new)), None)
            merged = new.model_copy(update={
                "turn": turn,
                "keys": {**(old.keys if old else {}), **new.keys},
                "label": new.label or (old.label if old else ""),
                "ordinal": new.ordinal if item.is_list else (old.ordinal if old else None),
            })
            entities = [entity for entity in entities if entity is not old] + [merged]
        if item.lookup is not None:
            lookups.append(item.lookup.model_copy(update={"turn": turn}))
    entities = [entity for entity in entities if turn - entity.turn < FACT_TTL_TURNS][-MAX_ENTITIES:]
    lookups = [lookup for lookup in lookups if turn - lookup.turn < FACT_TTL_TURNS][-MAX_LOOKUPS:]
    return SessionFacts(
        turn=turn,
        owner=owner,
        entities=entities,
        lookups=lookups,
        pending_reason=final_reason if final_reason in _PENDING_REASONS else None,
    )


def _model_context(current: ConversationState, turn_models: list[str]) -> dict:
    turn_models = list(dict.fromkeys(turn_models))
    # Accumulate oldest -> newest; a model mentioned again moves to the end.
    last_models = [model for model in current.last_models if model not in turn_models]
    last_models = [*last_models, *turn_models][-MAX_LAST_MODELS:]
    # active_model: the only model of this turn; a multi-model turn (comparison)
    # clears it; a turn without models (chitchat, company info) keeps it.
    if len(turn_models) == 1:
        active_model = turn_models[0]
    elif turn_models:
        active_model = None
    else:
        active_model = current.active_model
    return {"last_models": last_models, "active_model": active_model}


def _general_pending(state: RunState) -> PendingClarification | None:
    """Non-blocking pending for a general answer that asked which model is used."""
    analysis = state.analysis
    assert analysis is not None
    for sub_query in analysis.sub_queries:
        clarification = sub_query.clarification
        if (
            clarification is None
            or clarification.blocking
            or clarification.reason != "missing_product_model"
            or sub_query.retrieval_scope is None
            or sub_query.retrieval_scope.answer_mode != "general"
            or sub_query.id not in analysis.raw_sub_queries
        ):
            continue
        candidates = clarification.candidates.get(clarification.reason, [])
        raw = {**analysis.raw_sub_queries[sub_query.id], "model_dependency": "model_specific"}
        return PendingClarification(
            focus=clarification.reason,
            question_type="confirm" if len(candidates) == 1 else "choose" if candidates else "open",
            candidates=candidates,
            llm_raw={"sub_queries": [raw], "mentions": [], "reason": clarification.reason},
            ttl=PENDING_TTL,
            blocking=False,
        )
    return None


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
