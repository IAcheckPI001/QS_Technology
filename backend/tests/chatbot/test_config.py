
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


def test_crm_report_requires_base_url_and_valid_timezone(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host/db")
    monkeypatch.setenv("CRM_REPORT_ENABLED", "true")
    monkeypatch.delenv("CRM_API_BASE_URL", raising=False)

    with pytest.raises(ValueError, match="CRM_REPORT_ENABLED requires CRM_API_BASE_URL"):
        Settings(_env_file=None)

    monkeypatch.setenv("CRM_API_BASE_URL", " https://crm.test ")
    monkeypatch.setenv("CRM_REPORT_TIMEZONE", "Mars/Base")
    with pytest.raises(ValueError, match="IANA timezone"):
        Settings(_env_file=None)

    monkeypatch.setenv("CRM_REPORT_TIMEZONE", "Asia/Ho_Chi_Minh")
    settings = Settings(_env_file=None)
    assert settings.crm_api_base_url == "https://crm.test"
    assert settings.crm_report_max_items == 2000
