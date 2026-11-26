"""Đồng bộ danh mục tài liệu CRM vào bảng `crm_documents` (màn "Tài liệu & chunk", B6 phần đọc; chạy tay).

Nguồn:
- sổ `crm_sources.lock.json` của doc-ingest (tài liệu đã tải PDF để cắt đoạn: doc_id, model, sha256, trạng thái);
- `--tree`: cây `company-docs/website-tree` của CRM (mọi tài liệu, kể cả nhánh chưa đưa vào chatbot). Không có
  `--tree` thì chỉ cập nhật các dòng có trong sổ.

Không import `doc_ingest` (ranh giới tool offline): sổ và cây được đọc như JSON. Không lưu URL đã ký của CRM.
Ghi trong một transaction (upsert theo `crm_id`); tài liệu có trong bảng mà không còn trong cây → `on_crm = false`.

Chạy từ `backend/` (venv chính):
    .\\venv\\Scripts\\python.exe -m app.modules.chunking_loader.sync_crm_documents --tree --dry-run
    .\\venv\\Scripts\\python.exe -m app.modules.chunking_loader.sync_crm_documents --tree --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import selectors
import sys
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TABLE = "public.crm_documents"
DEFAULT_LOCK = Path(__file__).resolve().parents[1] / "doc_ingest" / "sources" / "crm" / "crm_sources.lock.json"
DEFAULT_TREE_URL = "https://erp.qstcnc.com/api/v1/public/company-docs/website-tree"
COLUMNS = ("crm_id", "doc_id", "name", "branch", "folder", "model", "document_type", "language", "connection_types",
           "version", "file_size", "sha256", "sync_mode", "sync_state", "synced_at", "crm_updated_at", "on_crm",
           "last_seen_at", "sort_order")


@dataclass
class DocRow:
    crm_id: str
    name: str
    branch: str
    folder: str | None = None
    doc_id: str | None = None
    model: str | None = None
    document_type: str | None = None
    language: str | None = None
    connection_types: list[str] = field(default_factory=list)
    version: str | None = None
    file_size: int | None = None
    sha256: str | None = None
    sync_mode: str = "none"
    sync_state: str | None = None
    synced_at: str | None = None
    crm_updated_at: str | None = None
    on_crm: bool = True
    last_seen_at: str | None = None
    sort_order: int | None = None

    def params(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in COLUMNS}


def _connection_types(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip():
        return [v.strip(" '\"") for v in value.strip("[]").split(",") if v.strip(" '\"")]
    return []


def tree_documents(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """Node `document` của cây kèm `path` (tên thư mục từ dưới gốc tới thư mục chứa tài liệu)."""
    out: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], path: tuple[str, ...]) -> None:
        if node.get("node_type") == "document":
            out.append({**node, "_path": path})
            return
        for child in node.get("children") or []:
            walk(child, (*path, str(node.get("name") or "")) if node is not tree else path)

    walk(tree, ())
    return out


def build_rows(lock: dict[str, Any], tree: dict[str, Any] | None, now: str) -> list[DocRow]:
    """Gộp sổ nguồn và cây CRM thành dòng bảng. Sổ quyết định doc_id/model/sha256; cây quyết định thư mục, phiên bản
    và `on_crm`. Không có cây: chỉ dòng của sổ, giữ `on_crm` mặc định."""
    rows: dict[str, DocRow] = {}
    for entry in lock.get("documents") or []:
        crm_id = str(entry["crm_id"])
        rows[crm_id] = DocRow(
            crm_id=crm_id, name=str(entry.get("name") or ""), branch=str(entry.get("branch") or ""),
            doc_id=entry.get("doc_id"), model=entry.get("model"), document_type=entry.get("document_type"),
            language=entry.get("language"), connection_types=_connection_types(entry.get("connection_types")),
            version=entry.get("version"), file_size=entry.get("file_size"), sha256=entry.get("sha256"),
            sync_mode=entry.get("mode") if entry.get("mode") in ("build", "run_only") else "none",
            sync_state=entry.get("state"), synced_at=entry.get("synced_at"))
    if tree is None:
        return list(rows.values())
    for node in tree_documents(tree):
        crm_id = str(node["id"])
        path = node["_path"]
        row = rows.get(crm_id) or DocRow(crm_id=crm_id, name=str(node.get("name") or ""), branch=path[0] if path else "")
        size = node.get("file_size")
        row.name = str(node.get("name") or row.name)
        row.branch = path[0] if path else row.branch
        row.folder = path[-1] if len(path) > 1 else None
        row.document_type = node.get("document_type") or row.document_type
        row.language = (str(node["language"]).lower() if node.get("language") else row.language)
        row.connection_types = _connection_types(node.get("connection_types")) or row.connection_types
        row.crm_updated_at = node.get("updated_at")
        row.sort_order = node.get("sort_order") if isinstance(node.get("sort_order"), int) else None
        row.on_crm, row.last_seen_at = True, now
        # Phiên bản/kích thước theo CRM hiện tại; sha256 vẫn là của bản đã tải (lệch → cần tải lại).
        row.version = str(node.get("version") or "") or row.version
        row.file_size = int(size) if str(size or "").isdigit() else row.file_size
        rows[crm_id] = row
    return sorted(rows.values(), key=lambda r: (r.branch, r.folder or "", r.sort_order or 0, r.name))


def changes(rows: Sequence[DocRow], lock: dict[str, Any]) -> list[str]:
    """Cảnh báo cho người chạy: sổ khác CRM (phiên bản/kích thước) nghĩa là cần crm-plan/crm-fetch lại."""
    by_id = {str(e["crm_id"]): e for e in lock.get("documents") or []}
    notes = []
    for row in rows:
        entry = by_id.get(row.crm_id)
        if entry is None or not row.last_seen_at:
            continue
        if str(entry.get("version")) != str(row.version) or entry.get("file_size") != row.file_size:
            notes.append(f"{row.doc_id or row.name}: sổ {entry.get('version')}/{entry.get('file_size')} ≠ CRM "
                         f"{row.version}/{row.file_size} → chạy lại crm-plan, crm-fetch")
    missing = set(by_id) - {r.crm_id for r in rows if r.last_seen_at}
    if any(r.last_seen_at for r in rows):
        notes += [f"{by_id[m].get('doc_id')}: không còn trong cây CRM" for m in sorted(missing)]
    return notes


def upsert_sql() -> str:
    cols = ", ".join(COLUMNS)
    values = ", ".join(
        f"cast(:{c} as {'uuid' if c == 'crm_id' else 'text[]' if c == 'connection_types' else 'date' if c == 'synced_at' else 'timestamptz' if c in ('crm_updated_at', 'last_seen_at') else 'bigint' if c == 'file_size' else 'int' if c == 'sort_order' else 'boolean' if c == 'on_crm' else 'text'})"
        for c in COLUMNS)
    updates = ", ".join(f"{c} = excluded.{c}" for c in COLUMNS if c != "crm_id")
    return (f"insert into {TABLE} ({cols}) values ({values}) "
            f"on conflict (crm_id) do update set {updates}, updated_at = now()")


async def apply(rows: Sequence[DocRow], with_tree: bool) -> tuple[int, int]:
    from sqlalchemy import text

    from app.db.engine import AsyncSessionFactory, engine

    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                statement = text(upsert_sql())
                for row in rows:
                    await session.execute(statement, row.params())
                gone = 0
                if with_tree:
                    result = await session.execute(
                        text(f"update {TABLE} set on_crm = false, updated_at = now() "
                             "where on_crm and not (crm_id = any(cast(:ids as uuid[])))"),
                        {"ids": [r.crm_id for r in rows if r.last_seen_at]})
                    gone = result.rowcount or 0
                return len(rows), gone
    finally:
        await engine.dispose()


def fetch_tree(url: str, timeout_s: float = 60.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "qs-workspace/crm-documents", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:   # noqa: S310 - URL cấu hình, API công khai
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict) or "children" not in data:
        raise RuntimeError("cây tài liệu CRM không đúng dạng (thiếu `children`)")
    return data


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Đồng bộ sổ nguồn CRM (+ cây CRM) vào bảng crm_documents")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="chỉ in kết quả, không ghi DB")
    mode.add_argument("--apply", action="store_true", help="ghi vào bảng crm_documents (upsert)")
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK, help="mặc định: sổ nguồn của doc-ingest")
    parser.add_argument("--tree", action="store_true", help="đọc thêm cây CRM (mọi tài liệu, đánh dấu tài liệu đã gỡ)")
    parser.add_argument("--tree-url", default=DEFAULT_TREE_URL)
    args = parser.parse_args(argv)

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    tree = fetch_tree(args.tree_url) if args.tree else None
    now = datetime.now(UTC).isoformat(timespec="seconds")
    rows = build_rows(lock, tree, now)
    by_branch: dict[str, int] = {}
    for row in rows:
        by_branch[row.branch] = by_branch.get(row.branch, 0) + 1
    print(f"{len(rows)} tài liệu ({len(lock.get('documents') or [])} trong sổ nguồn, "
          f"{sum(1 for r in rows if r.doc_id)} có doc_id): " + ", ".join(f"{b} {n}" for b, n in by_branch.items()))
    for note in changes(rows, lock):
        print("  ! " + note)
    if args.dry_run:
        for row in rows:
            print(f"  {row.branch} › {row.folder or '-'} › {row.name} · {row.version} · {row.doc_id or '(chưa dùng)'}")
        print("Chưa ghi gì (--dry-run).")
        return 0
    written, gone = asyncio.run(
        apply(rows, args.tree),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    print(f"Đã ghi {written} dòng vào {TABLE}; đánh dấu {gone} tài liệu không còn trên CRM.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
