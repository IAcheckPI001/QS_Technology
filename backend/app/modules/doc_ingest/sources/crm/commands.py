"""Lệnh crm-sync: `crm-plan` (so CRM với sổ nguồn), `crm-fetch` (tải PDF + manifest nháp), `crm-status`.

Offline: chỉ đọc API công khai, tải file và ghi file trong repo/`data/`; không ghi database.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from app.modules.doc_ingest.manifest import load_manifest
from app.modules.doc_ingest.schemas.manifest import CrmSource
from app.modules.doc_ingest.sources.crm.client import CrmError, Fetcher, fetch_tree, strip_query
from app.modules.doc_ingest.sources.crm.config import REPO_ROOT, CrmConfig, registry_models
from app.modules.doc_ingest.sources.crm.diff import ACTIONABLE, PlanItem, plan
from app.modules.doc_ingest.sources.crm.lock import LockEntry, load_lock, save_lock
from app.modules.doc_ingest.sources.crm.manifest_draft import draft_manifest, write_manifest
from app.modules.doc_ingest.sources.crm.tree import documents, sanitized_tree, select

STATUS_TEXT = {"new": "Mới", "updated": "Đổi phiên bản", "anomaly": "Bất thường (cần người kiểm)",
               "version_only": "Chỉ tăng version", "removed": "Bị gỡ khỏi CRM", "unchanged": "Không đổi",
               "skipped": "Bỏ qua"}


def _rel(path: Path, root: Path = REPO_ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _plan_md(items: list[PlanItem], api_url: str, at: str, out_of_scope: int) -> str:
    lines = [f"# crm-plan {at}", "", f"Nguồn: `{api_url}`", ""]
    for status in ("new", "updated", "anomaly", "version_only", "removed", "unchanged", "skipped"):
        group = [i for i in items if i.status == status]
        if not group:
            continue
        lines += [f"## {STATUS_TEXT[status]} ({len(group)})", "",
                  "| doc_id | Tài liệu CRM | Nhánh | Ngôn ngữ | Version (sổ → CRM) | Lý do |", "|---|---|---|---|---|---|"]
        for i in sorted(group, key=lambda x: (x.doc_id or "", x.name)):
            version = f"{i.locked_version or '—'} → {i.version or '—'}"
            lines.append(f"| {i.doc_id or '—'} | {i.name} | {i.branch} | {i.language or '—'} | {version} | {i.reason} |")
        lines.append("")
    lines.append(f"Ngoài phạm vi đồng bộ (nhánh không cấu hình): {out_of_scope} tài liệu.")
    return "\n".join(lines) + "\n"


def run_plan(config: CrmConfig, fetch: Fetcher, lock_path: Path, out_dir: Path) -> Path:
    tree = fetch_tree(fetch, config.api_url)
    docs = documents(tree)
    selection = select(docs, config, registry_models())
    items = plan(selection, docs, load_lock(lock_path, config.api_url))
    at = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out_dir / at
    out.mkdir(parents=True, exist_ok=True)
    (out / "tree.json").write_text(json.dumps(sanitized_tree(tree), ensure_ascii=False, indent=1), encoding="utf-8")
    payload = {"at": at, "api_url": config.api_url, "out_of_scope": selection.out_of_scope,
               "items": [asdict(i) for i in items]}
    (out / "plan.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "plan.md").write_text(_plan_md(items, config.api_url, at, selection.out_of_scope), encoding="utf-8")
    counts = {s: sum(1 for i in items if i.status == s) for s in STATUS_TEXT}
    print("crm-plan: " + ", ".join(f"{STATUS_TEXT[s].lower()} {n}" for s, n in counts.items() if n)
          + f"; ngoài phạm vi {selection.out_of_scope}")
    return out


def _load_plan(plan_dir: Path) -> list[PlanItem]:
    data = json.loads((plan_dir / "plan.json").read_text(encoding="utf-8"))
    return [PlanItem(**{**i, "connection_types": tuple(i.get("connection_types") or ())}) for i in data["items"]]


def run_fetch(config: CrmConfig, fetch: Fetcher, plan_dir: Path, *, lock_path: Path, sources_dir: Path,
              manifests_dir: Path, only: list[str] | None = None, profile: str | None = None,
              today: str | None = None) -> list[str]:
    """Tải PDF + sinh manifest cho các mục `new`/`updated` của plan. Trả danh sách lỗi (rỗng = đạt hết)."""
    today = today or date.today().isoformat()
    targets = [i for i in _load_plan(plan_dir) if i.status in ACTIONABLE and (not only or i.doc_id in only)]
    if only:
        missing = set(only) - {i.doc_id for i in targets}
        if missing:
            raise CrmError(f"không có trong mục cần tải của plan: {', '.join(sorted(missing))}")
    if not targets:
        print("crm-fetch: plan không có tài liệu mới/đổi phiên bản.")
        return []
    current = {d.crm_id: d for d in documents(fetch_tree(fetch, config.api_url))}   # URL đã ký còn hạn
    lock = load_lock(lock_path, config.api_url)
    errors: list[str] = []
    commands: list[str] = []
    for item in targets:
        doc = current.get(item.crm_id)
        label = f"{item.doc_id} ({item.name})"
        if doc is None:
            errors.append(f"{label}: không còn trong cây CRM; chạy lại crm-plan")
            continue
        if doc.version != item.version or doc.file_id != item.file_id:
            errors.append(f"{label}: CRM đã đổi sau lúc plan (version/mã file); chạy lại crm-plan")
            continue
        if not doc.download_pdf_url or doc.file_id is None:
            errors.append(f"{label}: thiếu download_pdf_url hoặc mã file")
            continue
        try:
            data = fetch(config.base_url.rstrip("/") + doc.download_pdf_url)
        except CrmError as exc:
            errors.append(f"{label}: {exc}")
            continue
        if not data.startswith(b"%PDF"):
            errors.append(f"{label}: file tải về không phải PDF (đầu file {data[:8]!r})")
            continue
        if doc.file_size is not None and len(data) != doc.file_size:
            errors.append(f"{label}: kích thước {len(data)} khác file_size {doc.file_size} của CRM")
            continue
        sha = hashlib.sha256(data).hexdigest()
        folder = sources_dir / str(item.doc_id) / (doc.version or doc.file_id)
        folder.mkdir(parents=True, exist_ok=True)
        pdf = folder / f"{doc.file_id}.pdf"
        pdf.write_bytes(data)
        source = CrmSource(crm_id=doc.crm_id, version=doc.version, file_id=doc.file_id, sha256=sha, synced_at=today)
        manifest_rel = None
        if item.mode == "build":
            path = manifests_dir / f"{item.doc_id}.yaml"
            existing = load_manifest(path) if path.is_file() else None
            manifest = draft_manifest(config, doc_id=str(item.doc_id), name=doc.name, model=str(item.model),
                                      document_type=str(item.document_type), language=str(doc.language),
                                      source=source, existing=existing)
            write_manifest(manifest, path, fresh=existing is None)
            manifest_rel = _rel(path)
        lock.upsert(LockEntry(
            crm_id=doc.crm_id, doc_id=str(item.doc_id), name=doc.name, branch=doc.branch,
            mode=item.mode or "build", model=item.model, document_type=doc.document_type, language=doc.language,  # type: ignore[arg-type]
            connection_types=list(doc.connection_types), version=doc.version, file_id=doc.file_id,
            file_size=doc.file_size, sha256=sha, state="fetched", pdf_path=_rel(pdf), manifest=manifest_rel,
            synced_at=today))
        save_lock(lock, lock_path)
        flags = "" if item.mode == "build" else " --no-build"
        commands.append(f'..\\.venv-ingest\\Scripts\\python.exe -m app.modules.doc_ingest.cli run --pdf "{pdf}" '
                        f"--doc-id {item.doc_id} --profile {profile or config.profile}{flags}")
        print(f"  tải {label}: {len(data):,} byte, sha256 {sha[:12]}…, {_rel(pdf)}")
    print(f"crm-fetch: tải {len(commands)}/{len(targets)} tài liệu; lỗi {len(errors)}")
    for error in errors:
        print(f"  LỖI {error}")
    if commands:
        print("Lệnh chạy pipeline (từ backend/):")
        for command in commands:
            print(f"  {command}")
    return errors


def run_status(config: CrmConfig, lock_path: Path, runs_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in load_lock(lock_path, config.api_url).documents:
        runs = sorted((p for p in (runs_dir / entry.doc_id).glob("*") if (p / "run_report.json").is_file()),
                      key=lambda p: p.name) if (runs_dir / entry.doc_id).is_dir() else []
        latest = runs[-1] if runs else None
        chunks_file = latest / "build" / "chunks.jsonl" if latest else None
        chunks = (sum(1 for line in chunks_file.read_text(encoding="utf-8").splitlines() if line.strip())
                  if chunks_file is not None and chunks_file.is_file() else None)
        rows.append({"doc_id": entry.doc_id, "version": entry.version, "state": entry.state,
                     "run": latest.name if latest else None, "chunks": chunks})
        print(f"  {entry.doc_id:28} v{entry.version:6} {entry.state:12} run={latest.name if latest else '—':20} "
              f"chunk={chunks if chunks is not None else '—'}")
    return rows


__all__ = ["run_fetch", "run_plan", "run_status", "strip_query"]
