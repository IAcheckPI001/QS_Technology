"""Client OpenAI cho Bước 3 (chỉ venv chính có SDK `openai`; module chỉ import SDK khi tạo client).

Key lấy từ env `OPENAI_API_KEY` (rơi về `backend/.env`, xem `env.py`), không in, không ghi log.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.modules.doc_ingest.enrich.prompt import SYSTEM_PROMPT, user_message
from app.modules.doc_ingest.schemas.chunk import DraftChunk, EnrichmentOutput


@dataclass(frozen=True)
class EnrichResult:
    output: EnrichmentOutput
    input_tokens: int
    output_tokens: int


class Enricher(Protocol):
    model: str

    def enrich(self, chunk: DraftChunk) -> EnrichResult: ...


class OpenAIEnricher:
    """Structured output (JSON schema theo `EnrichmentOutput`), temperature 0 để chạy lại ổn định."""

    def __init__(self, model: str, api_key: str, system: str = SYSTEM_PROMPT, timeout_s: float = 60.0,
                 max_retries: int = 2) -> None:
        if not api_key:
            raise SystemExit("thiếu OPENAI_API_KEY (env hoặc backend/.env)")
        from openai import OpenAI

        self.model = model
        self.system = system
        self._client = OpenAI(api_key=api_key, timeout=timeout_s, max_retries=max_retries)

    def enrich(self, chunk: DraftChunk) -> EnrichResult:
        response = self._client.chat.completions.parse(
            model=self.model,
            temperature=0,
            messages=[{"role": "system", "content": self.system},
                      {"role": "user", "content": user_message(chunk)}],
            response_format=EnrichmentOutput,
        )
        message = response.choices[0].message
        if message.parsed is None:
            raise RuntimeError(f"model không trả JSON hợp lệ (refusal: {message.refusal!r})")
        usage = response.usage
        return EnrichResult(message.parsed, usage.prompt_tokens if usage else 0,
                            usage.completion_tokens if usage else 0)
