"""Rebuild held sub-queries from a pending clarification without calling the LLM."""

import copy
import re

from app.modules.chatbot.extraction.validate_registry import _norm, display_name
from app.modules.chatbot.orchestration.planner import held_sub_query_ids
from app.modules.chatbot.schemas.system import (
    Analysis,
    PendingClarification,
    Route,
)

MAX_CLARIFY_ATTEMPTS = 2


def patch_pending(pending: PendingClarification, answer: str) -> list[dict]:
    """Replace the clarified mention with the user's answer in the held raw sub-queries."""
    mentions = list(pending.llm_raw.get("mentions") or [])
    focus_keys = {_norm(mention) for mention in mentions}
    label = display_name(answer)

    patched: list[dict] = []
    for raw in pending.llm_raw.get("sub_queries") or []:
        sub_query = copy.deepcopy(raw)
        models = [
            model for model in sub_query.get("product_models") or []
            if _norm(model) not in focus_keys
        ]
        if answer not in models:
            models.append(answer)
        query = sub_query.get("standalone_query") or ""
        replaced = query
        for mention in mentions:
            replaced = re.sub(re.escape(mention), label, replaced, flags=re.IGNORECASE)
        if replaced == query:
            replaced = f"{query} ({label})"
        sub_query.update(
            standalone_query=replaced,
            product_models=models,
            unresolved_mentions=[
                mention for mention in sub_query.get("unresolved_mentions") or []
                if _norm(mention) not in focus_keys
            ],
            history_conflict=False,
        )
        patched.append(sub_query)
    return patched


def exhaust_clarification(analysis: Analysis) -> Analysis:
    """Stop asking again: held sub-queries become no_docs after too many attempts."""
    held = held_sub_query_ids(analysis)
    if not held:
        return analysis
    sub_queries = [
        sub_query.model_copy(update={
            "route": Route.NO_DOCS,
            "clarification": None,
            "retrieval_scope": None,
            "unsupported_models": (
                sub_query.unsupported_models or sub_query.entities.unresolved_mentions
            ),
            "warnings": [*sub_query.warnings, "clarification_exhausted"],
        })
        if sub_query.id in held else sub_query
        for sub_query in analysis.sub_queries
    ]
    return analysis.model_copy(update={
        "sub_queries": sub_queries,
        "clarification": None,
        "no_docs_sub_query_ids": [
            *analysis.no_docs_sub_query_ids,
            *(sub_query_id for sub_query_id in sorted(held)
              if sub_query_id not in analysis.no_docs_sub_query_ids),
        ],
    })
