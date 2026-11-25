"""`publish-assets` (D-014 giai đoạn B): kế hoạch, upload không ghi đè, sổ sha256, bucket phải private."""
from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from app.modules.doc_ingest import cli
from app.modules.doc_ingest.publish.assets import PublishError, StorageClient, plan_assets, publish, read_ledger

KEY = "service-role-secret-123"


def _run(tmp_path: Path, files: dict[str, bytes] | None = None) -> Path:
    run = tmp_path / "doc" / "run-1"
    (run / "build").mkdir(parents=True)
    files = {"normalized/images/a.png": b"AAAA", "normalized/images/b.png": b"BBBBBB"} if files is None else files
    for name, data in files.items():
        target = run / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def asset(element: str, local: str) -> dict[str, Any]:
        return {"bucket": "doc-assets", "path": f"doc/{element}.png", "page": 1, "printed_page": None,
                "element_id": element, "local_path": local}

    chunks = [
        {"chunk_key": "doc:B1", "assets": [asset("e1", "normalized/images/a.png")]},
        {"chunk_key": "doc:B2", "assets": [asset("e1", "normalized/images/a.png"), asset("e2", "normalized/images/b.png")]},
        {"chunk_key": "doc:B3", "assets": []},
    ]
    rows = [{"chunk_key": "doc:B1", "review_status": "approved"}, {"chunk_key": "doc:B2", "review_status": "draft"},
            {"chunk_key": "doc:B3", "review_status": "draft"}]
    (run / "build" / "chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks), encoding="utf-8")
    (run / "build" / "doc_chunks_v2.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return run


def test_plan_dedupes_assets_and_hashes_content(tmp_path: Path) -> None:
    plan = plan_assets(_run(tmp_path))
    assert [(e.path, e.size) for e in plan.entries] == [("doc/e1.png", 4), ("doc/e2.png", 6)]
    assert plan.entries[0].sha256 == hashlib.sha256(b"AAAA").hexdigest()
    assert plan.entries[0].chunk_keys == ["doc:B1", "doc:B2"] and plan.entries[0].content_type == "image/png"
    assert plan.problems == [] and plan.skipped_status == 0


def test_plan_status_approved_keeps_only_approved_chunks(tmp_path: Path) -> None:
    plan = plan_assets(_run(tmp_path), "approved")
    assert [e.path for e in plan.entries] == ["doc/e1.png"] and plan.skipped_status == 2


def test_plan_reports_unrendered_images_instead_of_guessing(tmp_path: Path) -> None:
    plan = plan_assets(_run(tmp_path, files={"normalized/images/a.png": b"AAAA"}))
    assert [e.path for e in plan.entries] == ["doc/e1.png"]
    assert len(plan.problems) == 1 and "doc:B2" in plan.problems[0] and "chưa render" in plan.problems[0]
    with pytest.raises(PublishError):
        plan_assets(tmp_path / "khong-co")


class _Response:
    def __init__(self, status: int, body: Any = b"") -> None:
        self.status = status
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class FakeStorage:
    """Giả Supabase Storage: bucket + object trong bộ nhớ; ghi lại mọi request."""

    def __init__(self, bucket: dict[str, Any] | None = None, objects: set[str] | None = None) -> None:
        self.bucket, self.objects, self.requests = bucket, objects or set(), []

    def __call__(self, request):
        self.requests.append(request)
        url, method = request.full_url, request.get_method()
        if method == "GET" and "/storage/v1/bucket/" in url:
            if self.bucket is None:
                raise _http(url, 404, {"error": "not_found"})
            return _Response(200, self.bucket)
        if method == "POST" and url.endswith("/storage/v1/bucket"):
            self.bucket = {**json.loads(request.data), "public": json.loads(request.data)["public"]}
            return _Response(200, {"name": self.bucket["name"]})
        path = url.split("/storage/v1/object/", 1)[1]
        if path in self.objects:
            raise _http(url, 400, {"error": "Duplicate", "message": "The resource already exists"})
        self.objects.add(path)
        return _Response(200, {"Key": path})


def _http(url: str, code: int, body: Any) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(json.dumps(body).encode()))  # type: ignore[arg-type]


def _client(storage: FakeStorage) -> StorageClient:
    return StorageClient("https://p.supabase.co/", KEY, opener=storage)


def test_publish_creates_private_bucket_uploads_once_and_writes_ledger(tmp_path: Path) -> None:
    run, storage = _run(tmp_path), FakeStorage()
    plan = plan_assets(run)
    counts = publish(run, plan, _client(storage))
    assert counts == {"uploaded": 2, "skipped": 0, "exists_unverified": 0, "bucket_created": 1}
    assert storage.bucket["public"] is False and storage.objects == {"doc-assets/doc/e1.png", "doc-assets/doc/e2.png"}
    uploads = [r for r in storage.requests if r.get_method() == "POST" and "/object/" in r.full_url]
    assert all(r.headers["X-upsert"] == "false" and r.headers["Content-type"] == "image/png" for r in uploads)
    assert all(r.headers["Authorization"] == f"Bearer {KEY}" for r in storage.requests)
    ledger = read_ledger(run)["items"]
    assert ledger["doc-assets/doc/e1.png"]["sha256"] == hashlib.sha256(b"AAAA").hexdigest()
    assert ledger["doc-assets/doc/e1.png"]["state"] == "published"
    assert KEY not in (run / "build" / "assets_published.json").read_text(encoding="utf-8")   # khóa không vào sổ


def test_publish_is_idempotent_and_never_overwrites_changed_content(tmp_path: Path) -> None:
    run, storage = _run(tmp_path), FakeStorage()
    publish(run, plan_assets(run), _client(storage))
    again = publish(run, plan_assets(run), _client(storage))
    assert again["uploaded"] == 0 and again["skipped"] == 2
    (run / "normalized/images/a.png").write_bytes(b"CHANGED")                  # cùng đường dẫn, nội dung khác
    with pytest.raises(PublishError, match="không ghi đè"):
        publish(run, plan_assets(run), _client(storage))


def test_publish_marks_existing_object_without_ledger_as_unverified(tmp_path: Path) -> None:
    run = _run(tmp_path)
    storage = FakeStorage(bucket={"id": "doc-assets", "public": False}, objects={"doc-assets/doc/e1.png"})
    counts = publish(run, plan_assets(run), _client(storage))
    assert counts["uploaded"] == 1 and counts["exists_unverified"] == 1 and counts["bucket_created"] == 0
    assert read_ledger(run)["items"]["doc-assets/doc/e1.png"]["state"] == "exists_unverified"


def test_publish_refuses_a_public_bucket(tmp_path: Path) -> None:
    run = _run(tmp_path)
    storage = FakeStorage(bucket={"id": "doc-assets", "public": True})
    with pytest.raises(PublishError, match="public"):
        publish(run, plan_assets(run), _client(storage))
    assert not [r for r in storage.requests if "/object/" in r.full_url]       # chưa upload gì


def test_cli_without_apply_makes_no_network_call(tmp_path: Path, capsys, monkeypatch) -> None:
    run = _run(tmp_path)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: pytest.fail("không được gọi mạng khi thiếu --apply"))
    assert cli.main(["publish-assets", "--run-dir", str(run)]) == 0
    out = capsys.readouterr().out
    assert "2 ảnh" in out and "Chưa đẩy gì" in out
    assert cli.main(["publish-assets", "--run-dir", str(run), "--apply"]) == 2   # thiếu biến môi trường
    assert "SUPABASE_SERVICE_ROLE_KEY" in capsys.readouterr().out
