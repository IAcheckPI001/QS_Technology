"""Chuẩn bị một hội thoại CRM cho bước tách segment: nạp → lọc → privacy.

Không lưu job (chưa có bảng); Segmenter/Extractor chưa được nối.
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Protocol, Sequence
from uuid import UUID

from app.core.config import Settings
from app.modules.chatbot.providers.ollama_model import OllamaModelProvider
from app.util.token_counter import count_tokens

from ..privacy.pipeline import PrivacyPipeline
from ..privacy.schemas import PrivacyCheckUnavailable, PrivacyResult
from ..privacy.sensitivity_checker import SensitivityChecker
from ..schemas.common import StrictModel
from ..schemas.registry import RegistrySnapshot
from .prefilter import prefilter
from .source_document import SupportChatRow, build_source_document

logger = logging.getLogger(__name__)


class PrivacyConfigurationError(RuntimeError):
    """Ollama là bắt buộc cho luồng học tri thức."""


class IngestionStatus(str, Enum):
    READY = "ready"
    SKIPPED = "skipped"
    NOT_FOUND = "not_found"
    PRIVACY_UNAVAILABLE = "privacy_unavailable"


class IngestionResult(StrictModel):
    status: IngestionStatus
    session_id: UUID
    reason: str | None = None
    privacy: PrivacyResult | None = None


class SupportChatSource(Protocol):
    async def list_for_session(self, *, session_id: UUID) -> Sequence[SupportChatRow]: ...


class LearningIngestionService:
    def __init__(self, repository: SupportChatSource, pipeline: PrivacyPipeline,
                 registry: RegistrySnapshot | None = None) -> None:
        self._repository = repository
        self._pipeline = pipeline
        self._registry = registry

    async def prepare(self, session_id: UUID) -> IngestionResult:
        started = time.perf_counter()
        rows = await self._repository.list_for_session(session_id=session_id)
        if not rows:
            logger.info("learning ingestion session_id=%s status=not_found", session_id)
            return IngestionResult(status=IngestionStatus.NOT_FOUND, session_id=session_id)

        document = build_source_document(session_id, rows)
        logger.info("learning ingestion loaded session_id=%s source_id=%s rows=%d units=%d",
                    session_id, document.source_id, len(rows), len(document.units))

        skip = prefilter(document, self._registry)
        if skip is not None:
            logger.info("learning ingestion session_id=%s status=skipped reason=%s elapsed_ms=%d",
                        session_id, skip.value, _elapsed_ms(started))
            return IngestionResult(status=IngestionStatus.SKIPPED, session_id=session_id, reason=skip.value)

        try:
            privacy = await self._pipeline.run(document)
        except PrivacyCheckUnavailable as exc:
            logger.warning("learning ingestion session_id=%s source_id=%s status=privacy_unavailable "
                           "reason=%s elapsed_ms=%d", session_id, document.source_id, exc, _elapsed_ms(started))
            return IngestionResult(status=IngestionStatus.PRIVACY_UNAVAILABLE, session_id=session_id,
                                   reason=str(exc))
        logger.info("learning ingestion session_id=%s source_id=%s status=ready elapsed_ms=%d",
                    session_id, document.source_id, _elapsed_ms(started))
        return IngestionResult(status=IngestionStatus.READY, session_id=session_id, privacy=privacy)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def create_privacy_pipeline(settings: Settings) -> tuple[PrivacyPipeline, OllamaModelProvider]:
    """Dựng pipeline với Ollama. Caller chịu trách nhiệm `await provider.close()`."""
    if not settings.ollama_base_url or not settings.ollama_model:
        raise PrivacyConfigurationError("OLLAMA_BASE_URL and OLLAMA_MODEL are required for learning ingestion")
    provider = OllamaModelProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout=settings.ollama_timeout_seconds,
        num_ctx=settings.ollama_num_ctx,
    )
    checker = SensitivityChecker(
        provider,
        window_tokens=settings.ollama_window_tokens,
        token_counter=lambda text: count_tokens(text, settings.ollama_model),
    )
    return PrivacyPipeline(checker), provider
