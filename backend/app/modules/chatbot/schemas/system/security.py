"""Typed security findings shared by detectors and the chatbot pipeline."""

from enum import StrEnum

from pydantic import Field

from ..default import Probability, SystemModel


class SecurityAction(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    REVIEW = "review"


class SecuritySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityFinding(SystemModel):
    detector_id: str = Field(min_length=1, max_length=64)
    category: str = Field(min_length=1, max_length=64)
    severity: SecuritySeverity
    rule_id: str = Field(min_length=1, max_length=128)
    confidence: Probability | None = None


class SecurityDecision(SystemModel):
    action: SecurityAction
    stage_name: str = Field(min_length=1, max_length=64)
    findings: list[SecurityFinding] = Field(default_factory=list)
    highest_severity: SecuritySeverity | None = None
    policy_version: str = Field(min_length=1, max_length=32)

    @classmethod
    def allow(cls, *, stage_name: str, policy_version: str) -> "SecurityDecision":
        return cls(
            action=SecurityAction.ALLOW,
            stage_name=stage_name,
            policy_version=policy_version,
        )
