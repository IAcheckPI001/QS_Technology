from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_origins(value: str | list[str]) -> list[str]:
    origins = value.split(",") if isinstance(value, str) else value
    return [origin.strip().rstrip("/") for origin in origins if origin.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        enable_decoding=False,
        extra="ignore",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    context_token_budget: int = Field(default=2048, alias="CONTEXT_TOKEN_BUDGET",)
    ollama_base_url: str = Field(default="", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="", alias="OLLAMA_MODEL")
    ollama_timeout_seconds: float = Field(default=180.0, alias="OLLAMA_TIMEOUT_SECONDS")
    ollama_num_ctx: int = Field(default=8192, alias="OLLAMA_NUM_CTX")
    ollama_window_tokens: int = Field(default=2500, alias="OLLAMA_WINDOW_TOKENS")
    # Endpoint học tri thức chưa có xác thực: chỉ bật khi kiểm thử nội bộ.
    learning_api_enabled: bool = Field(default=False, alias="LEARNING_API_ENABLED")
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

    @field_validator("openai_api_key", "openai_model", "ollama_base_url", "ollama_model", mode="before")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("ollama_timeout_seconds", "ollama_num_ctx", "ollama_window_tokens")
    @classmethod
    def _validate_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Ollama timeout, num_ctx and window tokens must be greater than zero")
        return value

    @model_validator(mode="after")
    def _window_fits_context(self) -> "Settings":
        if self.ollama_window_tokens >= self.ollama_num_ctx:
            raise ValueError("OLLAMA_WINDOW_TOKENS must be smaller than OLLAMA_NUM_CTX")
        return self

    @field_validator("context_token_budget")
    @classmethod
    def _validate_context_budget(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("CONTEXT_TOKEN_BUDGET must be greater than zero")
        return value

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
