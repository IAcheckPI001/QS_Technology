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
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    # Tham số retrieval khởi đầu để thử nghiệm, chưa tối ưu cho dữ liệu QS Technology:
    # điều chỉnh theo Recall@k, số parent trùng và độ dài context thực tế.
    retrieval_vector_candidate_k: int = Field(default=20, alias="RETRIEVAL_VECTOR_CANDIDATE_K")
    retrieval_fts_candidate_k: int = Field(default=20, alias="RETRIEVAL_FTS_CANDIDATE_K")
    retrieval_rrf_k: int = Field(default=60, alias="RETRIEVAL_RRF_K")
    retrieval_final_chunk_top_k: int = Field(default=6, alias="RETRIEVAL_FINAL_CHUNK_TOP_K")
    retrieval_max_context_parents: int = Field(default=5, alias="RETRIEVAL_MAX_CONTEXT_PARENTS")
    # Cosine similarity tối thiểu để chunk được coi là liên quan; cần đo lại trên dữ liệu thật.
    retrieval_min_similarity: float = Field(default=0.25, alias="RETRIEVAL_MIN_SIMILARITY")
    retrieval_spec_boost: float = Field(default=0.005, alias="RETRIEVAL_SPEC_BOOST")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    gpt4o_mini_input_usd_per_million: float = Field(default=0.15, alias="GPT4O_MINI_INPUT_USD_PER_MILLION")
    gpt4o_mini_output_usd_per_million: float = Field(default=0.60, alias="GPT4O_MINI_OUTPUT_USD_PER_MILLION")
    embedding_input_usd_per_million: float = Field(default=0.02, alias="EMBEDDING_INPUT_USD_PER_MILLION")
    usd_to_vnd_rate: float = Field(default=26000, alias="USD_TO_VND_RATE")
    
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
    CORS_ALLOW_CREDENTIALS: bool = Field(default=False, alias="CORS_ALLOW_CREDENTIALS")
    TRUST_PROXY_REQUEST_ID: bool = Field(default=False, alias="TRUST_PROXY_REQUEST_ID")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    # Khóa HMAC ký visitor token của khách website; để trống thì /chat/website trả 503.
    visitor_token_secret: str = Field(default="", alias="VISITOR_TOKEN_SECRET")
    visitor_token_ttl_seconds: int = Field(default=7 * 24 * 3600, alias="VISITOR_TOKEN_TTL_SECONDS")
    visitor_token_issuer: str = Field(default="qs-chatbot", alias="VISITOR_TOKEN_ISSUER")
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

    @field_validator(
        "embedding_dimensions",
        "retrieval_vector_candidate_k",
        "retrieval_fts_candidate_k",
        "retrieval_rrf_k",
        "retrieval_final_chunk_top_k",
        "retrieval_max_context_parents",
    )
    @classmethod
    def _validate_retrieval_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Embedding and retrieval sizes must be greater than zero")
        return value

    @model_validator(mode="after")
    def _final_top_k_within_candidates(self) -> "Settings":
        if self.retrieval_final_chunk_top_k > self.retrieval_vector_candidate_k:
            raise ValueError(
                "RETRIEVAL_FINAL_CHUNK_TOP_K must not exceed RETRIEVAL_VECTOR_CANDIDATE_K"
            )
        return self

    @field_validator("visitor_token_secret", mode="before")
    @classmethod
    def _strip_secret(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _visitor_token_settings(self) -> "Settings":
        if self.visitor_token_secret and len(self.visitor_token_secret.encode()) < 32:
            raise ValueError("VISITOR_TOKEN_SECRET must be at least 32 bytes")
        if self.visitor_token_ttl_seconds <= 0:
            raise ValueError("VISITOR_TOKEN_TTL_SECONDS must be greater than zero")
        return self

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
