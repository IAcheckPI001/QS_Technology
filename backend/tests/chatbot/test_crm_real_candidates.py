"""File ứng viên câu hỏi thật từ CRM (`evals/retrieval_cases/crm_real_candidates.yaml`): hợp lệ và đã ẩn danh."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals" / "retrieval_cases" / "crm_real_candidates.yaml"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_candidates_load_with_gold_schema() -> None:
    ev = _load("run_retrieval_eval", ROOT / "evals" / "run_retrieval_eval.py")
    cases = ev.load_cases(CASES)
    assert [c.id for c in cases] == [f"RC{i:02d}" for i in range(1, 17)]
    assert all(c.source == "real" and c.expected_intents and c.routing_only for c in cases)
    by_id = {c.id: c for c in cases}
    assert by_id["RC01"].split == by_id["RC04"].split == "dev"          # cùng ý: cùng split, không rò rỉ
    assert {c.split for c in cases} == {"dev", "test"}
    assert {c.id for c in cases if c.expect_abstain} == {"RC02", "RC08", "RC12"}


def test_candidates_are_anonymized() -> None:
    export = _load("export_chat_log", ROOT / "scripts" / "export_chat_log.py")
    for case in yaml.safe_load(CASES.read_text(encoding="utf-8"))["cases"]:
        text, changed = export.anonymize(case["question"])
        assert not changed, f"{case['id']}: còn thông tin cá nhân: {text}"
