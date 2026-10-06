from collections.abc import AsyncIterator

from app.modules.chatbot.prompts.default import SYSTEM_PROMPT
from app.modules.chatbot.providers.openai import OpenAIProvider


class ChatbotService:
    def __init__(self, provider: OpenAIProvider) -> None:
        self._provider = provider

    async def stream_reply(self, message: str) -> AsyncIterator[str]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]
        async for chunk in self._provider.stream_chat(messages):
            yield chunk
