import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.learning_ai.ingestion.service import PrivacyConfigurationError, create_privacy_pipeline

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    provider = None
    if settings.openai_api_key:
        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    application.state.chatbot_provider = provider

    privacy_provider = None
    application.state.learning_privacy_pipeline = None
    if settings.learning_api_enabled:
        try:
            pipeline, privacy_provider = create_privacy_pipeline(settings)
            application.state.learning_privacy_pipeline = pipeline
            logger.info("learning API enabled with Ollama model=%s", settings.ollama_model)
        except PrivacyConfigurationError:
            logger.warning("learning API enabled but Ollama is not configured; requests will return 503")
    try:
        yield
    finally:
        if provider is not None:
            await provider.close()
        if privacy_provider is not None:
            await privacy_provider.close()


app = FastAPI(title="QS Chatbot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.include_router(api_router)
