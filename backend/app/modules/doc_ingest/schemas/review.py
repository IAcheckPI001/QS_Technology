"""Knowledge unit và approval (D-08, H-1…H-9)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from app.modules.doc_ingest.schemas.base import StrictModel


class DocState(StrEnum):
    STAGING = "staging"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class UnitState(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONFLICT = "conflict"


class RiskTier(StrEnum):
    HIGH = "high"
    LOW = "low"


# Loại unit luôn duyệt từng unit (H-8).
HIGH_RISK_UNIT_TYPES = frozenset({"pinout", "wiring", "parameter", "warning", "figure_fact"})


class KnowledgeUnit(StrictModel):
    unit_id: str
    unit_type: str
    section_path: list[str] = Field(default_factory=list)
    content_hash: str
    evidence_hash: str
    state: UnitState = UnitState.DRAFT
    depends_on: list[str] = Field(default_factory=list)   # vd. wiring → warning liên kết (H-4)
    conflict_group: str | None = None
    flags: list[str] = Field(default_factory=list)          # cờ T-xx / V-xx trên phần tử của unit

    @property
    def risk_tier(self) -> RiskTier:
        return RiskTier.HIGH if self.unit_type in HIGH_RISK_UNIT_TYPES or self.flags else RiskTier.LOW


class ApprovalRecord(StrictModel):
    """Bản ghi audit; approval gắn với hash nội dung + evidence, không gắn hash profile."""

    unit_id: str
    unit_type: str
    reviewer: str
    approved_at: datetime
    unit_content_hash: str
    evidence_hash: str
    mode: str = "single"          # single | bulk_section

    @field_validator("reviewer")
    @classmethod
    def _reviewer_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reviewer bắt buộc")
        return value.strip()
