"""Nạp profile cấu hình (D-11). Luật T-xx chỉ đọc tri thức miền qua `Profile`.

Profile YAML nằm trong `profiles/`; `extends` kế thừa profile khác (key của con thay thế
nguyên giá trị, riêng `thresholds` gộp theo khóa); `vocabulary_file` trỏ tới snapshot
từ vựng registry. Hash profile chỉ để truy vết trong run report, không nằm trong hash
approval (approval gắn với nội dung unit, H-6).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from app.modules.doc_ingest.schemas.profile import Profile

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"


def _resolve_path(name_or_path: str | Path, base: Path) -> Path:
    path = Path(name_or_path)
    if path.suffix in {".yaml", ".yml"}:
        return path if path.is_absolute() else base / path
    return base / f"{name_or_path}.yaml"


def _load_raw(path: Path, seen: tuple[Path, ...] = ()) -> dict[str, Any]:
    if path in seen:
        raise ValueError(f"profile extends tạo vòng: {path.name}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"profile {path.name} phải là mapping")
    parent_name = raw.pop("extends", None)
    if parent_name is None:
        merged = raw
    else:
        merged = _load_raw(_resolve_path(parent_name, path.parent), (*seen, path))
        thresholds = {**merged.get("thresholds", {}), **raw.pop("thresholds", {})}
        merged = {**merged, **raw, "thresholds": thresholds}
    vocabulary_file = raw.get("vocabulary_file")
    if vocabulary_file is not None:
        merged["vocabulary_file"] = str(path.parent / vocabulary_file)
    return merged


def load_profile(name_or_path: str | Path = "default", base_dir: Path = PROFILES_DIR) -> Profile:
    raw = _load_raw(_resolve_path(name_or_path, base_dir))
    vocabulary_file = raw.pop("vocabulary_file", None)
    if vocabulary_file is None:
        raise ValueError("profile thiếu vocabulary_file (trực tiếp hoặc qua extends)")
    vocabulary = json.loads(Path(vocabulary_file).read_text(encoding="utf-8"))
    vocabulary.pop("source", None)
    return Profile.model_validate({**raw, "vocabulary": vocabulary})


def profile_hash(profile: Profile) -> str:
    canonical = json.dumps(profile.model_dump(mode="json"), sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
