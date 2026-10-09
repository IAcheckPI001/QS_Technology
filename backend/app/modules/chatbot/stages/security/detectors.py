from typing import Protocol

from app.modules.chatbot.schemas.system.security import SecurityFinding
from app.util.normalize import NormalizedInput


class SecurityDetector(Protocol):
    detector_id: str

    def detect(self, normalized: NormalizedInput) -> list[SecurityFinding]:
        """Return findings without changing the original request."""
