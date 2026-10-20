from typing import Any, Iterator

import pytest
from pydantic import ValidationError

from app.modules.learning_ai.schemas.content import KnowledgeType
from app.modules.learning_ai.schemas.llm_output import (Segment, SegmentationOutput, extraction_model_for,
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


def test_skipped_segment_may_omit_knowledge_type():
    seg = Segment(segment_id="S2", knowledge_type=None, problem_statement="Hỏi tình trạng giao hàng",
                  message_ids=["m5", "m6"], resolved=False, skip_reason="ngoài phạm vi kỹ thuật")

    assert seg.knowledge_type is None


def test_kept_segment_requires_knowledge_type():
    with pytest.raises(ValidationError):
        Segment(segment_id="S1", knowledge_type=None, problem_statement="F86 lệch xung",
                message_ids=["m1"], resolved=True, skip_reason=None)
