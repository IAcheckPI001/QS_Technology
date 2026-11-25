"""Đối tượng xem (2026-11-21): website chỉ tra chunk `public`, kênh CRM cả `internal`; mặc định hẹp nhất."""

import asyncio

from app.modules.chatbot.repositories.doc_chunk_v2_repository import DocChunkV2Repository
from app.modules.chatbot.retrieval.audience import audiences_for
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.system import RetrievalRequest
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from tests.chatbot.builders import make_request_context
from tests.chatbot.test_retrieval import (
    FakeRepository,
    _analysis,
    _match,
    _request,
    _retriever,
    _state,
    _sub_query,
)
from tests.chatbot.test_retrieval_v2 import ROW, _Session

KEY = ("technical_docs", ("installation",), ("F86",))


def test_audiences_by_channel_and_fail_safe_default() -> None:
    assert audiences_for(ChannelType.WEBSITE) == ("public",)
    assert audiences_for(ChannelType.CRM) == ("public", "internal")
    assert audiences_for("crm") == ("public", "internal")
    for unknown in (None, "", "partner", 7):
        assert audiences_for(unknown) == ("public",)         # kênh lạ: tập hẹp nhất


def test_request_defaults_to_public_only() -> None:
    assert _request().audiences == ["public"]
    assert RetrievalRequest.model_fields["audiences"].default_factory() == ["public"]


def _run(channel: ChannelType) -> FakeRepository:
    repository = FakeRepository({KEY: [_match(1)]})
    analysis = _analysis(_sub_query("Cách lắp đặt F86", "guide.installation", ["F86"]))
    state = _state("Cách lắp đặt F86", analysis)
    state.request_context = make_request_context(channel)
    asyncio.run(ExecutionStage(retriever=_retriever(repository)).execute(state))
    return repository


def test_website_turn_searches_and_fetches_public_only() -> None:
    repository = _run(ChannelType.WEBSITE)
    assert repository.calls and all(call["audiences"] == ["public"] for call in repository.calls)
    assert repository.fetch_audiences == [["public"]]


def test_crm_turn_searches_and_fetches_public_and_internal() -> None:
    repository = _run(ChannelType.CRM)
    assert repository.calls and all(call["audiences"] == ["public", "internal"] for call in repository.calls)
    assert repository.fetch_audiences == [["internal", "public"]]


def test_targets_with_different_audiences_fetch_the_narrowest() -> None:
    """Một target lệch quyền không được mở rộng quyền xem khi lấy chunk cha."""
    repository = FakeRepository({KEY: [_match(1)]})
    wide = _request().model_copy(update={"audiences": ["public", "internal"]})
    narrow = _request().model_copy(update={"audiences": ["public"]})
    asyncio.run(_retriever(repository).search([wide, narrow]))
    assert repository.fetch_audiences == [["public"]]


def test_repository_sends_audiences_and_defaults_to_public() -> None:
    session = _Session([ROW])
    repo = DocChunkV2Repository(session_factory=lambda: session)
    kwargs = dict(embedding=[0.1], query_text="q", domain="technical_docs", scopes=[], models=[],
                  control_interface=[], spec_attributes=[], vector_k=5, fts_k=5, rrf_k=60, spec_boost=0.0)
    asyncio.run(repo.match(**kwargs))                                       # quên truyền: chỉ public
    asyncio.run(repo.match(**kwargs, audiences=("public", "internal")))
    asyncio.run(repo.fetch_by_ids([7]))
    asyncio.run(repo.fetch_by_ids([7], ("public", "internal")))
    (match_sql, default_params), (_, wide_params), (fetch_sql, fetch_default), (_, fetch_wide) = session.calls
    assert "p_audiences" in match_sql and "audience = any" in fetch_sql
    assert default_params["audiences"] == ["public"] and wide_params["audiences"] == ["public", "internal"]
    assert fetch_default["audiences"] == ["public"] and fetch_wide["audiences"] == ["public", "internal"]


def test_technical_models_coverage_counts_public_chunks_only() -> None:
    session = _Session([{"model": "F54"}])
    repo = DocChunkV2Repository(session_factory=lambda: session)
    assert asyncio.run(repo.technical_docs_models()) == ["F54"]
    assert "audience = 'public'" in session.calls[0][0]
