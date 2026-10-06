import os

from dotenv import load_dotenv


# Load backend/.env when the application is started from the backend directory.
load_dotenv()


def _parse_origins(value: str) -> list[str]:
    return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]


class Settings:
    def __init__(self) -> None:
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.cors_origins = _parse_origins(
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            )
        )
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
