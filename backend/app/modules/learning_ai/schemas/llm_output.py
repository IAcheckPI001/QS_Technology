"""DTO đầu ra LLM và bộ chuyển Pydantic → JSON Schema strict (OpenAI Structured Outputs).

Tách DTO khỏi KnowledgeRecord: LLM KHÔNG được sinh record_id, status, version, provenance,
privacy hay source_id. Các trường đó do hệ thống gán sau khi validate.

Trích xuất 2 pass:
  Pass 1 (Segmenter): hội thoại → danh sách segment, mỗi segment = 1 vấn đề + knowledge_type.
  Pass 2 (Extractor): mỗi segment → ExtractedRecord[<Content của đúng loại>].
Pass 2 dùng schema riêng từng loại → schema nhỏ, không cần union/anyOf lớn, LLM ít nhầm hơn.
"""
from __future__ import annotations

import copy
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from .common import Applicability, Classification, StrictModel
from .content import CONTENT_MODEL_BY_TYPE, KnowledgeType
from .registry import FIELD_TO_REGISTRY_KEY, RegistrySnapshot

# Enum quá lớn làm tăng chi phí/độ trễ schema; vượt ngưỡng thì để chuỗi tự do và validate sau.
ENUM_INJECT_LIMIT = 300
LLM_HIDDEN_FIELDS = {"source_id"}
LLM_FORBIDDEN_ENUM_VALUES = {"reviewer_confirmed"}  # chỉ người review được gán
_UNSUPPORTED_KEYS = {"default", "title", "minItems", "maxItems", "minimum", "maximum",
                     "minLength", "maxLength", "pattern", "format", "discriminator"}


# ---------------- Pass 1 ----------------
class Segment(StrictModel):
    segment_id: str
    knowledge_type: KnowledgeType
    problem_statement: str = Field(description="Một câu mô tả vấn đề đã ẩn danh")
    message_ids: list[str] = Field(description="Tất cả tin nhắn thuộc vấn đề này, kể cả tin nhắn điều kiện/ngữ cảnh")
    resolved: bool = Field(description="Có lời giải được nhân viên đưa ra rõ ràng hay không")
    skip_reason: str | None = Field(
        default=None, description="Lý do không nên tạo tri thức: chỉ chào hỏi, chỉ chuyển tiếp, cấu hình riêng...")


class SegmentationOutput(StrictModel):
    segments: list[Segment]


# ---------------- Pass 2 ----------------
C = TypeVar("C", bound=BaseModel)


class ExtractedRecord(StrictModel, Generic[C]):
    title: str
    summary: str
    classification: Classification
    applicability: Applicability
    content: C
    contains_customer_specific: bool = Field(
        description="True nếu nội dung còn giá trị chỉ đúng cho riêng hệ thống của khách này")


def extraction_model_for(kt: KnowledgeType) -> type[ExtractedRecord]:
    return ExtractedRecord[CONTENT_MODEL_BY_TYPE[kt]]  # type: ignore[index]


# ---------------- Pydantic → strict schema ----------------
def to_strict_schema(model: type[BaseModel], registry: RegistrySnapshot) -> dict[str, Any]:
    schema = copy.deepcopy(model.model_json_schema())
    _strictify(schema, registry)
    return schema


def _strictify(node: Any, reg: RegistrySnapshot, prop_name: str | None = None) -> None:
    if isinstance(node, list):
        for x in node:
            _strictify(x, reg)
        return
    if not isinstance(node, dict):
        return

    for k in list(node):
        if k in _UNSUPPORTED_KEYS:
            node.pop(k)
    if "const" in node:
        node["enum"] = [node.pop("const")]
    if "enum" in node:
        node["enum"] = [v for v in node["enum"] if v not in LLM_FORBIDDEN_ENUM_VALUES]
    if "oneOf" in node:
        node["anyOf"] = node.pop("oneOf")

    if node.get("type") == "object" and "properties" in node:
        for hidden in LLM_HIDDEN_FIELDS & node["properties"].keys():
            node["properties"].pop(hidden)
        node["required"] = list(node["properties"])
        node["additionalProperties"] = False
        for name, sub in node["properties"].items():
            _inject_enum(name, sub, reg)
            _strictify(sub, reg, name)
    for key in ("$defs", "items", "anyOf"):
        if key in node:
            sub = node[key]
            _strictify(list(sub.values()) if key == "$defs" else sub, reg)


def _inject_enum(name: str, sub: dict, reg: RegistrySnapshot) -> None:
    if name not in FIELD_TO_REGISTRY_KEY:
        return
    allowed = sorted(reg.allowed(name))
    if not allowed or len(allowed) > ENUM_INJECT_LIMIT:
        return
    if sub.get("type") == "array" and isinstance(sub.get("items"), dict):
        sub["items"]["enum"] = allowed
    elif sub.get("type") == "string":
        sub["enum"] = allowed
