"""D-014 giai đoạn B: nguồn đã trích dẫn kèm ảnh (URL ký) và event SSE `sources`."""

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
from starlette.requests import Request

from app.core.config import Settings
from app.modules.chatbot.analysis.analyzer import AnalysisError
from app.modules.chatbot.providers.supabase_storage import AssetSigner
from app.modules.chatbot.routers.sse import stream_chat
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.history import ChatHistoryItem
from app.modules.chatbot.schemas.system import ChunkAsset, ChunkHit
from app.modules.chatbot.services import ChatbotService
from app.modules.chatbot.services.turn_errors import turn_error
from app.modules.chatbot.services.turn_sources import retrieval_view
from app.modules.chatbot.sources import attach_chunk_images, attach_history_sources, build_sources, cited_source_ids
from tests.chatbot.agent_fakes import (
    FakeChunks,
    ScriptedToolProvider,
    agent_runner,
    analysis_output,
    answer,
    ask,
    calls,
    chunk,
    docs_registry,
    sub_query,
)
from tests.chatbot.builders import make_inbound, make_request_context, make_service_principal
from tests.chatbot.test_clarification import StoringHistoryRepository

SESSION_ID = UUID("00000000-0000-0000-0000-0000000000d1")


def _asset(n: int, bucket: str = "doc-assets") -> ChunkAsset:
    return ChunkAsset(bucket=bucket, path=f"f86/e{n}.png", page=n, printed_page=n + 1)


def _hit(source_id: str | None, assets: list[ChunkAsset], chunk_id: str = "1", pages=(5, 5)) -> ChunkHit:
    return ChunkHit(chunk_id=chunk_id, matched_chunk_ids=[chunk_id], doc_id="f86", section_title="Lắp đặt",
                    page_start=pages[0], page_end=pages[1], content="nội dung", assets=assets,
                    score=0.5, source_id=source_id)


class FakeSigner:
    def __init__(self, missing: set[str] | None = None) -> None:
        self.missing = missing or set()
        self.requested: list[list[ChunkAsset]] = []

    async def sign(self, assets):
        assets = list(assets)
        self.requested.append(assets)
        return {(a.bucket, a.path): f"https://signed.example/{a.path}?token=t" for a in assets
                if a.path not in self.missing}


def test_cited_source_ids_orders_dedupes_and_reads_lists() -> None:
    assert cited_source_ids("Bước 1 [S2]. Bước 2 [S1, S2]. Hết [S10].") == ["S2", "S1", "S10"]
    assert cited_source_ids("không trích dẫn; S1 không có ngoặc, [abc], [S]") == []
    assert cited_source_ids("[S01] cũng là S1") == ["S1"]


def test_build_sources_keeps_only_cited_hits_with_signed_images() -> None:
    hits = [_hit("S1", [_asset(1), _asset(2)]), _hit("S2", [_asset(3)], chunk_id="2"), _hit(None, [_asset(4)], "3")]
    signer = FakeSigner()
    items = asyncio.run(build_sources(hits, "Làm theo [S1].", signer))
    assert [i.source_id for i in items] == ["S1"] and items[0].pages == "5"
    assert [(img.page, img.printed_page) for img in items[0].images] == [(1, 2), (2, 3)]
    assert all(img.url.startswith("https://signed.example/") for img in items[0].images)
    assert [a.path for a in signer.requested[0]] == ["f86/e1.png", "f86/e2.png"]   # S2/ảnh không trích dẫn: không ký


def test_build_sources_limits_images_and_formats_page_range() -> None:
    hit = _hit("S1", [_asset(n) for n in range(1, 6)], pages=(5, 7))
    [item] = asyncio.run(build_sources([hit], "[S1]", FakeSigner(), max_images=2))
    assert len(item.images) == 2 and item.pages == "5-7"
    [no_images] = asyncio.run(build_sources([hit], "[S1]", FakeSigner(), max_images=0))
    assert no_images.images == []


def test_build_sources_degrades_without_signer_or_when_signing_fails() -> None:
    hit = _hit("S1", [_asset(1), _asset(2)])
    [item] = asyncio.run(build_sources([hit], "[S1]", None))
    assert item.source_id == "S1" and item.images == []                    # vẫn có nguồn, không có ảnh
    [partial] = asyncio.run(build_sources([hit], "[S1]", FakeSigner(missing={"f86/e1.png"})))
    assert [img.page for img in partial.images] == [2]
    assert asyncio.run(build_sources([hit], "không trích dẫn", FakeSigner())) == []


def _signer(handler) -> AssetSigner:
    return AssetSigner("https://proj.supabase.co/", "service-secret", ttl_s=600,
                       client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_asset_signer_batches_per_bucket_and_builds_absolute_urls() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        paths = json.loads(request.content)["paths"]
        return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/doc-assets/{p}?token=abc",
                                          "error": None} for p in paths if p != "bad.png"]
                              + [{"path": "bad.png", "signedURL": None, "error": "not found"}])

    signer = _signer(handler)
    signed = asyncio.run(signer.sign([
        ChunkAsset(bucket="doc-assets", path="a.png", page=1),
        ChunkAsset(bucket="doc-assets", path="a.png", page=1),            # trùng đường dẫn: gửi một lần
        ChunkAsset(bucket="doc-assets", path="bad.png", page=2),
    ]))
    assert len(seen) == 1 and seen[0].url.path == "/storage/v1/object/sign/doc-assets"
    assert json.loads(seen[0].content) == {"expiresIn": 600, "paths": ["a.png", "bad.png"]}
    assert seen[0].headers["authorization"] == "Bearer service-secret"
    assert signed == {("doc-assets", "a.png"):
                      "https://proj.supabase.co/storage/v1/object/sign/doc-assets/a.png?token=abc"}


def test_asset_signer_returns_nothing_on_http_error_and_never_logs_the_key(caplog) -> None:
    signer = _signer(lambda request: httpx.Response(500, text="boom"))
    with caplog.at_level("WARNING"):
        assert asyncio.run(signer.sign([ChunkAsset(bucket="doc-assets", path="a.png", page=1)])) == {}
    assert "asset signing failed" in caplog.text and "service-secret" not in caplog.text


def test_asset_signer_is_off_unless_flag_and_credentials_are_set() -> None:
    def make(**kw) -> Settings:
        return Settings(_env_file=None, **kw)

    assert AssetSigner.from_settings(make()) is None
    assert AssetSigner.from_settings(make(CHAT_SOURCES_ENABLED=True)) is None
    assert AssetSigner.from_settings(make(CHAT_SOURCES_ENABLED=True, SUPABASE_URL="https://p.supabase.co")) is None
    assert AssetSigner.from_settings(make(SUPABASE_URL="https://p.supabase.co", SUPABASE_SERVICE_ROLE_KEY="k")) is None
    on = AssetSigner.from_settings(make(CHAT_SOURCES_ENABLED=True, SUPABASE_URL="https://p.supabase.co",
                                        SUPABASE_SERVICE_ROLE_KEY="k"))
    assert on is not None
    assert "role-key-xyz" not in repr(make(SUPABASE_SERVICE_ROLE_KEY="role-key-xyz"))   # khóa không lọt vào repr/log


def _agent_service(signer, answer_text: str) -> ChatbotService:
    provider = ScriptedToolProvider(
        turns=[calls(ask("c1", "Hướng dẫn lắp đặt F86")), answer(answer_text)],
        analysis_outputs=[analysis_output(sub_query("Hướng dẫn lắp đặt F86", "guide.installation", ["F86"]))],
    )
    with_image = chunk(1, vector=0.7).model_copy(update={"assets": [_asset(1)]})
    chunks = FakeChunks({("technical_docs", ("F86",)): [with_image, chunk(2)]})
    runner = agent_runner(provider, docs_registry(provider, chunks))
    return ChatbotService(provider, StoringHistoryRepository(), agent_runner=runner,
                          asset_signer=signer, source_images_max=3)


def _events(service: ChatbotService) -> list[str]:
    request = Request({"type": "http", "method": "POST", "path": "/chat/crm", "headers": [], "state": {}})
    inbound = make_inbound("Hướng dẫn lắp đặt F86", session_id=SESSION_ID, channel=ChannelType.CRM)

    async def collect():
        response = stream_chat(request, service, inbound, make_service_principal(),
                               make_request_context(ChannelType.CRM))
        return [event async for event in response.body_iterator]

    return asyncio.run(collect())


def test_sse_emits_sources_with_images_before_done() -> None:
    events = _events(_agent_service(FakeSigner(), "Lắp theo các bước [S1]."))
    names = [e.split("\n", 1)[0] for e in events]
    assert names == ["event: delta", "event: sources", "event: done"]
    payload = json.loads(events[1].split("data: ", 1)[1])
    [item] = payload["items"]
    assert item["source_id"] == "S1" and item["doc_id"] == "f86_installation"
    assert item["images"] == [{"url": "https://signed.example/f86/e1.png?token=t", "page": 1, "printed_page": 2}]


def test_sse_has_no_sources_event_when_disabled_or_uncited() -> None:
    off = [e.split("\n", 1)[0] for e in _events(_agent_service(None, "Lắp theo các bước [S1]."))]
    assert off == ["event: delta", "event: done"]                          # tính năng tắt: giữ nguyên hành vi cũ
    uncited = [e.split("\n", 1)[0] for e in _events(_agent_service(FakeSigner(), "Lắp theo các bước."))]
    assert uncited == ["event: delta", "event: done"]

# --- WU-17 đợt 2: history_id trong done, snapshot lưu độ khớp + tham chiếu ảnh, ký lại ảnh khi đọc ---


def _events_and_rows(service: ChatbotService, message_id: str):
    request = Request({"type": "http", "method": "POST", "path": "/chat/crm", "headers": [], "state": {}})
    inbound = make_inbound("Hướng dẫn lắp đặt F86", session_id=SESSION_ID, channel=ChannelType.CRM,
                           message_id=message_id)

    async def collect():
        response = stream_chat(request, service, inbound, make_service_principal(),
                               make_request_context(ChannelType.CRM))
        return [event async for event in response.body_iterator]

    return asyncio.run(collect())


def test_done_has_history_id_and_snapshot_keeps_similarity_and_asset_refs_not_urls() -> None:
    message_id = "00000000-0000-0000-0000-0000000000e1"
    service = _agent_service(FakeSigner(), "Lắp theo các bước [S1].")
    events = _events_and_rows(service, message_id)
    done = json.loads(events[-1].split("data: ", 1)[1])
    assert done["history_id"] == message_id and done["session_id"] == str(SESSION_ID)
    [row] = service._history_repository.rows
    first = row.retrieval_snapshot["chunks"][0]
    assert first["source_id"] == "S1" and first["similarity"] == 0.7
    assert first["assets"] == [{"bucket": "doc-assets", "path": "f86/e1.png", "page": 1, "printed_page": 2}]
    assert "signed.example" not in json.dumps(row.retrieval_snapshot)      # không lưu URL ký


def _row(answer_text: str, chunks: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), answer=answer_text, retrieval_snapshot={"chunks": chunks})


def _saved_chunk(source_id: str, assets: list[dict] | None = None, **extra) -> dict:
    return {"rank": 1, "score": 0.03, "content": "x", "source_id": source_id, "section_title": f"Mục {source_id}",
            "doc_id": "f54_installation", "page_start": 7, "page_end": 8, "assets": assets or [], **extra}


def test_attach_history_sources_rebuilds_cited_sources_and_signs_once_for_all_turns() -> None:
    img = {"bucket": "doc-assets", "path": "f54/p7.png", "page": 7, "printed_page": None}
    rows = [
        _row("Đấu dây theo [S2].", [_saved_chunk("S1"), _saved_chunk("S2", [img])]),
        _row("Không trích dẫn.", [_saved_chunk("S1", [img])]),
        _row("Lượt cũ [S1].", [{"rank": 1, "score": 0.03, "content": "x"}]),       # trước W1: không có source_id
    ]
    items = [ChatHistoryItem(id=r.id, session_id=SESSION_ID, query_origin="q", answer=r.answer, status="completed",
                             created_at=datetime(2026, 11, 25, tzinfo=UTC), updated_date=datetime(2026, 11, 25, tzinfo=UTC),
                             channel="website") for r in rows]
    signer = FakeSigner()
    out = asyncio.run(attach_history_sources(items, rows, signer, max_images=3))
    assert len(signer.requested) == 1                                     # một lần ký cho cả trang
    [source] = out[0].cited_sources
    assert (source.source_id, source.title, source.pages) == ("S2", "Mục S2", "7-8")
    assert source.images[0].url == "https://signed.example/f54/p7.png?token=t"
    assert out[1].cited_sources == [] and out[2].cited_sources == []
    # Tính năng tắt (không có signer): vẫn có tiêu đề/trang để hiện chú thích, không có ảnh.
    [plain] = asyncio.run(attach_history_sources(items, rows, None))[0].cited_sources
    assert plain.images == []


def test_retrieval_view_exposes_similarity_error_and_fresh_images() -> None:
    img = {"bucket": "doc-assets", "path": "f54/p7.png", "page": 7}
    row = SimpleNamespace(
        id=uuid4(), query_origin="q", model=None, total_tokens=0, status="completed",
        retrieval_snapshot={"chunks": [_saved_chunk("S1", [img], similarity=0.74), _saved_chunk("S2")],
                            "error": {"stage": "analysis", "code": "analysis_failed",
                                      "provider_code": "invalid_api_key", "http_status": 401}},
    )
    view = retrieval_view(SESSION_ID, row)
    assert view.chunks[0].similarity == 0.74 and view.chunks[1].similarity is None
    assert view.error is not None and view.error.provider_code == "invalid_api_key"
    signed = asyncio.run(attach_chunk_images(view, row, FakeSigner()))
    assert [len(c.images) for c in signed.chunks] == [1, 0]
    assert asyncio.run(attach_chunk_images(view, row, None)).chunks[0].images == []


class _ProviderError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Incorrect API key provided: sk-secret")
        self.code = "invalid_api_key"
        self.status_code = 401


def test_turn_error_keeps_only_identifiers_from_the_cause_chain() -> None:
    try:
        try:
            raise _ProviderError()
        except _ProviderError as cause:
            raise AnalysisError("analysis_failed", "Analysis failed: Incorrect API key sk-secret") from cause
    except AnalysisError as error:
        info = turn_error(error)
    assert info == {"stage": "analysis", "code": "analysis_failed", "provider_code": "invalid_api_key",
                    "http_status": 401}
    assert "sk-secret" not in json.dumps(info)
    assert turn_error(ValueError("boom")) == {"stage": None, "code": "value_error", "provider_code": None,
                                              "http_status": None}
