from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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
    # Kênh CRM chạy luồng agent (tool-calling); "pipeline" để rollback về luồng tra cứu cũ.
    crm_chat_flow: Literal["agent", "pipeline"] = Field(default="agent", alias="CRM_CHAT_FLOW")
    # Giới hạn của một lượt agent. Mọi timeout lấy từ deadline chung AGENT_TURN_TIMEOUT_S;
    # AGENT_FINAL_RESERVE_S được giữ lại cho bước trả lời cuối.
    agent_max_steps: int = Field(default=5, alias="AGENT_MAX_STEPS")
    agent_max_tool_calls: int = Field(default=8, alias="AGENT_MAX_TOOL_CALLS")
    agent_turn_timeout_s: float = Field(default=60.0, alias="AGENT_TURN_TIMEOUT_S")
    agent_llm_timeout_s: float = Field(default=20.0, alias="AGENT_LLM_TIMEOUT_S")
    agent_tool_timeout_s: float = Field(default=20.0, alias="AGENT_TOOL_TIMEOUT_S")
    agent_final_reserve_s: float = Field(default=10.0, alias="AGENT_FINAL_RESERVE_S")
    agent_tool_output_tokens: int = Field(default=3000, alias="AGENT_TOOL_OUTPUT_TOKENS")
    agent_parallel_tools: int = Field(default=3, alias="AGENT_PARALLEL_TOOLS")
    agent_max_concurrent_runs: int = Field(default=8, alias="AGENT_MAX_CONCURRENT_RUNS")
    agent_history_messages: int = Field(default=6, alias="AGENT_HISTORY_MESSAGES")
    # Tool báo cáo CRM (crm_report, thử nghiệm): gọi API CRM bằng Bearer <acting_user_id>.
    crm_report_enabled: bool = Field(default=False, alias="CRM_REPORT_ENABLED")
    crm_api_base_url: str = Field(default="", alias="CRM_API_BASE_URL")
    crm_api_timeout_s: float = Field(default=10.0, alias="CRM_API_TIMEOUT_S")
    crm_report_max_items: int = Field(default=2000, alias="CRM_REPORT_MAX_ITEMS")
    crm_report_timezone: str = Field(default="Asia/Ho_Chi_Minh", alias="CRM_REPORT_TIMEZONE")
    # Lease chống hai lượt chạy song song trên cùng phiên; hết hạn tự giải phóng nếu tiến trình chết.
    chat_turn_lease_s: int = Field(default=120, alias="CHAT_TURN_LEASE_S")
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

    @field_validator(
        "agent_max_steps",
        "agent_max_tool_calls",
        "agent_turn_timeout_s",
        "agent_llm_timeout_s",
        "agent_tool_timeout_s",
        "agent_tool_output_tokens",
        "agent_parallel_tools",
        "agent_max_concurrent_runs",
        "chat_turn_lease_s",
    )
    @classmethod
    def _validate_agent_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Agent limits and turn lease must be greater than zero")
        return value

    @field_validator("crm_api_base_url", "crm_report_timezone", mode="before")
    @classmethod
    def _strip_crm(cls, value: str) -> str:
        return value.strip()

    @field_validator("crm_api_timeout_s", "crm_report_max_items")
    @classmethod
    def _validate_crm_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("CRM API timeout and max items must be greater than zero")
        return value

    @model_validator(mode="after")
    def _crm_report_configured(self) -> "Settings":
        if not self.crm_report_enabled:
            return self
        if not self.crm_api_base_url:
            raise ValueError("CRM_REPORT_ENABLED requires CRM_API_BASE_URL")
        # Cần dữ liệu múi giờ (tzdata hệ thống hoặc package tzdata) khi bật tool.
        try:
            ZoneInfo(self.crm_report_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("CRM_REPORT_TIMEZONE must be an IANA timezone name") from None
        return self

    @model_validator(mode="after")
    def _agent_reserve_within_turn(self) -> "Settings":
        if not 0 <= self.agent_final_reserve_s < self.agent_turn_timeout_s:
            raise ValueError("AGENT_FINAL_RESERVE_S must be >= 0 and below AGENT_TURN_TIMEOUT_S")
        if self.chat_turn_lease_s <= self.agent_turn_timeout_s:
            raise ValueError("CHAT_TURN_LEASE_S must exceed AGENT_TURN_TIMEOUT_S")
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
