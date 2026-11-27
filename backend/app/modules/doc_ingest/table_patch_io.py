"""Nạp file lớp vá ô `table_patches/<doc_id>.yaml` (xem `schemas/table_patch.py`, luật áp dụng T-21 ở
`normalize/table_patches.py`). Nằm ngoài `normalize/` vì luật chuẩn hoá không tự đọc YAML (test PI-04)."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.modules.doc_ingest.schemas.table_patch import CellPatch, TablePatchFile, TextPatch

PATCHES_DIR = Path(__file__).resolve().parent / "table_patches"


def _load(doc_id: str, patches_dir: Path) -> TablePatchFile | None:
    path = patches_dir / f"{doc_id}.yaml"
    if not path.exists():
        return None
    data = TablePatchFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if data.doc_id != doc_id:
        raise ValueError(f"{path.name}: doc_id {data.doc_id!r} khác tên file {doc_id!r}")
    return data


def load_patches(doc_id: str, patches_dir: Path = PATCHES_DIR) -> list[CellPatch]:
    data = _load(doc_id, patches_dir)
    return data.patches if data else []


def load_text_patches(doc_id: str, patches_dir: Path = PATCHES_DIR) -> list[TextPatch]:
    data = _load(doc_id, patches_dir)
    return data.text_patches if data else []
