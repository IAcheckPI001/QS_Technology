"""Nạp manifest tài liệu (contract C2 §3) từ `manifests/*.yaml`; schema ở `schemas/manifest.py`."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.modules.doc_ingest.schemas.manifest import DocManifest

MANIFESTS_DIR = Path(__file__).resolve().parent / "manifests"


def load_manifest(path: Path) -> DocManifest:
    return DocManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def find_manifest(run_doc_id: str, manifests_dir: Path = MANIFESTS_DIR) -> DocManifest | None:
    """Manifest có `run_doc_ids` chứa `run_doc_id` (hoặc tên file trùng); không có → None."""
    for path in sorted(manifests_dir.glob("*.yaml")):
        manifest = load_manifest(path)
        if run_doc_id in manifest.run_doc_ids or path.stem == run_doc_id:
            return manifest
    return None
