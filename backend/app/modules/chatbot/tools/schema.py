"""Chuẩn hóa JSON Schema của Pydantic thành schema tham số tool theo dialect provider.

Registry là nơi duy nhất làm việc này: AgentRunner và từng tool không tự sửa
schema. Schema không biểu diễn được cho dialect bị từ chối lúc register/startup.
"""

from typing import Any

from pydantic import BaseModel

from app.modules.chatbot.schemas.system import SchemaDialect

# Keyword không gửi cho provider. Ràng buộc bị bỏ vẫn được Pydantic kiểm tra
# khi registry validate arguments.
_DROP_KEYS: dict[str, frozenset[str]] = {
    "openai_strict": frozenset({
        "title", "default", "examples", "minLength", "maxLength",
        "minProperties", "maxProperties", "uniqueItems",
    }),
    "json_schema_basic": frozenset({"title", "examples"}),
}


class ToolSchemaError(ValueError):
    """Input model không chuyển được sang dialect của provider."""


def to_provider_schema(model: type[BaseModel], dialect: SchemaDialect) -> dict[str, Any]:
    raw = model.model_json_schema()
    definitions = raw.pop("$defs", {})
    schema = _inline_refs(raw, definitions, ())
    if schema.get("type") != "object":
        raise ToolSchemaError(f"{model.__name__}: tool parameters must be an object")
    return _normalize(schema, dialect, model.__name__)


def _inline_refs(node: Any, definitions: dict[str, Any], stack: tuple[str, ...]) -> Any:
    if isinstance(node, list):
        return [_inline_refs(item, definitions, stack) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        if name in stack:
            raise ToolSchemaError(f"recursive schema is not supported: {name}")
        if name not in definitions:
            raise ToolSchemaError(f"unknown schema reference: {name}")
        target = _inline_refs(definitions[name], definitions, (*stack, name))
        extra = {key: value for key, value in node.items() if key != "$ref"}
        return {**target, **_inline_refs(extra, definitions, stack)}
    return {key: _inline_refs(value, definitions, stack) for key, value in node.items()}


def _normalize(node: dict[str, Any], dialect: SchemaDialect, path: str) -> dict[str, Any]:
    node = {key: value for key, value in node.items() if key not in _DROP_KEYS[dialect]}

    if "anyOf" in node:
        options = [_normalize(option, dialect, path) for option in node.pop("anyOf")]
        non_null = [option for option in options if option != {"type": "null"}]
        nullable = len(non_null) < len(options)
        if nullable and len(non_null) == 1 and isinstance(non_null[0].get("type"), str):
            # Optional[T] -> type: [T, "null"]
            merged = {**non_null[0], **node}
            merged["type"] = [non_null[0]["type"], "null"]
            if "enum" in merged:
                merged["enum"] = [*merged["enum"], None]
            return merged
        if dialect == "json_schema_basic":
            raise ToolSchemaError(f"{path}: union types are not supported by {dialect}")
        node["anyOf"] = options
        return node

    if node.get("type") == "object":
        if "additionalProperties" in node and node["additionalProperties"] is not False:
            raise ToolSchemaError(f"{path}: free-form objects (dict) are not supported")
        properties = {
            name: _normalize(value, dialect, f"{path}.{name}")
            for name, value in node.get("properties", {}).items()
        }
        node["properties"] = properties
        node["additionalProperties"] = False
        if dialect == "openai_strict":
            # Strict yêu cầu mọi field nằm trong required; field tùy chọn đã là nullable.
            node["required"] = list(properties)
        return node

    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        node["items"] = _normalize(node["items"], dialect, f"{path}[]")
    return node
