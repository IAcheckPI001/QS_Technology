from app.modules.chatbot.schemas.system.security import (
    SecurityFinding,
    SecuritySeverity,
)
from app.util.normalize import NormalizedInput

from .policies.injection_rules import INJECTION_RULES_V1, InjectionRule


DEFAULT_RULES = INJECTION_RULES_V1


class InjectionGuard:
    detector_id = "injection_guard"

    def __init__(self, rules: tuple[InjectionRule, ...] = DEFAULT_RULES) -> None:
        self._rules = rules

    def detect(self, normalized: NormalizedInput) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        views = (normalized.casefolded_text, normalized.accent_folded_text)
        if "\x00" in normalized.original_text:
            findings.append(
                SecurityFinding(
                    detector_id=self.detector_id,
                    category="null_bytes",
                    severity=SecuritySeverity.CRITICAL,
                    rule_id="null-byte",
                    confidence=1.0,
                )
            )

        for rule in self._rules:
            if any(rule.pattern.search(view) for view in views):
                findings.append(
                    SecurityFinding(
                        detector_id=self.detector_id,
                        category=rule.category,
                        severity=rule.severity,
                        rule_id=rule.rule_id,
                        confidence=1.0,
                    )
                )
        return findings
