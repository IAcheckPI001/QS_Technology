"""Builder dùng chung cho test chatbot: InboundRequest, principal, request context."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.inbound import (
    ChannelInfo,
    InboundRequest,
    MessageUser,
    ResourceRefs,
    SessionInfo,
)
from app.modules.chatbot.schemas.security.principal import PrincipalContext, RequestContext
from app.modules.chatbot.schemas.system import RunState

DEFAULT_SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_principal(subject_id: str = "website_main") -> PrincipalContext:
    """Principal của website backend: service key, không có người dùng cụ thể."""
    return PrincipalContext(
        subject_id=subject_id,
        principal_type="service",
        tenant_id="qs_technology",
        authn_method="service_key",
        credential_id="fedcba9876543210",
    )


def make_service_principal(
    user_id: str | None = "employee-1",
    integration_id: str = "crm_sales",
) -> PrincipalContext:
    principal = PrincipalContext(
        subject_id=integration_id,
        principal_type="service",
        tenant_id="qs_technology",
        authn_method="service_key",
        credential_id="0123456789abcdef",
    )
    return principal.acting_for(user_id) if user_id else principal


def make_request_context(channel: ChannelType = ChannelType.WEBSITE) -> RequestContext:
    return RequestContext(
        request_id="req-test-0001",
        channel=channel,
        received_at=datetime.now(UTC),
    )


def make_inbound(
    text: str = "Câu hỏi hiện tại",
    *,
    session_id: UUID | str = DEFAULT_SESSION_ID,
    channel: ChannelType = ChannelType.WEBSITE,
    branch: str | None = None,
    message_id: str | None = None,
    resources: ResourceRefs | None = None,
) -> InboundRequest:
    return InboundRequest(
        message=MessageUser(message_id=message_id or str(uuid4()), text=text),
        session=SessionInfo(session_id=str(session_id)),
        channel=ChannelInfo(type=channel, branch=branch),
        resources=resources or ResourceRefs(),
    )


def make_run_state(text: str = "Câu hỏi hiện tại", **inbound_options) -> RunState:
    inbound = make_inbound(text, **inbound_options)
    return RunState(
        input=inbound,
        principal=make_principal(),
        request_context=make_request_context(inbound.channel.type),
    )


def collect_reply(service, text: str, session_id: UUID | str = DEFAULT_SESSION_ID) -> list[str]:
    inbound = make_inbound(text, session_id=session_id)

    async def collect():
        return [
            chunk
            async for chunk in service.stream_reply(
                inbound,
                make_principal(),
                make_request_context(inbound.channel.type),
            )
        ]

    return asyncio.run(collect())
