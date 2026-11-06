from enum import StrEnum
from typing import Literal

import pytest
from pydantic import Field

from app.core.config import Settings
from app.modules.chatbot.agent.setup import build_agent_runner
from app.modules.chatbot.schemas.default import SystemModel
from app.modules.chatbot.schemas.system import LLMCapabilities
from app.modules.chatbot.tools import (
    ProductDocsAskInput,
    ToolConfigurationError,
    ToolRegistry,
    ToolSchemaError,
    to_provider_schema,
)
from tests.chatbot.agent_fakes import ScriptedToolProvider, echo_tool


class Scope(StrEnum):
    INSTALLATION = "installation"
    OPERATION = "operation"


class Period(SystemModel):
    start: str
    end: str | None = None


class ReportIn(SystemModel):
    scope: Scope
    status: Literal["open", "closed"] = "open"
    limit: int | None = Field(default=None, ge=1, le=50)
    period: Period
    tags: list[str] = Field(default_factory=list, max_length=5)


def test_product_docs_strict_schema_snapshot():
    assert to_provider_schema(ProductDocsAskInput, "openai_strict") == {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Câu hỏi tự đủ nghĩa, ghi rõ mã model nếu đã biết.",
            },
            # Strict: field có default vẫn nằm trong required (LLM gửi [] khi không trích nguồn);
            # giới hạn số phần tử kiểm tra bằng code, không gửi maxItems cho provider.
            "based_on_sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "source_id (vd S3) đã nhận trong lượt này, nói rõ model trong question thỏa "
                    "điều kiện của câu hỏi trước. Để [] khi model do nhân viên nêu hoặc có trong "
                    "catalog_match."
                ),
            },
        },
        "required": ["question", "based_on_sources"],
        "additionalProperties": False,
    }


def test_strict_schema_inlines_refs_and_makes_optional_fields_nullable_and_required():
    schema = to_provider_schema(ReportIn, "openai_strict")

    assert "$defs" not in schema and "$ref" not in str(schema)
    assert schema["required"] == ["scope", "status", "limit", "period", "tags"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["scope"] == {
        "enum": ["installation", "operation"], "type": "string",
    }
    assert schema["properties"]["limit"] == {
        "type": ["integer", "null"], "minimum": 1, "maximum": 50,
    }
    period = schema["properties"]["period"]
    assert period["additionalProperties"] is False
    assert period["required"] == ["start", "end"]
    assert period["properties"]["end"] == {"type": ["string", "null"]}
    assert "default" not in str(schema) and "title" not in str(schema)


def test_basic_schema_keeps_pydantic_required_and_length_constraints():
    schema = to_provider_schema(ReportIn, "json_schema_basic")

    assert schema["required"] == ["scope", "period"]
    assert schema["properties"]["tags"]["maxItems"] == 5


class Email(SystemModel):
    address: str


class Phone(SystemModel):
    number: str


class ContactIn(SystemModel):
    contact: Email | Phone


class FreeFormIn(SystemModel):
    filters: dict[str, str]


def test_object_union_is_kept_for_strict_and_rejected_for_basic():
    strict = to_provider_schema(ContactIn, "openai_strict")
    assert len(strict["properties"]["contact"]["anyOf"]) == 2

    with pytest.raises(ToolSchemaError, match="union types"):
        to_provider_schema(ContactIn, "json_schema_basic")


def test_free_form_dict_parameters_are_rejected():
    with pytest.raises(ToolSchemaError, match="free-form"):
        to_provider_schema(FreeFormIn, "openai_strict")


def test_provider_tool_definition_is_function_with_strict_flag():
    registry = ToolRegistry([echo_tool()])

    [tool] = registry.provider_tools(registry.allowed(_principal()), "openai_strict")

    assert tool["type"] == "function"
    assert tool["function"]["name"] == "echo"
    assert tool["function"]["strict"] is True
    assert tool["function"]["parameters"]["required"] == ["text"]


@pytest.mark.parametrize("capabilities, missing", [
    (LLMCapabilities(), "tool_calling, tool_choice_none"),
    (LLMCapabilities(tool_calling=True), "tool_choice_none"),
])
def test_validate_rejects_provider_without_required_capabilities(capabilities, missing):
    with pytest.raises(ToolConfigurationError, match=f"missing {missing}"):
        ToolRegistry([echo_tool()]).validate_for(capabilities)


def test_validate_rejects_schema_the_provider_dialect_cannot_express():
    from app.modules.chatbot.tools import ToolSpec
    from tests.chatbot.agent_fakes import EchoOut

    spec = ToolSpec(name="contact", description="x", input_model=ContactIn,
                    output_model=EchoOut, run=echo_tool().run)
    basic = LLMCapabilities(tool_calling=True, tool_choice_none=True,
                            schema_dialect="json_schema_basic")

    with pytest.raises(ToolConfigurationError, match="contact: .*union types"):
        ToolRegistry([spec]).validate_for(basic)


def test_agent_setup_fails_at_startup_for_provider_without_tool_calling():
    provider = ScriptedToolProvider(capabilities=LLMCapabilities())

    with pytest.raises(ToolConfigurationError, match="does not support agent mode"):
        build_agent_runner(provider, retriever=object(), settings=_settings())


def test_agent_setup_requires_a_retriever():
    with pytest.raises(ToolConfigurationError, match="retriever"):
        build_agent_runner(ScriptedToolProvider(), retriever=None, settings=_settings())


def test_agent_setup_registers_product_docs_tool():
    runner = build_agent_runner(ScriptedToolProvider(), retriever=object(), settings=_settings())

    assert runner.tool_names == ["product_docs_ask"]


def test_agent_setup_registers_crm_report_when_enabled():
    settings = _settings(CRM_REPORT_ENABLED=True, CRM_API_BASE_URL="https://crm.test")
    runner = build_agent_runner(ScriptedToolProvider(), retriever=object(), settings=settings)

    assert runner.tool_names == ["product_docs_ask", "crm_report"]


def _settings(**overrides) -> Settings:
    # Ghi đè cờ CRM để file .env cục bộ không làm đổi kết quả test.
    return Settings(**{
        "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
        "CRM_REPORT_ENABLED": False,
        **overrides,
    })


def _principal():
    from tests.chatbot.builders import make_service_principal

    return make_service_principal()
