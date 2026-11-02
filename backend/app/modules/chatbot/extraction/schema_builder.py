
from app.modules.chatbot.extraction.registry import REGISTRY as R


def build_output_schema() -> dict:
    """Schema strict (OpenAI Structured Outputs). v3.1: thêm pending_answer; v3.2: thêm model_dependency; v3.3: thêm language;
    v3.4: thêm excluded_control_interface, interface_match, unmapped_conditions."""
 
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
        "excluded_control_interface": arr(R["control_interface"]),
        "interface_match": {"type": "string", "enum": ["all", "any"]},
        "unmapped_conditions": arr(),
        "spec_attributes": arr(R["spec_attributes"]),
        "handoff_reason": {"type": ["string", "null"], "enum": [*R["handoff_reasons"], None]},
        "history_conflict": {"type": "boolean"},
        "model_dependency": {"type": "string", "enum": ["general", "model_specific"]},
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
            "language": {"type": "string"},
        },
        "required": ["sub_queries", "pending_answer", "language"],
        "additionalProperties": False,
    }