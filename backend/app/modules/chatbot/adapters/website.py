from uuid import UUID

from app.modules.chatbot.schemas.channels import WebsiteChatIn
from app.modules.chatbot.schemas.inbound import (
    ChannelInfo,
    ChannelType,
    InboundRequest,
    MessageUser,
    SessionInfo,
)
from app.modules.chatbot.schemas.security.principal import RequestContext


def website_to_inbound(
    payload: WebsiteChatIn,
    *,
    session_id: UUID,
    message_id: str,
    idempotency_key: UUID | None,
    request_context: RequestContext,
) -> InboundRequest:
    return InboundRequest(
        schema_version=payload.schema_version,
        message=MessageUser(
            message_id=message_id,
            text=payload.message.text,
            idempotency_key=idempotency_key,
        ),
        session=SessionInfo(session_id=str(session_id)),
        channel=ChannelInfo(type=ChannelType.WEBSITE, branch=request_context.branch),
        client_context=payload.client_context,
    )
