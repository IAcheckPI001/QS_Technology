"""Sinh manifest nháp (`manifests/<doc_id>.yaml`) từ metadata CRM; người kiểm các dòng TODO trước khi build thật.

Nếu manifest đã có (lần đồng bộ trước, người đã sửa), giữ các trường người điền (`exclude_*`, `scope_rules`, `note`)
và chỉ cập nhật phiên bản + nguồn.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.modules.doc_ingest.schemas.manifest import CrmSource, DocManifest
from app.modules.doc_ingest.sources.crm.config import CrmConfig

_KEEP = ("scope_rules", "exclude_pages", "exclude_sections", "exclude_reason", "note")


def draft_manifest(config: CrmConfig, *, doc_id: str, name: str, model: str, document_type: str, language: str,
                   source: CrmSource, existing: DocManifest | None = None) -> DocManifest:
    rule = config.document_types[document_type]
    data = {
        "doc_id": doc_id, "run_doc_ids": [doc_id], "doc_type": rule.doc_type, "doc_title": name,
        "doc_version": source.version, "product_models": [model], "lang": language,
        "default_scopes": list(rule.default_scopes),
        "scope_rules": [r.model_dump() for r in rule.scope_rules],
        "storage_bucket": f"{model.lower()}-docs",
        "note": f"Sinh từ CRM {source.synced_at}; cần người kiểm exclude_pages (bìa, lời cảm ơn) và scope_rules",
        "source": source.model_dump(mode="json"),
    }
    if existing is not None:
        data.update({k: getattr(existing, k) for k in _KEEP})
        data["scope_rules"] = [r.model_dump() for r in existing.scope_rules]
    return DocManifest.model_validate(data)


def write_manifest(manifest: DocManifest, path: Path, *, fresh: bool) -> None:
    header = [
        f"# {manifest.doc_title} · sinh từ CRM bởi `crm-fetch` (doc_ingest/sources/crm).",
        "# TODO người kiểm: exclude_pages/exclude_sections (bìa, lời cảm ơn, lịch sử phiên bản), scope_rules,"
        " rồi xoá dòng TODO." if fresh else "# Cập nhật phiên bản từ CRM; giữ các trường người đã điền.",
    ]
    body = yaml.safe_dump(manifest.model_dump(mode="json", exclude_defaults=False), allow_unicode=True,
                          sort_keys=False, width=110)
    path.write_text("\n".join(header) + "\n" + body, encoding="utf-8")
