

"""RetrievalTrace – ghi lại mỗi lần search_doc được gọi."""

from typing import Annotated

from pydantic import Field, model_validator

from ..default import (
    SystemModel,
    Identifier,
    NonEmptyStr,
    NonNegInt,
    SourceId,
    SourceMetadata,
)


class Scores(SystemModel):
    # Tùy chọn: method chỉ vector thì không có keyword, chưa rerank thì không có rerank.
    keyword: float | None = None
    vector: float | None = None
    fused: float | None = None
    rerank: float | None = None

class Candidate(SystemModel):
    chunk_id: Identifier
    source_id: SourceId | None = None   # chỉ có khi selected=True
    selected: bool = False
    scores: Scores
    metadata: SourceMetadata
    reject_reason: str | None = None

    @model_validator(mode="after")
    def source_id_iff_selected(self) -> "Candidate":
        if self.selected != (self.source_id is not None):
            raise ValueError("source_id phải có khi và chỉ khi selected=True")
        return self

class RetrievalFilters(SystemModel):
    collections: list[NonEmptyStr] = Field(min_length=1)
    doc_ids: list[Identifier] = Field(default_factory=list)


class RetrievalParams(SystemModel):
    top_k: Annotated[int, Field(ge=1, le=100)] = 20
    rerank_top_n: Annotated[int, Field(ge=1)] = 5
    filters: RetrievalFilters

    @model_validator(mode="after")
    def rerank_within_top_k(self) -> "RetrievalParams":
        if self.rerank_top_n > self.top_k:
            raise ValueError("rerank_top_n không được lớn hơn top_k")
        return self

class RetrievalTrace(SystemModel):
    retrieval_id: Identifier
    iteration: NonNegInt
    query: NonEmptyStr
    method: NonEmptyStr = "hybrid+rerank"
    params: RetrievalParams
    candidates: list[Candidate] = Field(default_factory=list)
    latency_ms: NonNegInt

    @property
    def selected(self) -> list[Candidate]:
        return [c for c in self.candidates if c.selected]