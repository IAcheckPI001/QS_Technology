


"""RunContext – do Context stage dựng (1 lần / request)."""

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from ..default import (
    SystemModel,
    Identifier,
    LanguageCode,
    NonEmptyStr,
    SourceId,
    SourceMetadata,
)


class HistoryCitation(SystemModel):
    source_id: SourceId
    chunk_id: Identifier
    metadata: SourceMetadata


class ConversationMessage(SystemModel):
    role: Literal["user", "assistant"]
    content: str
    message_id: Identifier
    citations: list[HistoryCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def only_assistant_has_citations(self) -> "ConversationMessage":
        if self.role == "user" and self.citations:
            raise ValueError("message role='user' không có citations")
        return self


class Conversation(SystemModel):
    summary: str | None = None
    history: list[ConversationMessage] = Field(default_factory=list)


class RewriteMethod(StrEnum):
    LLM = "llm"
    RULE = "rule"
    PASSTHROUGH = "passthrough"   # lượt đầu hội thoại, không cần viết lại


class ModelProvider(StrEnum):
    SELF_HOST = "self_host"
    OPENAI = "openai"


class RewriteInfo(SystemModel):
    method: RewriteMethod
    # Tách "chạy ở đâu" (provider) khỏi "model nào" (model).
    provider: ModelProvider | None = None
    model: str | None = None

    @model_validator(mode="after")
    def llm_requires_model(self) -> "RewriteInfo":
        if self.method is RewriteMethod.LLM and not (self.provider and self.model):
            raise ValueError("rewrite.method='llm' cần provider và model")
        return self


class QueryInfo(SystemModel):
    origin: NonEmptyStr
    standalone: NonEmptyStr
    language: LanguageCode = "vi"
    rewrite: RewriteInfo


class RetrievalScope(SystemModel):
    # Server resolve từ channel.branch qua cấu hình, không nhận từ client.
    collections: list[NonEmptyStr] = Field(min_length=1)


class RunContext(SystemModel):
    conversation: Conversation
    query: QueryInfo
    retrieval_scope: RetrievalScope