"""Nhóm PI: profile isolation (D-11) + GT-23. PI-07 (đồng bộ snapshot registry) nằm ở
`tests/chatbot/test_registry_snapshot.py` vì cần import module chatbot."""
import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.modules.doc_ingest.profile import PROFILES_DIR, load_profile, profile_hash
from app.modules.doc_ingest.review.approval import carry_over, content_hash, table_unit_payload, transition
from app.modules.doc_ingest.schemas.review import KnowledgeUnit, UnitState
from tests.doc_ingest.f54 import f54_docs, run_docs, run_f54

DOC_INGEST = Path(__file__).resolve().parents[2] / "app" / "modules" / "doc_ingest"
RULE_PACKAGES = ("normalize", "technical_refs", "review", "schemas", "validate")
SNAPSHOT = PROFILES_DIR / "registry_snapshot.json"


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------------ PI-01, PI-02

def test_pi01_bundled_profiles_load() -> None:
    default, qs = load_profile("default"), load_profile("qs_controller")
    assert (default.name, qs.name) == ("default", "qs_controller")
    assert qs.applicability_lexicon == default.applicability_lexicon       # kế thừa
    assert qs.thresholds == default.thresholds


def test_pi01_unknown_key_is_rejected(tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad.yaml", f"name: bad\nvocabulary_file: {SNAPSHOT.as_posix()}\ncolour: red\n")
    with pytest.raises(ValidationError):
        load_profile(bad)


def test_pi01_extends_cycle_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "a.yaml", "name: a\nextends: b\n")
    _write(tmp_path / "b.yaml", "name: b\nextends: a\n")
    with pytest.raises(ValueError, match="vòng"):
        load_profile("a", base_dir=tmp_path)


def test_pi02_default_profile_has_no_domain_patterns() -> None:
    default = load_profile("default")
    assert default.code_patterns == [] and default.param_prefixes == []
    models = {m.casefold() for m in default.vocabulary.product_models}
    for entry in default.applicability_lexicon:
        assert not models & set(entry.phrase.casefold().split())


# ------------------------------------------------------------------ PI-04 (GT-23)

def _code_strings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
                  and node.body and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant)}
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings]


def _rule_files() -> list[Path]:
    return [p for pkg in RULE_PACKAGES for p in (DOC_INGEST / pkg).rglob("*.py") if "__pycache__" not in p.parts]


def test_pi04_gt23_rules_contain_no_document_or_domain_constants() -> None:
    vocab = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    forbidden_words = {m.casefold() for m in vocab["product_models"]} | {"f54_om", "qstcnc", "touch controller"}
    forbidden_patterns = [re.compile(p) for p in (r"#\\?d", r"M\\d\{4\}", r"\bCN\d", r"\b[XY]\d{2}", r"#\d{2,}")]
    violations = []
    for path in _rule_files():
        for value in _code_strings(path):
            words = set(re.findall(r"[\w.]+", value.casefold())) | {value.casefold()}
            if words & forbidden_words or any(p.search(value) for p in forbidden_patterns):
                violations.append(f"{path.relative_to(DOC_INGEST)}: {value!r}")
    assert violations == []


def test_pi04_rules_read_profiles_only_through_loader() -> None:
    offenders = []
    for path in _rule_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        if "yaml" in imported or any("profiles" in s for s in _code_strings(path)):
            offenders.append(path.name)
    assert offenders == []


# ------------------------------------------------------------------ PI-05, PI-06, PI-08

def _strip_param_data(run) -> list[dict]:
    payloads = []
    for table in run.tables:
        data = table.model_dump(mode="json")
        data["flags"] = [f for f in data["flags"] if f != "param_table"]
        for row in data["rows"]:
            row["param_ref"] = None
        payloads.append(data)
    return payloads


def test_pi05_switching_profile_changes_only_profile_driven_output() -> None:
    default, qs = run_f54("default"), run_f54("qs_controller")
    assert _strip_param_data(default) == _strip_param_data(qs)
    assert any(r.param_ref for t in qs.tables for r in t.rows)
    assert [r.model_dump() for r in default.review] == [r.model_dump() for r in qs.review]


def test_pi06_profile_change_without_output_change_keeps_approval(tmp_path: Path) -> None:
    variant = _write(tmp_path / "variant.yaml",
                     f"name: default\nextends: {(PROFILES_DIR / 'default.yaml').as_posix()}\n"
                     "caption_keywords: [Figure, Fig., Hình, Table, Bảng, Abbildung]\n")
    base, changed = load_profile("default"), load_profile(variant)
    assert profile_hash(base) != profile_hash(changed)

    def unit_for(run) -> KnowledgeUnit:
        table = run.tables[0]
        return KnowledgeUnit(unit_id=table.logical_table_id, unit_type="parameter",
                             content_hash=content_hash(table_unit_payload(table)), evidence_hash="e",
                             state=UnitState.PENDING_REVIEW)

    docs = f54_docs({167, 168, 169})
    _, record = transition(unit_for(run_docs(docs, base)), UnitState.APPROVED, actor="reviewer.a",
                           now=datetime(2026, 11, 3, tzinfo=timezone.utc))
    assert record is not None
    result = carry_over([unit_for(run_docs(docs, changed))], [record])
    assert [u.state for u in result.units] == [UnitState.APPROVED]


def test_pi08_renaming_document_changes_only_identifiers() -> None:
    original = run_docs(f54_docs(), doc_id="f54")
    renamed = run_docs(f54_docs(), doc_id="manual_x")

    def dump(run, doc_id: str) -> str:
        text = json.dumps([t.model_dump(mode="json") for t in run.tables]
                          + [r.model_dump(mode="json") for r in run.review]
                          + [e.model_dump(mode="json") for e in run.log], ensure_ascii=False)
        return text.replace(f"{doc_id}:", "<doc>:")

    assert dump(original, "f54") == dump(renamed, "manual_x")
