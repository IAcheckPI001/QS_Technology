
import pytest
from app.core.config import Settings


def test_settings_parse_comma_separated_origins(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host/db")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        " http://localhost:5173/ , https://example.com ",
    )
    monkeypatch.setenv("LOG_LEVEL", " debug ")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://example.com",
    ]
    assert settings.log_level == "DEBUG"


def test_settings_default_model(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host/db")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.openai_model == "gpt-4o-mini"
