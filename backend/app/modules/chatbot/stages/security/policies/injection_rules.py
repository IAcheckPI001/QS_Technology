import re
from dataclasses import dataclass
from re import Pattern

from app.modules.chatbot.schemas.system.security import SecuritySeverity


@dataclass(frozen=True, slots=True)
class InjectionRule:
    rule_id: str
    category: str
    pattern: Pattern[str]
    severity: SecuritySeverity


def _rule(
    rule_id: str,
    category: str,
    pattern: str,
    severity: SecuritySeverity,
) -> InjectionRule:
    return InjectionRule(rule_id, category, re.compile(pattern), severity)


INJECTION_RULES_V1 = (
    _rule(
        "ignore-instructions",
        "ignore_instructions",
        r"\bignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+"
        r"(?:instructions?|rules?|prompts?)\b",
        SecuritySeverity.HIGH,
    ),
    _rule(
        "role-override",
        "role_override",
        r"\b(?:you\s+are\s+now|from\s+now\s+on\s+you\s+are|pretend\s+you\s+are|"
        r"act\s+as\s+if\s+you\s+are|imagine\s+you\s+are)\b",
        SecuritySeverity.HIGH,
    ),
    _rule(
        "system-tags",
        "system_tags",
        r"(?:<\s*system\s*>|\[\s*system\s*\]|\[\s*inst\s*\]|<<\s*sys\s*>>|"
        r"<\|im_start\|>\s*system|<\|system\|>)",
        SecuritySeverity.HIGH,
    ),
    _rule(
        "instruction-injection",
        "instruction_injection",
        r"\b(?:new\s+instruction|override|system\s+prompt)\s*:",
        SecuritySeverity.HIGH,
    ),
    _rule(
        "delimiter-escape",
        "delimiter_escape",
        r"\b(?:end\s+of\s+system|begin\s+user\s+input)\b|"
        r"<\s*(?:instructions?|rules?|prompt|context)\s*>",
        SecuritySeverity.HIGH,
    ),
)
