"""Typed analysis plan shared by analysis and downstream pipeline stages."""

from enum import StrEnum
from typing import Literal
from pydantic import Field

from ..default import SystemModel, NonEmptyStr


class Route(StrEnum):
    RETRIEVE = "retrieve"
    NO_DOCS = "no_docs"
    CHITCHAT = "chitchat"
    HANDOFF = "handoff"
    CLARIFY = "clarify"
    OUT_OF_SCOPE = "out_of_scope"


class Intent(SystemModel):
    name: NonEmptyStr

class Entity(SystemModel):
    type: NonEmptyStr
    value: NonEmptyStr
    normalized: str | None = None
    normalized_id: str | None = None


class ExtractedEntities(SystemModel):
    product_models: list[NonEmptyStr] = Field(default_factory=list)
    unresolved_mentions: list[NonEmptyStr] = Field(default_factory=list)
    control_interface: list[NonEmptyStr] = Field(default_factory=list)
    spec_attribute: list[NonEmptyStr] = Field(default_factory=list)


class RetrievalTarget(SystemModel):
    domain: NonEmptyStr
    scopes: list[NonEmptyStr] = Field(default_factory=list)


class RetrievalPlan(SystemModel):
    product_scope_mode: NonEmptyStr
    targets: list[RetrievalTarget] = Field(min_length=1)
    fallback_targets: list[RetrievalTarget] = Field(default_factory=list)
    model_filter: list[NonEmptyStr] | None = None
    unsupported_models: list[NonEmptyStr] = Field(default_factory=list)
    answer_mode: Literal["full", "overview"]


class SubQueryClarification(SystemModel):
    reason: NonEmptyStr
    blocking: bool
    mentions: list[NonEmptyStr] = Field(default_factory=list)
    candidates: dict[str, list[NonEmptyStr]] = Field(default_factory=dict)


class ClarificationPlan(SubQueryClarification):
    sub_query_id: NonEmptyStr


class SubQueryAnalysis(SystemModel):
    id: NonEmptyStr
    standalone_query: NonEmptyStr
    intent: NonEmptyStr | None = None
    entities: ExtractedEntities
    retrieval_scope: RetrievalPlan | None = None
    clarification: SubQueryClarification | None = None
    handoff_reason: NonEmptyStr | None = None
    unsupported_models: list[NonEmptyStr] = Field(default_factory=list)
    route: Route
    warnings: list[NonEmptyStr] = Field(default_factory=list)


class RetrievalBatch(SystemModel):
    domain: NonEmptyStr
    scopes: list[NonEmptyStr] = Field(default_factory=list)
    model_filter: list[NonEmptyStr] | None = None
    sub_query_ids: list[NonEmptyStr] = Field(min_length=1)


class Analysis(SystemModel):
    """Turn-level plan plus legacy single-query projection.

    The turn-level fields are authoritative. The legacy fields are populated
    from the first sub-query only for existing consumers that still expect a
    single intent/entity/route result.
    """

    intent: Intent | None = None
    entities: list[Entity] = Field(default_factory=list)
    route: Route | None = None
    turn_route: Route
    answer_sub_query_ids: list[NonEmptyStr] = Field(default_factory=list)
    no_docs_sub_query_ids: list[NonEmptyStr] = Field(default_factory=list)
    direct_sub_query_ids: list[NonEmptyStr] = Field(default_factory=list)
    handoff_reason: NonEmptyStr | None = None
    clarification: ClarificationPlan | None = None
    batches: list[RetrievalBatch] = Field(default_factory=list)
    sub_queries: list[SubQueryAnalysis] = Field(min_length=1)
    # Clarification loop: raw LLM sub-queries by id (internal, re-resolved after
    # the user confirms), the confirmed answer, and whether this turn resumed a
    # pending clarification.
    raw_sub_queries: dict[str, dict] = Field(default_factory=dict, exclude=True)
    pending_answer: NonEmptyStr | None = None
    resumed: bool = False

    @classmethod
    def from_plan(cls, plan: dict) -> "Analysis":
        sub_queries = [
            SubQueryAnalysis.model_validate(sub_query)
            for sub_query in plan["sub_queries"]
        ]
        first = sub_queries[0]
        legacy_entities = [
            Entity(type="product_model", value=model, normalized=model)
            for model in first.entities.product_models
        ]
        legacy_entities.extend(
            Entity(type="unresolved_mention", value=mention)
            for mention in first.entities.unresolved_mentions
        )
        return cls(
            intent=Intent(name=first.intent) if first.intent else None,
            entities=legacy_entities,
            route=first.route,
            turn_route=plan["turn_route"],
            answer_sub_query_ids=plan["answer"],
            no_docs_sub_query_ids=plan["no_docs"],
            direct_sub_query_ids=plan["direct"],
            handoff_reason=plan["handoff_reason"],
            clarification=plan["clarification"],
            batches=plan["batches"],
            sub_queries=sub_queries,
        )