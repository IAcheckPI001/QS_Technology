
"""OutboundResponse – schema đầu ra trả cho CRM / website."""
 
import re
from enum import StrEnum
from typing import Annotated, Literal
 
from pydantic import Field, model_validator
 
from .default import (
    SCHEMA_VERSION,
    Identifier,
    NonEmptyStr,
    NonNegInt,
    OutboundModel,
    PublicSourceMetadata,
    SourceId,
)
from .inbound import Branch
 
CITATION_MARKER = re.compile(r"\[(\d+)\]")
 
 
class Status(StrEnum):
    ANSWERED = "answered"
    NOT_FOUND = "not_found"
    CLARIFY = "clarify"
    HANDOFF = "handoff"
    REFUSED = "refused"
    ERROR = "error"
 
 
# Các trạng thái mà CRM tự động chuyển ticket cho nhân viên.
HANDOFF_STATUSES = frozenset({Status.NOT_FOUND, Status.HANDOFF})
 
 
class HandoffReason(StrEnum):
    NOT_FOUND = "not_found"
    USER_REQUESTED = "user_requested"
    LOW_CONFIDENCE = "low_confidence"
    OUT_OF_SCOPE = "out_of_scope"
    SENSITIVE = "sensitive"
 
 
class AnswerOut(OutboundModel):
    text: NonEmptyStr
    format: Literal["plain", "markdown"] = "plain"
 
 
class CitationOut(OutboundModel):
    index: Annotated[int, Field(ge=1)]
    source_id: SourceId
    chunk_id: Identifier
    snippet: str | None = None
    metadata: PublicSourceMetadata
 
 
class Handoff(OutboundModel):
    reason: HandoffReason
    target_branch: Branch
    summary_for_agent: NonEmptyStr
    searched_queries: list[str] = Field(default_factory=list)
 
 
class ErrorInfo(OutboundModel):
    code: NonEmptyStr
    message: NonEmptyStr
    retryable: bool = False
 
 
class Usage(OutboundModel):
    input_tokens: NonNegInt
    output_tokens: NonNegInt
 
 
class OutboundResponse(OutboundModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    request_id: Identifier
    session_id: Identifier
    ticket_id: Identifier | None = None
    status: Status
    answer: AnswerOut | None = None
    citations: list[CitationOut] = Field(default_factory=list)
    handoff: Handoff | None = None
    error: ErrorInfo | None = None
    # Thông tin vận hành – tùy chọn. Cân nhắc chỉ bật cho client nội bộ.
    model: str | None = None
    usage: Usage | None = None
    latency_ms: NonNegInt | None = None
 
    @model_validator(mode="after")
    def check_status_consistency(self) -> "OutboundResponse":
        s = self.status
        if s is Status.ERROR:
            if self.error is None:
                raise ValueError("status='error' cần có trường error")
        elif self.answer is None:
            raise ValueError(f"status='{s}' cần có answer.text để hiển thị cho người dùng")
 
        if s in HANDOFF_STATUSES and self.handoff is None:
            raise ValueError(f"status='{s}' cần có khối handoff cho nhân viên")
        if s not in HANDOFF_STATUSES and self.handoff is not None:
            raise ValueError("handoff chỉ dùng với status 'not_found' hoặc 'handoff'")
 
        if s is not Status.ANSWERED and self.citations:
            raise ValueError("citations chỉ có khi status='answered'")
        return self
 
    @model_validator(mode="after")
    def check_citation_markers(self) -> "OutboundResponse":
        indexes = [c.index for c in self.citations]
        if sorted(indexes) != list(range(1, len(indexes) + 1)):
            raise ValueError("citation.index phải liên tục từ 1 và không trùng")
        if self.answer is not None:
            markers = {int(m) for m in CITATION_MARKER.findall(self.answer.text)}
            missing = markers - set(indexes)
            if missing:
                raise ValueError(f"answer.text có marker không có citation: {sorted(missing)}")
        return self