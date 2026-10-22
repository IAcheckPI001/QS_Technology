

"""RetrievalTrace – ghi lại mỗi lần search_doc được gọi."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

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
    # collections: khái niệm cũ theo kênh; doc_chunks lọc theo domain/scopes/models.
    collections: list[NonEmptyStr] = Field(default_factory=list)
    doc_ids: list[Identifier] = Field(default_factory=list)
    domain: NonEmptyStr | None = None
    scopes: list[NonEmptyStr] = Field(default_factory=list)
    product_models: list[NonEmptyStr] | None = None
    control_interface: list[NonEmptyStr] = Field(default_factory=list)
    spec_attributes: list[NonEmptyStr] = Field(default_factory=list)


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


class RetrievalQuery(SystemModel):
    sub_query_id: NonEmptyStr
    query: NonEmptyStr
    answer_mode: Literal["full", "overview"]


class RetrievalRequest(SystemModel):
    """Một lần tra cứu cho một target (domain + scopes) của sub-query."""

    task_id: NonEmptyStr
    domain: NonEmptyStr
    scopes: list[NonEmptyStr] = Field(default_factory=list)
    model_filter: list[NonEmptyStr] | None = None
    product_scope_mode: NonEmptyStr = "unspecified"
    control_interface: list[NonEmptyStr] = Field(default_factory=list)
    spec_attributes: list[NonEmptyStr] = Field(default_factory=list)
    queries: list[RetrievalQuery] = Field(min_length=1)


class ChunkAsset(SystemModel):
    # assets là jsonb do pipeline ingest ghi: bỏ qua khóa lạ thay vì làm hỏng retrieval.
    model_config = ConfigDict(extra="ignore")

    bucket: NonEmptyStr
    path: NonEmptyStr
    page: int | None = None
    printed_page: int | None = None


class ChunkRecord(SystemModel):
    """Một dòng doc_chunks dùng làm context."""

    id: int
    parent_id: int | None = None
    doc_id: NonEmptyStr
    section_title: NonEmptyStr
    section_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    content: NonEmptyStr
    assets: list[ChunkAsset] = Field(default_factory=list)


class ChunkMatch(ChunkRecord):
    """Dòng trả về từ match_doc_chunks kèm điểm xếp hạng."""

    vector_score: float
    keyword_score: float | None = None
    fused_score: float


class ChunkHit(SystemModel):
    """Chunk context đã chọn cho sub-query (chunk cha nếu được mở rộng)."""

    chunk_id: Identifier
    matched_chunk_ids: list[Identifier] = Field(min_length=1)
    doc_id: NonEmptyStr
    section_title: NonEmptyStr
    section_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    content: NonEmptyStr
    assets: list[ChunkAsset] = Field(default_factory=list)
    score: float
    source_id: SourceId | None = None   # ExecutionStage gán sau khi mọi task chạy xong


class RetrievalSubQueryResult(SystemModel):
    sub_query_id: NonEmptyStr
    hits: list[ChunkHit] = Field(default_factory=list)
    traces: list[RetrievalTrace] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class RetrievalResult(SystemModel):
    task_id: NonEmptyStr
    results: list[RetrievalSubQueryResult] = Field(min_length=1)
    missing_sub_query_ids: list[NonEmptyStr] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def result_ids_are_unique(self) -> "RetrievalResult":
        ids = [result.sub_query_id for result in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("retrieval result sub-query ids must be unique")
        if len(self.missing_sub_query_ids) != len(set(self.missing_sub_query_ids)):
            raise ValueError("missing retrieval sub-query ids must be unique")
        if set(ids) & set(self.missing_sub_query_ids):
            raise ValueError("retrieval sub-query cannot be both completed and missing")
        return self