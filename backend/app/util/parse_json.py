

import json
from typing import Any


class InvalidModelJSONError(ValueError):
    """Raised when the model response is not a valid JSON object."""


def parse_json_object(content: str | None) -> dict[str, Any]:
    if not content or not content.strip():
        raise InvalidModelJSONError("Model returned empty JSON content.")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InvalidModelJSONError(
            "Model returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise InvalidModelJSONError(
            "Expected a JSON object at the top level."
        )

    return payload