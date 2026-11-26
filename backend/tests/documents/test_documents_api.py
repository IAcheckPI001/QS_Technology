"""B6 phần đọc: API /workspace/documents, đồng bộ sổ nguồn CRM vào crm_documents (2026-11-26)."""

import asyncio

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import build_api_router
from app.core.config import Settings
from app.modules.chatbot.dependencies import get_asset_signer
from app.modules.chatbot.schemas.system import ChunkAsset
from app.modules.chunking_loader.sync_crm_documents import build_rows, changes, upsert_sql
from app.modules.documents import service
from app.modules.documents.crm_tree import CrmDocumentTree
from app.modules.documents.repository import ChunkStats
from app.modules.documents.router import get_crm_tree, get_document_repository, router

DOCS = [
    {"crm_id": "c-f54-op", "doc_id": "f54-operation-en", "name": "F54 - Operation Guide", "branch": "Bộ điều khiển",
     "folder": "F54", "model": "F54", "document_type": "operation", "language": "en", "connection_types": ["Pulse Train"],
     "version": "1.0", "file_size": 8332391, "sync_mode": "build", "sync_state": "fetched",
     "crm_updated_at": "2026-10-29T03:58:14Z", "on_crm": True, "last_seen_at": "2026-11-26T08:00:00Z", "sort_order": 1},
    {"crm_id": "c-f86-op", "doc_id": "f86-operation-en", "name": "F86 - Operation Guide", "branch": "Bộ điều khiển",
     "folder": "F86", "model": "F86", "document_type": "operation", "language": "en", "connection_types": [],
     "version": "1.0", "file_size": 1, "sync_mode": "build", "sync_state": "fetched", "crm_updated_at": None,
     "on_crm": True, "last_seen_at": "2026-11-26T08:00:00Z", "sort_order": 2},
    {"crm_id": "c-servo", "doc_id": None, "name": "SDV3 manual", "branch": "QS Servo", "folder": "SDV3",
     "model": None, "document_type": None, "language": "en", "connection_types": [], "version": "1", "file_size": 2,
     "sync_mode": "none", "sync_state": None, "crm_updated_at": None, "on_crm": True,
     "last_seen_at": "2026-11-26T09:00:00Z", "sort_order": 1},
]
CHUNK = {"id": 7, "chunk_key": "B0016", "chunk_index": 16, "chunk_type": "figure",
         "section_path": ["PART 2: WIRING", "2.3 Input"], "section_title": "2.3 Input", "page_start": 17, "page_end": 17,
         "printed_page_start": 10, "printed_page_end": 10, "content": "Figure 12.", "summary_vi": "Sơ đồ",
         "keywords": ["X40"], "review_status": "draft",
         "assets": [{"bucket": "doc-assets", "path": "f54/p17.png", "page": 17, "printed_page": 10}]}


class FakeRepository:
    def __init__(self):
        self.chunk_calls = []

    async def documents(self):
        return DOCS

    async def document(self, doc_id):
        return next((d for d in DOCS if d["doc_id"] == doc_id), None)

    async def stats(self, doc_ids):
        data = {"f54-operation-en": ChunkStats(chunks=243, approved=3, doc_title="F54 Operation", doc_version="1.0",
                                               page_count=170, image_chunks=80),
                "f86-operation-en": ChunkStats(chunks=10, approved=10, doc_version="1.0")}
        return {d: data[d] for d in doc_ids if d in data}

    async def section_paths(self, doc_id, doc_version):
        return [(["PART 2: WIRING", "2.3 Input", "2.3.1 Sensor"], 2), (["PART 2: WIRING", "2.4 Output"], 1),
                (["4.11 Wi-Fi", "4.11.3 Transfer"], 4)]

    async def chunks(self, doc_id, doc_version, **kwargs):
        self.chunk_calls.append(kwargs)
        return 1, [CHUNK]


class FakeSigner:
    async def sign(self, assets):
        return {(a.bucket, a.path): f"https://signed/{a.path}" for a in assets}


def _client(repo=None, tree=None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_document_repository] = lambda: repo or FakeRepository()
    app.dependency_overrides[get_asset_signer] = lambda: FakeSigner()
    if tree is not None:
        app.dependency_overrides[get_crm_tree] = lambda: tree
    return TestClient(app)


def test_tree_groups_by_branch_and_folder_with_plain_status() -> None:
    body = _client().get("/workspace/documents").json()
    assert [b["name"] for b in body["branches"]] == ["Bộ điều khiển", "QS Servo"]   # nhánh chatbot dùng lên đầu
    controllers = body["branches"][0]
    assert controllers["used_by_chatbot"] is True and controllers["document_count"] == 2
    f54 = controllers["folders"][0]["documents"][0]
    assert (f54["status"], f54["chunk_count"], f54["approved_count"], f54["pending_count"]) == ("review", 243, 3, 240)
    assert controllers["folders"][1]["documents"][0]["status"] == "live"
    servo = body["branches"][1]
    assert servo["used_by_chatbot"] is False and servo["folders"][0]["documents"][0]["status"] == "idle"
    assert body["document_count"] == 3 and body["synced_at"] == "2026-11-26T09:00:00Z"


def test_detail_outline_and_unknown_document() -> None:
    client = _client()
    detail = client.get("/workspace/documents/f54-operation-en").json()
    assert detail["doc_version"] == "1.0" and detail["page_count"] == 170 and detail["folder"] == "F54"
    outline = client.get("/workspace/documents/f54-operation-en/outline").json()
    assert outline["total"] == 7
    part2, unknown = outline["nodes"]
    assert (part2["title"], part2["chunk_count"]) == ("PART 2: WIRING", 3)
    assert [c["title"] for c in part2["children"]] == ["2.3 Input", "2.4 Output"]
    assert unknown["title"] == service.UNKNOWN_SECTION and unknown["children"][0]["title"] == "4.11 Wi-Fi"
    missing = client.get("/workspace/documents/nope")
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "document_not_found"


def test_chunks_page_passes_filters_and_signs_images() -> None:
    repo = FakeRepository()
    response = _client(repo).get("/workspace/documents/f54-operation-en/chunks",
                                 params={"offset": 20, "limit": 10, "status": "draft", "has_images": "true",
                                         "q": " homing ", "section": ["PART 2: WIRING", "2.3 Input"]})
    body = response.json()
    assert body["total"] == 1 and body["offset"] == 20
    item = body["items"][0]
    assert item["images"] == [{"url": "https://signed/f54/p17.png", "page": 17, "printed_page": 10}]
    assert item["image_count"] == 1 and "assets" not in item
    assert repo.chunk_calls == [{"offset": 20, "limit": 10, "status": "draft", "has_images": True, "q": "homing",
                                 "section": ["PART 2: WIRING", "2.3 Input"]}]
    assert _client(repo).get("/workspace/documents/f54-operation-en/chunks", params={"limit": 500}).status_code == 422


def test_pdf_redirects_to_fresh_crm_link_and_reports_crm_errors() -> None:
    signed = "/api/v1/public/company-docs/c-f54-op/view-pdf?exp=1&sig=abc"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"children": [{"node_type": "folder", "name": "Bộ điều khiển", "children": [
            {"node_type": "document", "id": "c-f54-op", "view_pdf_url": signed,
             "download_pdf_url": "/api/v1/public/company-docs/c-f54-op/download-pdf?exp=1&sig=abc"}]}]})

    tree = CrmDocumentTree("https://crm/tree", "https://crm", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    client = _client(tree=tree)
    response = client.get("/workspace/documents/f54-operation-en/pdf", follow_redirects=False)
    assert response.status_code == 307 and response.headers["location"] == "https://crm" + signed
    assert client.get("/workspace/documents/f86-operation-en/pdf", follow_redirects=False).json()["detail"]["code"] == "pdf_not_found"

    down = CrmDocumentTree("https://crm/tree", "https://crm",
                           client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    failed = _client(tree=down).get("/workspace/documents/f54-operation-en/pdf", follow_redirects=False)
    assert failed.status_code == 502 and failed.json()["detail"]["code"] == "crm_unavailable"


def test_crm_tree_is_cached_between_clicks() -> None:
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"children": [{"node_type": "document", "id": "a", "view_pdf_url": "https://x/a"}]})

    tree = CrmDocumentTree("https://crm/tree", "https://crm", ttl_s=300,
                           client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def twice():
        return await tree.pdf_url("a", "view"), await tree.pdf_url("a", "view")

    assert asyncio.run(twice()) == ("https://x/a", "https://x/a") and len(calls) == 1


def test_routes_are_off_unless_flag_is_set() -> None:
    def make(**kw) -> TestClient:
        app = FastAPI()
        app.include_router(build_api_router(Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://u:p@h/x", **kw)))
        app.dependency_overrides[get_document_repository] = FakeRepository
        return TestClient(app)

    assert make().get("/workspace/documents").status_code == 404
    assert make(WORKSPACE_DOCUMENTS_API_ENABLED=True).get("/workspace/documents").status_code == 200


def test_sync_rows_merge_lock_and_tree_without_signed_urls() -> None:
    lock = {"documents": [
        {"crm_id": "c-f54-op", "doc_id": "f54-operation-en", "name": "F54 - Operation Guide", "branch": "Bộ điều khiển",
         "mode": "build", "model": "F54", "document_type": "operation", "language": "en", "connection_types": [],
         "version": "1.0", "file_size": 100, "sha256": "abc", "state": "fetched", "synced_at": "2026-11-19"},
        {"crm_id": "c-gone", "doc_id": "old-doc", "name": "Old", "branch": "Catalogue & Hồ sơ", "mode": "run_only",
         "version": "1", "file_size": 5}]}
    tree = {"children": [{"node_type": "folder", "name": "Bộ điều khiển", "children": [
        {"node_type": "folder", "name": "F54", "children": [
            {"node_type": "document", "id": "c-f54-op", "name": "F54 - Operation Guide", "version": "1.1",
             "file_size": 120, "language": "EN", "document_type": "operation", "sort_order": 2,
             "updated_at": "2026-11-20T00:00:00Z", "view_pdf_url": "/v?sig=s"}]}]},
        {"node_type": "folder", "name": "QS Servo", "children": [
            {"node_type": "document", "id": "c-servo", "name": "SDV3", "version": "1", "file_size": "7"}]}]}
    rows = {r.crm_id: r for r in build_rows(lock, tree, "2026-11-26T00:00:00+00:00")}
    f54 = rows["c-f54-op"]
    assert (f54.doc_id, f54.folder, f54.version, f54.sha256, f54.sync_mode, f54.language) == (
        "f54-operation-en", "F54", "1.1", "abc", "build", "en")
    assert rows["c-servo"].branch == "QS Servo" and rows["c-servo"].doc_id is None and rows["c-servo"].file_size == 7
    assert rows["c-gone"].last_seen_at is None
    assert "sig=" not in repr(list(rows.values()))
    notes = changes(list(rows.values()), lock)
    assert any("f54-operation-en" in n and "crm-plan" in n for n in notes)
    assert any("old-doc" in n and "không còn" in n for n in notes)
    assert "on conflict (crm_id) do update" in upsert_sql()


def test_chunk_items_without_signer_have_no_images() -> None:
    [item] = asyncio.run(service.chunk_items([CHUNK], None))
    assert item.images == [] and item.image_count == 1
    assert ChunkAsset.model_validate(CHUNK["assets"][0]).path == "f54/p17.png"
