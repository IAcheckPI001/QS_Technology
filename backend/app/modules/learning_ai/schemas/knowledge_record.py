


"""KnowledgeRecord: nguồn tri thức chuẩn. Không chứa vector, embedding_text hay chunk."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Iterator
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from .common import Applicability, Claim, Classification, StrictModel
from .content import KnowledgeContent, KnowledgeType

SCHEMA_VERSION = "kr-1.0"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RecordStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"   # bị thay bởi phiên bản mới hơn / record khác
    ARCHIVED = "archived"       # rút khỏi sử dụng (sản phẩm ngừng hỗ trợ...)


class Provenance(StrictModel):
    source_ids: list[str] = Field(min_length=1, description="ID mờ của SourceDocument, không phải ticket ID")
    extraction_run_id: str
    extractor_model: str
    prompt_version: str
    registry_version: str
    schema_version: str = SCHEMA_VERSION


class ReviewEvent(StrictModel):
    at: datetime = Field(default_factory=_now)
    actor: str
    action: str                       # submit | approve | reject | edit | request_changes | supersede
    from_status: RecordStatus | None = None
    to_status: RecordStatus | None = None
    note: str | None = None


class Lifecycle(StrictModel):
    status: RecordStatus = RecordStatus.DRAFT
    created_at: datetime = Field(default_factory=_now)
    created_by: str = "system:extractor"
    approved_by: str | None = None
    approved_at: datetime | None = None
    history: list[ReviewEvent] = Field(default_factory=list)


class ConflictStatus(str, Enum):
    OPEN = "open"
    KEEP_BOTH = "keep_both"                # khác điều kiện → cả hai đúng, cần làm rõ condition
    THIS_SUPERSEDES = "this_supersedes"
    REJECT_THIS = "reject_this"
    FALSE_POSITIVE = "false_positive"


class ConflictRef(StrictModel):
    conflict_id: str
    against_kind: str = Field(description="'knowledge_record' | 'manual'")
    against_id: str                       # record_id hoặc document source_id
    against_revision: str | None = None
    field_path: str                        # vd "settings[parameter_id=P01].value"
    description: str
    detected_by: str                       # 'rule' | 'llm' | 'reviewer'
    status: ConflictStatus = ConflictStatus.OPEN
    resolution_note: str | None = None


class Versioning(StrictModel):
    version: int = Field(default=1, ge=1)
    parent_revision_id: UUID | None = None
    supersedes_record_ids: list[UUID] = Field(default_factory=list)
    superseded_by_record_id: UUID | None = None
    change_summary: str | None = None


class Visibility(str, Enum):
    INTERNAL = "internal"       # dùng chung cho chatbot / toàn bộ nhân viên
    RESTRICTED = "restricted"   # còn cấu hình đặc thù khách hàng → không vào index chính thức


class PrivacyInfo(StrictModel):
    redaction_applied: bool
    pii_types_detected: list[str] = Field(default_factory=list)
    contains_customer_specific: bool = False
    visibility: Visibility = Visibility.INTERNAL


class KnowledgeRecord(StrictModel):
    record_id: UUID = Field(default_factory=uuid4, description="ID logic, ổn định qua các phiên bản")
    revision_id: UUID = Field(default_factory=uuid4, description="ID của đúng phiên bản nội dung này")
    title: str
    summary: str
    language: str = "vi"
    classification: Classification
    applicability: Applicability
    content: KnowledgeContent
    provenance: Provenance
    lifecycle: Lifecycle = Field(default_factory=Lifecycle)
    versioning: Versioning = Field(default_factory=Versioning)
    conflicts: list[ConflictRef] = Field(default_factory=list)
    privacy: PrivacyInfo

    @property
    def knowledge_type(self) -> KnowledgeType:
        return KnowledgeType(self.content.kind)

    @model_validator(mode="after")
    def _privacy_vs_visibility(self):
        if self.privacy.contains_customer_specific and self.privacy.visibility == Visibility.INTERNAL:
            raise ValueError("record chứa cấu hình đặc thù khách hàng không được để visibility=internal")
        return self

    # ---- nội dung chuẩn dùng cho hash, so sánh phiên bản, kiểm tra stale của dữ liệu dẫn xuất ----
    def canonical_payload(self) -> dict:
        return self.model_dump(
            mode="json",
            include={"title", "summary", "language", "classification", "applicability", "content"},
        )

    def content_hash(self) -> str:
        raw = json.dumps(self.canonical_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def iter_claims(self) -> Iterator[tuple[str, Claim]]:
        """Duyệt mọi Claim trong record kèm đường dẫn, dùng cho validator / approval gate / UI review."""
        yield "applicability", self.applicability
        yield from _walk(self.content, "content")


def _walk(obj: object, path: str) -> Iterator[tuple[str, Claim]]:
    if isinstance(obj, Claim):
        yield path, obj
    if isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            yield from _walk(getattr(obj, name), f"{path}.{name}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from _walk(item, f"{path}[{i}]")