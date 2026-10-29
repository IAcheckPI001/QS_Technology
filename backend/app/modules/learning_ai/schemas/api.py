"""Contract HTTP của `POST /ai/learning`, schema version 1.0.

Response chỉ chứa text ĐÃ CHE; text gốc không bao giờ rời khỏi service.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ..extraction.validators import Role
from ..ingestion.service import IngestionResult, IngestionStatus
from ..privacy.schemas import FindingType, SensitivityFlag
from .common import StrictModel

SCHEMA_VERSION = "1.0"
PRODUCT_MODELS = Literal["F54", "F86", "F10T", "ASTRO_10S", "ASTRO_6AH", "ASTRO_6AV", "ASTRO_10I"]


class SupportChatSessionCreate(StrictModel):
    product_models: list[PRODUCT_MODELS] = Field(default_factory=list)


class SupportChatSession(StrictModel):
    session_id: UUID
    product_models: list[str]
    created_at: datetime


class SupportChatMessage(StrictModel):
    id: UUID
    session_id: UUID
    message_no: int
    sender_role: Literal["user", "staff"]
    message_text: str
    created_at: datetime


class SupportChatMessagesResponse(StrictModel):
    session_id: UUID
    messages: list[SupportChatMessage]


class LearnRequest(StrictModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    session_id: UUID
    retry_failed: bool = Field(default=False, description="Chưa có tác dụng cho tới khi có bảng job")


class LearnedUnit(StrictModel):
    locator: str
    role: Role
    text: str


class LearnResponse(StrictModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    request_id: str
    session_id: UUID
    status: Literal[IngestionStatus.READY, IngestionStatus.SKIPPED]
    reason: str | None = None
    source_id: str | None = None
    checker_model: str | None = None
    redaction_applied: bool = False
    pii_types_detected: list[FindingType] = Field(default_factory=list)
    flags_by_locator: dict[str, list[SensitivityFlag]] = Field(default_factory=dict)
    unverified_findings: int = 0
    residual_redactions: int = 0
    units: list[LearnedUnit] = Field(default_factory=list)

    @classmethod
    def from_result(cls, result: IngestionResult, request_id: str) -> LearnResponse:
        base = cls(request_id=request_id, session_id=result.session_id, status=result.status, reason=result.reason)
        privacy = result.privacy
        if privacy is None:
            return base
        return base.model_copy(update={
            "source_id": privacy.document.source_id,
            "checker_model": privacy.checker_model,
            "redaction_applied": privacy.redaction_applied,
            "pii_types_detected": privacy.pii_types_detected,
            "flags_by_locator": privacy.flags_by_locator,
            "unverified_findings": privacy.unverified_findings,
            "residual_redactions": privacy.residual_redactions,
            "units": [LearnedUnit(locator=u.locator, role=u.role, text=u.text) for u in privacy.document.units],
        })
