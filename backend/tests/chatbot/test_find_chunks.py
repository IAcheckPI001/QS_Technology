"""Định dạng đầu ra của `scripts/find_chunks.py`. Không cần DB."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("find_chunks", ROOT / "scripts" / "find_chunks.py")
fc = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = fc
spec.loader.exec_module(fc)

ROW = {"id": 7, "chunk_key": "d:B0007", "doc_id": "d", "chunk_type": "wiring", "chunk_role": "child",
       "section_path": ["PART 2", "2.1 \"Home\" setting"], "page_start": 5, "page_end": 6,
       "content": "Set  parameter\n#1234 to 10.\n", "content_hash": "ab" * 32, "assets": [{"path": "x.png"}]}


def test_yaml_entry_is_valid_yaml_and_matches_eval_schema() -> None:
    entry = yaml.safe_load("expected:\n" + fc.yaml_entry(ROW))["expected"][0]
    assert entry["content_hash"] == "ab" * 32 and entry["section_path"] == ["PART 2", "2.1 \"Home\" setting"]
    assert entry["chunk_key"] == "d:B0007" and entry["note"] == "Set parameter #1234 to 10."


def test_format_row() -> None:
    text = fc.format_row(ROW, show=12)
    assert text.splitlines()[0] == f"#7 d tr.5-6 [wiring/child] {len(ROW['content'])} ký tự, ảnh 1, hash abababab"
    assert "PART 2 › 2.1" in text and text.endswith("Set paramete")      # show=12 cắt đúng 12 ký tự
    assert len(fc.format_row(ROW, show=0).splitlines()) == 2        # show=0: không in nội dung
