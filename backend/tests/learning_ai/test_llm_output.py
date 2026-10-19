from typing import Any, Iterator

import pytest

from app.modules.learning_ai.schemas.content import KnowledgeType
from app.modules.learning_ai.schemas.llm_output import (SegmentationOutput, extraction_model_for,
                                                        to_strict_schema)


def _nodes(node: Any) -> Iterator[dict]:
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _nodes(v)
    elif isinstance(node, list):
        for v in node:
            yield from _nodes(v)


@pytest.mark.parametrize("kt", list(KnowledgeType))
def test_extraction_schema_is_strict(kt, reg):
    schema = to_strict_schema(extraction_model_for(kt), reg)

    objects = [n for n in _nodes(schema) if n.get("type") == "object" and "properties" in n]
    assert objects
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])
        assert "source_id" not in obj["properties"]
    for n in _nodes(schema):
        assert "reviewer_confirmed" not in n.get("enum", [])
        assert "discriminator" not in n


@pytest.mark.parametrize("kt", list(KnowledgeType))
def test_extraction_schema_injects_registry_enums(kt, reg):
    schema = to_strict_schema(extraction_model_for(kt), reg)

    props = [n["properties"] for n in _nodes(schema) if "properties" in n]
    models = next(p["product_models"] for p in props if "product_models" in p)
    intents = next(p["intents"] for p in props if "intents" in p)
    assert models["items"]["enum"] == ["F54", "F86", "G10"]
    assert intents["items"]["enum"] == ["setup", "troubleshoot"]


def test_segmentation_schema_is_strict(reg):
    schema = to_strict_schema(SegmentationOutput, reg)

    for obj in (n for n in _nodes(schema) if n.get("type") == "object" and "properties" in n):
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])
