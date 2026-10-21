"""Handoff to a human agent.

Scaffold only: no external agent platform is connected yet.
`DisabledHandoffProvider` never creates a ticket, so the conversation stays
in bot mode. A real adapter must implement `HandoffProvider`.
"""

from typing import Protocol
from uuid import UUID

from app.modules.chatbot.schemas.default import NonEmptyStr, SystemModel
from app.modules.chatbot.schemas.system import ConversationMessage, Mode


class HandoffTicket(SystemModel):
    ticket_id: NonEmptyStr
    mode: Mode = Mode.AWAITING_AGENT


class HandoffProvider(Protocol):
    async def transfer(
        self,
        session_id: UUID,
        history: list[ConversationMessage],
        reason: str,
    ) -> HandoffTicket | None:
        """Send the conversation to the agent platform and return its ticket."""


class DisabledHandoffProvider:
    async def transfer(
        self,
        session_id: UUID,
        history: list[ConversationMessage],
        reason: str,
    ) -> HandoffTicket | None:
        return None
