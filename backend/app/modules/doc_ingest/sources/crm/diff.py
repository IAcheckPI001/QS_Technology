"""So tài liệu CRM hiện hành với sổ nguồn → việc cần làm (hàm thuần).

| version (nhánh có version) | mã file | Kết luận |
|---|---|---|
| chưa có trong sổ | — | new |
| tăng | đổi | updated |
| bằng | đổi | anomaly: thay file không tăng version → người kiểm, không tự xử lý |
| bằng | bằng | unchanged |
| tăng | bằng | version_only: chỉ cập nhật version trong sổ |
| giảm / sai định dạng | — | anomaly |
| có trong sổ, không còn trong cây | — | removed |

Nhánh không kiểm version (`require_version: false`): chỉ so mã file (đổi → updated).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.modules.doc_ingest.sources.crm.lock import LockEntry, SourceLock
from app.modules.doc_ingest.sources.crm.tree import CrmDocument, Selected, Selection, parse_version

Status = Literal["new", "updated", "unchanged", "version_only", "anomaly", "removed", "skipped"]
ACTIONABLE: frozenset[str] = frozenset({"new", "updated"})


@dataclass
class PlanItem:
    status: Status
    reason: str
    crm_id: str
    name: str
    branch: str
    doc_id: str | None = None
    mode: str | None = None
    model: str | None = None
    document_type: str | None = None
    language: str | None = None
    version: str | None = None
    file_id: str | None = None
    file_size: int | None = None
    connection_types: tuple[str, ...] = ()
    locked_version: str | None = None
    locked_file_id: str | None = None


def classify(sel: Selected, entry: LockEntry | None) -> tuple[Status, str]:
    doc = sel.doc
    if doc.file_id is None:
        return "anomaly", "không đọc được mã file từ file_url"
    new_version = parse_version(doc.version)
    if sel.require_version and new_version is None:
        return "anomaly", f"version sai định dạng: {doc.version!r}"
    if entry is None:
        return "new", "chưa có trong sổ nguồn"
    file_changed = doc.file_id != entry.file_id
    if not sel.require_version:
        return ("updated", "mã file đổi") if file_changed else ("unchanged", "mã file giữ nguyên")
    old_version = parse_version(entry.version)
    if old_version is None or new_version is None:
        return "anomaly", f"không so được version: sổ {entry.version!r}, CRM {doc.version!r}"
    if new_version > old_version:
        if file_changed:
            return "updated", f"version {entry.version} → {doc.version}"
        return "version_only", f"version {entry.version} → {doc.version} nhưng mã file giữ nguyên"
    if new_version < old_version:
        return "anomaly", f"version giảm {entry.version} → {doc.version}"
    if file_changed:
        return "anomaly", f"file đổi nhưng version giữ {doc.version} (thay file không tăng version)"
    return "unchanged", f"version {doc.version}, mã file giữ nguyên"


def _item(status: Status, reason: str, doc: CrmDocument, sel: Selected | None = None,
          entry: LockEntry | None = None) -> PlanItem:
    return PlanItem(
        status=status, reason=reason, crm_id=doc.crm_id, name=doc.name, branch=doc.branch,
        doc_id=sel.doc_id if sel else (entry.doc_id if entry else None), mode=sel.mode if sel else None,
        model=sel.model if sel else None, document_type=doc.document_type, language=doc.language,
        version=doc.version, file_id=doc.file_id, file_size=doc.file_size,
        connection_types=tuple(doc.connection_types),
        locked_version=entry.version if entry else None, locked_file_id=entry.file_id if entry else None)


def plan(selection: Selection, all_docs: list[CrmDocument], lock: SourceLock) -> list[PlanItem]:
    locked = lock.by_crm_id()
    items: list[PlanItem] = []
    for sel in selection.selected:
        status, reason = classify(sel, locked.get(sel.doc.crm_id))
        items.append(_item(status, reason, sel.doc, sel, locked.get(sel.doc.crm_id)))
    items.extend(_item("skipped", s.reason, s.doc, entry=locked.get(s.doc.crm_id)) for s in selection.skipped)
    in_tree = {d.crm_id for d in all_docs}
    for entry in lock.documents:
        if entry.crm_id not in in_tree and entry.state != "removed":
            items.append(PlanItem(status="removed", reason="không còn trong cây CRM", crm_id=entry.crm_id,
                                  name=entry.name, branch=entry.branch, doc_id=entry.doc_id, mode=entry.mode,
                                  model=entry.model, document_type=entry.document_type, language=entry.language,
                                  locked_version=entry.version, locked_file_id=entry.file_id))
    return items
