

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.middleware.request_context import RequestContextMiddleware
from app.core.config import settings
from app.core.logging import configure_logging
from app.modules.chatbot.agent.setup import build_agent_runner
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.providers.supabase_storage import AssetSigner
from app.modules.chatbot.extraction.registry import extend_technical_coverage
from app.modules.chatbot.repositories.doc_chunk_v2_repository import DocChunkV2Repository, MatchV2Options
from app.modules.chatbot.retrieval import QueryEmbedder, Retriever, RetrieverConfig
from app.modules.learning_ai.ingestion.service import PrivacyConfigurationError, create_privacy_pipeline

logger = logging.getLogger(__name__)


def build_doc_repository() -> DocChunkV2Repository:
    """Repository tra cứu của chat: `doc_chunks_v2` (D-009), mặc định production của `MatchV2Options`."""
    return DocChunkV2Repository(MatchV2Options(approved_only=settings.retrieval_approved_only))


def build_retriever(embedder: QueryEmbedder, repository: DocChunkV2Repository) -> Retriever:
    return Retriever(embedder, repository, RetrieverConfig.from_settings(settings))


async def load_technical_coverage(repository: DocChunkV2Repository) -> list[str]:
    """Thêm vào registry các model có tài liệu kỹ thuật trong `doc_chunks_v2`; lỗi DB thì giữ registry tĩnh."""
    try:
        added = extend_technical_coverage(await repository.technical_docs_models())
    except Exception:
        logger.warning("Không nạp được coverage technical_docs từ doc_chunks_v2; dùng registry tĩnh", exc_info=True)
        return []
    logger.info(
        "Coverage technical_docs từ doc_chunks_v2 (approved_only=%s): thêm %s",
        repository.options.approved_only, ", ".join(added) or "không model nào",
    )
    return added


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
        repository = build_doc_repository()
        retriever = build_retriever(provider, repository)
        await load_technical_coverage(repository)
    agent_runner = None
    agent_provider = None
    if provider is not None and settings.crm_chat_flow == "agent":
        if settings.effective_agent_model != settings.openai_model:
            # Model riêng cho vòng lặp agent; luồng website và stage phân tích giữ OPENAI_MODEL.
            agent_provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.effective_agent_model,
                embedding_model=settings.embedding_model,
                reasoning_effort=settings.agent_reasoning_effort or None,
            )
        # Provider/tool không đủ điều kiện thì ToolConfigurationError dừng khởi động.
        agent_runner = build_agent_runner(provider, retriever, settings, agent_provider=agent_provider)
        logger.info(
            "CRM chat flow: agent (model=%s, tools=%s)",
            agent_runner.model, ", ".join(agent_runner.tool_names),
        )
    # Dùng chung một client HTTP cho mọi request; đóng khi tắt dịch vụ.
    asset_signer = AssetSigner.from_settings(settings)
    if settings.chat_sources_enabled and asset_signer is None:
        logger.warning("CHAT_SOURCES_ENABLED=true nhưng thiếu SUPABASE_URL hoặc SUPABASE_SERVICE_ROLE_KEY: tắt event sources")
    application.state.chatbot_asset_signer = asset_signer
    application.state.chatbot_provider = provider
    application.state.chatbot_retriever = retriever
    application.state.chatbot_agent_runner = agent_runner

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
        if agent_provider is not None:
            await agent_provider.close()
        if privacy_provider is not None:
            await privacy_provider.close()
        if asset_signer is not None:
            await asset_signer.close()

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