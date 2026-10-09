from dataclasses import dataclass

from app.modules.chatbot.schemas.system.security import (
    SecurityAction,
    SecurityDecision,
    SecurityFinding,
    SecuritySeverity,
)
from app.util.normalize import NormalizedInput, normalize_for_detection

from .content_policy import ContentPolicy
from .detectors import SecurityDetector
from .injection_guard import InjectionGuard


@dataclass(frozen=True, slots=True)
class SecurityRequestState:
    text: str


class SecurityBlockedError(Exception):
    """Raised only after a request receives a security block decision."""

    def __init__(self, decision: SecurityDecision, locale: str | None = None) -> None:
        super().__init__("request blocked by security policy")
        self.decision = decision
        self.locale = locale


_SEVERITY_ORDER = {
    SecuritySeverity.LOW: 1,
    SecuritySeverity.MEDIUM: 2,
    SecuritySeverity.HIGH: 3,
    SecuritySeverity.CRITICAL: 4,
}


class SecurityStage:
    name = "security"

    def __init__(
        self,
        detectors: tuple[SecurityDetector, ...] | None = None,
        policy_version: str = "v1",
    ) -> None:
        self._detectors = detectors or (InjectionGuard(), ContentPolicy(policy_version=policy_version))
        self.policy_version = policy_version

    async def execute(self, state: SecurityRequestState) -> SecurityDecision:
        return self.inspect(state.text)

    def inspect(self, text: str) -> SecurityDecision:
        normalized = normalize_for_detection(text)
        findings: list[SecurityFinding] = []
        for detector in self._detectors:
            findings.extend(detector.detect(normalized))

        highest = max(
            (finding.severity for finding in findings),
            key=lambda severity: _SEVERITY_ORDER[severity],
            default=None,
        )
        action = SecurityAction.BLOCK if findings else SecurityAction.ALLOW
        decision = SecurityDecision(
            action=action,
            stage_name=self.name,
            findings=sorted(findings, key=lambda item: item.rule_id),
            highest_severity=highest,
            policy_version=self.policy_version,
        )
        return decision
