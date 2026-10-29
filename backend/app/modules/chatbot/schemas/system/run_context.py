


"""RunContext – do Context stage dựng (1 lần / request)."""

from enum import StrEnum
from typing import Literal
from dataclasses import asdict
from dataclasses import dataclass
from pydantic import Field, model_validator, ConfigDict

from ..default import (
    SystemModel,
    Identifier,
    LanguageCode,
    NonEmptyStr,
    SourceId,
    SourceMetadata,
)

MAX_LAST_MODELS = 4


class _Model(SystemModel):
    # TODO: thay bằng SystemModel của dự án
    model_config = ConfigDict(extra="forbid")


class Mode(StrEnum):
    BOT = "bot"
    AWAITING_AGENT = "awaiting_agent"
    WITH_AGENT = "with_agent"


class PendingClarification(_Model):
    focus: str = Field(min_length=1)                  # mention đang hỏi lại, VD "F58"
    question_type: Literal["confirm", "choose", "open"]
    candidates: list[str] = Field(default_factory=list)
    llm_raw: dict                                     # sub_query gốc để nối lại
    ttl: int = Field(ge=0)
    # False: câu hỏi model ở cuối câu trả lời chung; chỉ nhận mã/alias/số thứ tự,
    # không nhận "ok/đúng" để tránh kích hoạt tra cứu ngoài ý muốn.
    blocking: bool = True


class ConversationState(_Model):
    mode: Mode = Mode.BOT
    # Các model đã nhắc trong phiên, cũ -> mới (tham chiếu "các model trên", gợi ý).
    last_models: list[str] = Field(default_factory=list, max_length=MAX_LAST_MODELS)
    # Model đang được bàn: model duy nhất của lượt gần nhất; None sau lượt có >= 2 model.
    active_model: str | None = None
    # Ngôn ngữ của người dùng trong phiên (ISO 639-1), do analysis phát hiện.
    language: LanguageCode | None = None
    last_intent: str | None = None
    pending: PendingClarification | None = None
    clarify_attempts: int = Field(default=0, ge=0)
    miss_streak: int = Field(default=0, ge=0)       # lượt liên tiếp không trả lời được
    ticket_id: str | None = None

    def for_llm(self) -> dict:
        data: dict = {}
        if self.last_models:
            data["last_models"] = self.last_models
        if self.active_model:
            data["active_model"] = self.active_model
        if self.language:
            data["language"] = self.language
        return data


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
    state: ConversationState = Field(
        default_factory=ConversationState,
    )
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
    standalone: NonEmptyStr | None = None
    language: LanguageCode = "vi"
    rewrite: RewriteInfo | None = None


class RetrievalScope(SystemModel):
    # Server resolve từ channel.branch qua cấu hình, không nhận từ client.
    collections: list[NonEmptyStr] = Field(min_length=1)


class RunContext(SystemModel):
    conversation: Conversation
    query: QueryInfo
    retrieval_scope: RetrievalScope