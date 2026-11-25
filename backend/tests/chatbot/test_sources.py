"""D-014 giai đoạn B: nguồn đã trích dẫn kèm ảnh (URL ký) và event SSE `sources`."""

import asyncio
import json
from uuid import UUID

import httpx
from starlette.requests import Request

from app.core.config import Settings
from app.modules.chatbot.providers.supabase_storage import AssetSigner
from app.modules.chatbot.routers.sse import stream_chat
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.system import ChunkAsset, ChunkHit
from app.modules.chatbot.services import ChatbotService
from app.modules.chatbot.sources import build_sources, cited_source_ids
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
