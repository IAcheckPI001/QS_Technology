"""`publish-assets`: đẩy ảnh của chunk lên Supabase Storage (bucket private, D-014 giai đoạn B).

Đọc `build/chunks.jsonl` (có `local_path`) và `build/doc_chunks_v2.jsonl` (có `review_status`) của một run, tải từng ảnh
lên `bucket/path` đã ghi trong chunk, ghi sổ `build/assets_published.json` (sha256, kích thước). Không ghi đè: đường dẫn
đã có nội dung khác thì dừng và báo (đổi `doc_version`). Chỉ dùng stdlib (venv ingest không có httpx). Khóa service role
lấy từ biến môi trường, không ghi log, không nằm trong sổ. Mặc định chỉ lập kế hoạch; `--apply` mới gọi mạng.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_NAME = "assets_published.json"
Opener = Callable[[urllib.request.Request], Any]


class PublishError(RuntimeError):
    pass


@dataclass
class AssetEntry:
    bucket: str
    path: str
    file: Path
    size: int
    sha256: str
    content_type: str
    chunk_keys: list[str] = field(default_factory=list)


@dataclass
class Plan:
    entries: list[AssetEntry]
    problems: list[str]
    skipped_status: int = 0        # asset của chunk bị loại theo --status


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def plan_assets(run_dir: Path, status: str = "all") -> Plan:
    """Ảnh cần đẩy lên của run. `status`: `all` (cả draft, để thử nghiệm) hoặc `approved` (chỉ chunk đã duyệt)."""
    build = run_dir / "build"
    chunks_file, rows_file = build / "chunks.jsonl", build / "doc_chunks_v2.jsonl"
    if not chunks_file.is_file() or not rows_file.is_file():
        raise PublishError(f"thiếu chunks.jsonl hoặc doc_chunks_v2.jsonl trong {build} (chạy `build` trước)")
    statuses = {row["chunk_key"]: row["review_status"] for row in _read_jsonl(rows_file)}
    entries: dict[tuple[str, str], AssetEntry] = {}
    problems: list[str] = []
    skipped = 0
    for chunk in _read_jsonl(chunks_file):
        key = chunk["chunk_key"]
        for asset in chunk.get("assets", []):
            if status == "approved" and statuses.get(key) != "approved":
                skipped += 1
                continue
            ident = (asset["bucket"], asset["path"])
            local = asset.get("local_path")
            file = (run_dir / local) if local else None
            if file is None or not file.is_file():
                problems.append(f"{key}: ảnh {asset['path']} chưa render ({local or 'không có local_path'}); "
                                f"chạy lại `run --raw-dir … --pdf …` để render ảnh")
                continue
            if ident in entries:
                entries[ident].chunk_keys.append(key)
                continue
            data = file.read_bytes()
            entries[ident] = AssetEntry(
                bucket=asset["bucket"], path=asset["path"], file=file, size=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                content_type=mimetypes.guess_type(file.name)[0] or "application/octet-stream", chunk_keys=[key])
    return Plan(sorted(entries.values(), key=lambda e: (e.bucket, e.path)), problems, skipped)


class StorageClient:
    """Supabase Storage REST (`/storage/v1`): kiểm/tạo bucket private và upload không ghi đè."""

    def __init__(self, base_url: str, service_key: str, opener: Opener | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {service_key}", "apikey": service_key}
        self._open = opener or (lambda request: urllib.request.urlopen(request, timeout=60))

    def _call(self, method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, Any]:
        request = urllib.request.Request(url, data=data, method=method, headers={**self._headers, **(headers or {})})
        try:
            with self._open(request) as response:
                body = response.read()
                return response.status, (json.loads(body) if body[:1] in (b"{", b"[") else body.decode("utf-8", "replace"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            try:
                return error.code, json.loads(body)
            except ValueError:
                return error.code, body
        except urllib.error.URLError as error:
            raise PublishError(f"không kết nối được Storage: {error.reason}") from None

    def ensure_private_bucket(self, bucket: str) -> str:
        """Trả `exists` hoặc `created`. Bucket đang public → từ chối (ảnh nội bộ không được lộ)."""
        status, body = self._call("GET", f"{self._base}/storage/v1/bucket/{urllib.parse.quote(bucket)}")
        if status == 200:
            if isinstance(body, dict) and body.get("public"):
                raise PublishError(f"bucket '{bucket}' đang public: đặt private trước khi đẩy ảnh (D-014)")
            return "exists"
        if status not in (400, 404):
            raise PublishError(f"kiểm bucket '{bucket}' lỗi HTTP {status}")
        payload = json.dumps({"id": bucket, "name": bucket, "public": False}).encode()
        status, _ = self._call("POST", f"{self._base}/storage/v1/bucket", payload, {"Content-Type": "application/json"})
        if status not in (200, 201):
            raise PublishError(f"tạo bucket '{bucket}' lỗi HTTP {status}")
        return "created"

    def upload(self, entry: AssetEntry) -> str:
        """`uploaded` hoặc `exists` (đường dẫn đã có; không ghi đè). Lỗi khác ném PublishError."""
        url = (f"{self._base}/storage/v1/object/{urllib.parse.quote(entry.bucket)}/"
               f"{urllib.parse.quote(entry.path, safe='/')}")
        status, body = self._call("POST", url, entry.file.read_bytes(),
                                  {"Content-Type": entry.content_type, "x-upsert": "false", "cache-control": "3600"})
        if status in (200, 201):
            return "uploaded"
        text = json.dumps(body) if not isinstance(body, str) else body
        if status in (400, 409) and ("Duplicate" in text or "already exists" in text):
            return "exists"
        raise PublishError(f"upload {entry.path} lỗi HTTP {status}")


def read_ledger(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "build" / LEDGER_NAME
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"items": {}}


def write_ledger(run_dir: Path, ledger: dict[str, Any]) -> Path:
    path = run_dir / "build" / LEDGER_NAME
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def publish(run_dir: Path, plan: Plan, client: StorageClient, *, now: datetime | None = None) -> dict[str, int]:
    """Đẩy ảnh theo kế hoạch; cập nhật sổ sau mỗi ảnh (chạy lại được, ảnh đã đẩy không đẩy lại)."""
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    ledger = read_ledger(run_dir)
    items: dict[str, Any] = ledger.setdefault("items", {})
    counts = {"uploaded": 0, "skipped": 0, "exists_unverified": 0, "bucket_created": 0}
    for bucket in sorted({e.bucket for e in plan.entries}):
        counts["bucket_created"] += client.ensure_private_bucket(bucket) == "created"
    for entry in plan.entries:
        key = f"{entry.bucket}/{entry.path}"
        known = items.get(key)
        if known and known["sha256"] == entry.sha256:
            counts["skipped"] += 1
            continue
        if known:
            raise PublishError(f"{key} đã đẩy với nội dung khác (sha256 {known['sha256'][:12]} ≠ {entry.sha256[:12]}): "
                               f"không ghi đè; đổi doc_version hoặc xoá thủ công trên Storage")
        result = client.upload(entry)
        # `exists` mà sổ không có: không biết nội dung đang là gì → ghi rõ chưa kiểm chứng
        state = "published" if result == "uploaded" else "exists_unverified"
        items[key] = {"sha256": entry.sha256, "size": entry.size, "content_type": entry.content_type,
                      "state": state, "published_at": stamp, "chunk_keys": entry.chunk_keys}
        counts["uploaded" if result == "uploaded" else "exists_unverified"] += 1
        write_ledger(run_dir, ledger)
    write_ledger(run_dir, ledger)
    return counts
