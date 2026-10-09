from dataclasses import dataclass
from re import Pattern

from app.modules.chatbot.schemas.system.security import SecurityFinding, SecuritySeverity
from app.util.normalize import NormalizedInput


@dataclass(frozen=True, slots=True)
class ContentRule:
    rule_id: str
    category: str
    pattern: Pattern[str]
    severity: SecuritySeverity = SecuritySeverity.MEDIUM


class ContentPolicy:
    """Configurable topic policy; empty rules intentionally allow all topics."""

    detector_id = "content_policy"

    def __init__(self, rules: tuple[ContentRule, ...] = (), policy_version: str = "v1") -> None:
        self._rules = rules
        self.policy_version = policy_version

    def detect(self, normalized: NormalizedInput) -> list[SecurityFinding]:
        return [
            SecurityFinding(
                detector_id=self.detector_id,
                category=rule.category,
                severity=rule.severity,
                rule_id=rule.rule_id,
                confidence=1.0,
            )
            for rule in self._rules
            if rule.pattern.search(normalized.casefolded_text)
            or rule.pattern.search(normalized.accent_folded_text)
        ]
