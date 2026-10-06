from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.service import ChatbotService


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    provider = None
    if settings.openai_api_key:
        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    application.state.chatbot_service = (
        ChatbotService(provider) if provider is not None else None
    )
    try:
        yield
    finally:
        if provider is not None:
            await provider.close()


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
