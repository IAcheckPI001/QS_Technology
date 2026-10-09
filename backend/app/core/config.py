from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_origins(value: str | list[str]) -> list[str]:
    origins = value.split(",") if isinstance(value, str) else value
    return [origin.strip().rstrip("/") for origin in origins if origin.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        enable_decoding=False,
        extra="ignore",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        alias="CORS_ORIGINS",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(alias="DATABASE_URL")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    database_pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=5, alias="DATABASE_MAX_OVERFLOW")
    database_pool_recycle: int = Field(default=1800, alias="DATABASE_POOL_RECYCLE")
    database_pool_mode: str = Field(default="session", alias="DATABASE_POOL_MODE")

    @field_validator("openai_api_key", "openai_model", mode="before")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _normalize_origins(
        cls,
        value: str | list[str],
    ) -> list[str]:
        return _parse_origins(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def get_db_settings() -> Settings:
    return get_settings()
