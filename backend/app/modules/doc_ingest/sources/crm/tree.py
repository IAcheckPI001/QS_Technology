"""Đọc cây `company-docs/website-tree` của CRM và chọn tài liệu cần đồng bộ (hàm thuần, không gọi mạng).

Quy ước của CRM (Toma, 2026-11-19): khóa tài liệu là `id` (`root_id` thừa); cây chỉ trả bản hiện hành; upload
file mới → `version`, URL và mã file trong `file_url` đổi. URL đã ký (`exp`, `sig`) hết hạn theo ngày.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.modules.doc_ingest.sources.crm.config import CrmConfig

_VERSION = re.compile(r"^\d+(\.\d+)*$")
_FILE_ID = re.compile(r"/files/([^/?#]+?)(?:\.pdf)?(?:[?#]|$)", re.IGNORECASE)


def parse_version(value: object) -> tuple[int, ...] | None:
    """"1.0" → (1, 0); so theo số nên "1.10" > "1.9". Sai định dạng → None."""
    text = str(value).strip() if value is not None else ""
    if not _VERSION.match(text):
        return None
    parts = [int(p) for p in text.split(".")]
    while len(parts) > 1 and parts[-1] == 0:   # "1.0" == "1"
        parts.pop()
    return tuple(parts)


def file_id(file_url: str | None) -> str | None:
    match = _FILE_ID.search(file_url or "")
    return match.group(1) if match else None


@dataclass
class CrmDocument:
    """Một node `document` của cây, kèm thư mục cha (nhánh và thư mục model)."""

    crm_id: str
    name: str
    path: tuple[str, ...]                 # tên các thư mục từ dưới gốc "Website" tới thư mục chứa tài liệu
    version: str
    file_id: str | None
    file_size: int | None
    language: str | None
    document_type: str | None
    connection_types: list[str]
    updated_at: str | None
    download_pdf_url: str | None          # URL đã ký: chỉ dùng lúc tải, không lưu

    @property
    def branch(self) -> str:
        return self.path[0] if self.path else ""

    @property
    def folder(self) -> str:
        return self.path[-1] if self.path else ""


def _connection_types(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip():
        return [v.strip(" '\"") for v in value.strip("[]").split(",") if v.strip(" '\"")]
    return []


def documents(tree: dict[str, Any]) -> list[CrmDocument]:
    out: list[CrmDocument] = []

    def walk(node: dict[str, Any], path: tuple[str, ...]) -> None:
        if node.get("node_type") == "document":
            size = node.get("file_size")
            out.append(CrmDocument(
                crm_id=str(node["id"]), name=str(node.get("name") or ""), path=path,
                version=str(node.get("version") or ""), file_id=file_id(node.get("file_url")),
                file_size=int(size) if str(size or "").isdigit() else None,
                language=(str(node["language"]).lower() if node.get("language") else None),
                document_type=(str(node["document_type"]) if node.get("document_type") else None),
                connection_types=_connection_types(node.get("connection_types")),
                updated_at=node.get("updated_at"), download_pdf_url=node.get("download_pdf_url")))
            return
        for child in node.get("children") or []:
            walk(child, (*path, str(node.get("name") or "")) if node is not tree else path)

    walk(tree, ())
    return out


@dataclass
class Selected:
    doc: CrmDocument
    doc_id: str
    mode: str                              # build | run_only
    require_version: bool
    model: str | None = None
    doc_type_key: str | None = None


@dataclass
class Skipped:
    doc: CrmDocument
    reason: str


@dataclass
class Selection:
    selected: list[Selected] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    out_of_scope: int = 0                  # tài liệu thuộc nhánh không đồng bộ


def _model_rule(config: CrmConfig, doc: CrmDocument):
    prefix = doc.name.split(" - ", 1)[0].strip().lower()
    return next((r for r in config.models if r.prefix.lower() == prefix), None)


def select(docs: list[CrmDocument], config: CrmConfig, registry: set[str]) -> Selection:
    """Lọc nhánh, ánh xạ model và loại tài liệu, chọn một bản mỗi (model, loại) theo `language_priority`.

    Không chọn theo `document_group_id`: dữ liệu thật có bản Installation (vi) và Operation (en) của 6AVE chung group.
    """
    branches = {b.name: b for b in config.branches}
    result = Selection()
    candidates: dict[tuple[str, str], list[CrmDocument]] = {}
    for doc in docs:
        branch = branches.get(doc.branch)
        if branch is None:
            result.out_of_scope += 1
            continue
        if branch.mode == "run_only":
            doc_id = config.run_only_doc_ids.get(doc.name)
            if doc_id is None:
                result.skipped.append(Skipped(doc, "chưa có doc_id trong run_only_doc_ids"))
            else:
                result.selected.append(Selected(doc, doc_id, "run_only", branch.require_version))
            continue
        rule = _model_rule(config, doc)
        if rule is None:
            result.skipped.append(Skipped(doc, "không nhận ra model từ tên tài liệu"))
            continue
        if rule.folder != doc.folder:
            result.skipped.append(Skipped(doc, f"tên thư mục '{doc.folder}' khác cấu hình '{rule.folder}'"))
            continue
        if rule.model not in registry:
            result.skipped.append(Skipped(doc, f"model lạ với registry: {rule.model}"))
            continue
        if doc.document_type not in config.document_types:
            result.skipped.append(Skipped(doc, f"document_type chưa ánh xạ: {doc.document_type}"))
            continue
        candidates.setdefault((rule.model, doc.document_type), []).append(doc)

    priority = {lang: i for i, lang in enumerate(config.language_priority)}
    for (model, dtype), group in sorted(candidates.items()):
        group.sort(key=lambda d: (priority.get(d.language or "", len(priority)), d.name))
        chosen, rest = group[0], group[1:]
        if chosen.language not in priority:
            result.skipped.extend(Skipped(d, f"ngôn ngữ ngoài language_priority: {d.language}") for d in group)
            continue
        slug = config.document_types[dtype].slug
        result.selected.append(Selected(chosen, f"{model.lower()}-{slug}-{chosen.language}", "build",
                                        branches[chosen.branch].require_version, model, dtype))
        result.skipped.extend(Skipped(d, f"đã chọn bản {chosen.language} cùng loại ({chosen.name})") for d in rest)
    result.selected.sort(key=lambda s: s.doc_id)
    return result


def sanitized_tree(tree: dict[str, Any]) -> dict[str, Any]:
    """Bản sao cây bỏ query của mọi URL (chữ ký `exp`, `sig`) để lưu snapshot."""
    def clean(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: (v.split("?", 1)[0] if isinstance(v, str) and k.endswith("_url") else clean(v))
                    for k, v in node.items()}
        if isinstance(node, list):
            return [clean(v) for v in node]
        return node

    return clean(tree)
