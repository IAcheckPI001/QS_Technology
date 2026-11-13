"""Tham số OpenAIProvider gửi đi theo loại model (model suy luận không nhận temperature/max_tokens)."""

import asyncio
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.modules.chatbot.providers.openai import OpenAIProvider, is_reasoning_model


class _Usage:
    prompt_tokens = 10
    completion_tokens = 2
    prompt_tokens_details = None


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content='{"ok": true}', tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=_Usage())


def _provider(model: str, effort: str | None = None) -> tuple[OpenAIProvider, _FakeCompletions]:
    provider = OpenAIProvider(api_key="test", model=model, reasoning_effort=effort)
    completions = _FakeCompletions()
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))  # type: ignore[assignment]
    return provider, completions


@pytest.mark.parametrize(("model", "reasoning"), [
    ("gpt-4o-mini", False), ("gpt-4.1", False), ("gpt-4.1-mini", False),
    ("gpt-5-mini", True), ("gpt-5.4-mini", True), ("o3", True), ("o4-mini", True), ("omni-x", False),
])
def test_reasoning_model_detection(model, reasoning):
    assert is_reasoning_model(model) is reasoning


def test_classic_model_keeps_temperature_and_max_tokens():
    provider, completions = _provider("gpt-4o-mini", effort="low")
    asyncio.run(provider.chat_complete_tools([{"role": "user", "content": "x"}], [], max_tokens=900))
    [call] = completions.calls
    assert call["temperature"] == 0 and call["max_tokens"] == 900
    assert "max_completion_tokens" not in call and "reasoning_effort" not in call
    assert provider.capabilities.reasoning is False


def test_reasoning_model_uses_max_completion_tokens_and_effort():
    provider, completions = _provider("gpt-5-mini", effort="low")
    asyncio.run(provider.chat_complete_tools(
        [{"role": "user", "content": "x"}], [{"type": "function"}], max_tokens=4000,
    ))
    asyncio.run(provider.chat_complete_json([{"role": "user", "content": "x"}]))
    tools_call, json_call = completions.calls
    for call in (tools_call, json_call):
        assert "temperature" not in call and "max_tokens" not in call
        assert call["reasoning_effort"] == "low"
    assert tools_call["max_completion_tokens"] == 4000 and tools_call["parallel_tool_calls"] is True
    assert provider.capabilities.reasoning is True and provider.capabilities.tool_calling is True


def test_agent_model_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("AGENT_MODEL", " gpt-5-mini ")
    monkeypatch.setenv("AGENT_REASONING_EFFORT", "low")
    settings = Settings()
    assert settings.effective_agent_model == "gpt-5-mini"
    assert settings.agent_max_completion_tokens == 1200
    monkeypatch.setenv("AGENT_MODEL", "")
    assert Settings().effective_agent_model == "gpt-4o-mini"
    monkeypatch.setenv("AGENT_REASONING_EFFORT", "extreme")
    with pytest.raises(ValueError):
        Settings()
