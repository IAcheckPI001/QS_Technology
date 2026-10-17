"""Analysis – kết quả phân tích câu hỏi (intent / entity / route)."""

from enum import StrEnum
from typing import Literal
from pydantic import Field

from ..default import SystemModel, NonEmptyStr, Probability


class Route(StrEnum):
    RAG = "rag"
    CHITCHAT = "chitchat"
    HANDOFF = "handoff"
    CLARIFY = "clarify"


class Intent(SystemModel):
    name: NonEmptyStr


EntityType = Literal[
    "product_model",
    "product_category",
    "control_interface",
    "connector",
    "signal_pin",
    "parameter_id",
    "code",
    "spec_attribute"
]

ResolutionStatus = Literal[
    "resolved",
    "ambiguous",
    "unresolved",
    "not_applicable",
]

class Entity(SystemModel):
    type: NonEmptyStr                 # clause, document, product, ...
    value: NonEmptyStr                # nguyên văn trong câu hỏi
    normalized: str | None = None     # giá trị chuẩn hóa, VD "5"
    normalized_id: str | None = None  # ID trong kho nếu map được, VD "d_42"


class Analysis(SystemModel):
    intent: Intent
    entities: list[Entity] = Field(default_factory=list)
    route: Route