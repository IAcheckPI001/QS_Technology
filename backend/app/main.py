

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.middleware.request_context import RequestContextMiddleware
from app.core.config import settings
from app.core.logging import configure_logging
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.repositories.doc_chunk_repository import DocChunkRepository
from app.modules.chatbot.retrieval import Retriever, RetrieverConfig
from app.modules.learning_ai.ingestion.service import PrivacyConfigurationError, create_privacy_pipeline

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    provider = None
    retriever = None
    if settings.openai_api_key:
        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            embedding_model=settings.embedding_model,
        )
        retriever = Retriever(
            provider,
            DocChunkRepository(),
            RetrieverConfig.from_settings(settings),
        )
    application.state.chatbot_provider = provider
    application.state.chatbot_retriever = retriever

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

def create_app() -> FastAPI:
    app = FastAPI(title="QS Chatbot API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Accept",
            "Authorization",
            "Idempotency-Key",
            "X-Request-ID",
            "X-CSRF-Token",
        ],
        expose_headers=["X-Request-ID"],
    )

    app.include_router(api_router)
    
    return app

configure_logging(settings.log_level)
fastapi_app = create_app()  # dùng cho include_router, dependency_overrides
# Lớp NGOÀI CÙNG: chạy `uvicorn app.main:app`
app = RequestContextMiddleware(
    fastapi_app,
    trust_incoming_request_id= settings.TRUST_PROXY_REQUEST_ID,  # chỉ bật khi reverse proxy luôn ghi đè X-Request-ID
)