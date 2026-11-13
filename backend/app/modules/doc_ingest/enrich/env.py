"""Cấu hình OpenAI cho Bước 3. `doc_ingest` không import `app.core.config` (ranh giới import của tool offline,
`tests/doc_ingest/test_import_boundary.py`), nên đọc thẳng biến môi trường, rơi về `backend/.env`.
Không in, không ghi log giá trị key."""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[4] / ".env"
DEFAULT_MODEL = "gpt-4o-mini"
# Giá gpt-4o-mini (USD / 1M token), cùng giá trị mặc định với Settings của dịch vụ chat; model khác → truyền giá.
GPT4O_MINI_INPUT_USD = 0.15
GPT4O_MINI_OUTPUT_USD = 0.60


def _env_value(name: str) -> str:
    value = os.environ.get(name, "")
    if value or not ENV_FILE.is_file():
        return value
    from dotenv import dotenv_values

    return dotenv_values(ENV_FILE).get(name) or ""


def openai_api_key() -> str:
    return _env_value("OPENAI_API_KEY")


def openai_model() -> str:
    return _env_value("OPENAI_MODEL") or DEFAULT_MODEL
