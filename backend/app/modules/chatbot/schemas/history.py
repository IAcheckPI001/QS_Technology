from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    query_origin: str = Field(min_length=1)
    answer: str | None = None
    status: str = Field(min_length=1)
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    session_id: UUID
    messages: list[ChatHistoryItem]
