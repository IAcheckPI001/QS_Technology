
from app.modules.chatbot.extraction.registry import REGISTRY as R


def build_output_schema() -> dict:
    """Schema strict (OpenAI Structured Outputs). v3.1: thêm pending_answer."""
 
    def arr(enum=None) -> dict:
        items: dict = {"type": "string"}
        if enum:
            items["enum"] = list(enum)
        return {"type": "array", "items": items}
 
    props = {
        "standalone_query": {"type": "string"},
        "intent": {"type": "string", "enum": list(R["intents"])},
        "product_models": arr(R["product_models"]),
        "unresolved_mentions": arr(),
        "control_interface": arr(R["control_interface"]),
        "spec_attribute": arr(R["spec_attributes"]),
        "handoff_reason": {"type": ["string", "null"], "enum": [*R["handoff_reasons"], None]},
        "history_conflict": {"type": "boolean"},
    }
    sub_query = {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "sub_queries": {"type": "array", "items": sub_query},
            "pending_answer": {"type": ["string", "null"]},
        },
        "required": ["sub_queries", "pending_answer"],
        "additionalProperties": False,
    }