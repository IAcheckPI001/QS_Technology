"""T-21: lớp vá ô thủ công cho bảng logic (2026-11-25)."""
import pytest
import yaml
from pydantic import ValidationError

from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.normalize.table_patches import apply_patches
from app.modules.doc_ingest.schemas.table_patch import CellPatch, TablePatchFile
from app.modules.doc_ingest.table_patch_io import PATCHES_DIR, load_patches, load_text_patches
from tests.doc_ingest.f54 import run_docs
from tests.doc_ingest.synthetic import SynPage


def _table():
    page = SynPage(1).table([["Port", "Pins", "Description"], ["CN6", "- - X46 - X45", "Input"],
                             ["CN7", "- X57 - CX2 X47", "Input"]], top=100)
    return run_docs([page.to_doc()], doc_id="syn").tables


def _patch(**kw) -> CellPatch:
    base = dict(patch_id="P01", page=1, row_key="CN7", column=1, find="- CX2 X47", replace="- CX2",
                reason="X47 thuộc CN6", evidence="PDF tr.1", status="proposed")
    return CellPatch(**{**base, **kw})


def _cell(tables, key, col):
    return next(r for r in tables[0].rows if r.cells[0].text == key).cells[col].text


def test_patch_replaces_exact_substring_and_records_log_and_flag() -> None:
    tables, rec = _table(), Recorder()
    applied = apply_patches(tables, [_patch(), _patch(patch_id="P02", row_key="CN6", find="- - X46", replace="- X47 - X46")], rec)
    assert applied == 2
    assert _cell(tables, "CN7", 1) == "- X57 - CX2"
    assert _cell(tables, "CN6", 1) == "- X47 - X46 - X45"
    assert {"cell_patched:P01", "cell_patched:P02"} <= set(tables[0].flags)
    entry = next(e for e in rec.log if e.rule_id == "T-21" and e.after["patch_id"] == "P01")
    assert entry.before == {"text": "- X57 - CX2 X47"} and entry.after["text"] == "- X57 - CX2"
    assert rec.review == []


def test_patch_not_found_creates_blocking_review_and_leaves_cell_unchanged() -> None:
    tables, rec = _table(), Recorder()
    for patch in (_patch(row_key="CN9"), _patch(patch_id="P02", page=2), _patch(patch_id="P03", find="không có"),
                  _patch(patch_id="P04", column=7)):
        assert apply_patches(tables, [patch], rec) == 0
    assert _cell(tables, "CN7", 1) == "- X57 - CX2 X47"
    assert [r.code for r in rec.review] == ["table_patch_unmatched"] * 4
    assert all(r.blocking and r.blocks == "chunk" for r in rec.review)
    assert "P03" in rec.review[2].detail


def test_patch_refuses_text_that_occurs_more_than_once_in_the_cell() -> None:
    page = SynPage(1).table([["Port", "Pins", "Description"], ["CN1", "- X1 - X1", "Input"]], top=100)
    tables, rec = run_docs([page.to_doc()], doc_id="syn").tables, Recorder()
    assert apply_patches(tables, [_patch(row_key="CN1", find="- X1", replace="- X2")], rec) == 0
    assert "occurs 2 times" in rec.review[0].detail and _cell(tables, "CN1", 1) == "- X1 - X1"


def test_patch_file_validation() -> None:
    patch = _patch().model_dump()
    with pytest.raises(ValidationError):
        TablePatchFile.model_validate({"doc_id": "x", "patches": [patch, patch]})            # patch_id trùng
    with pytest.raises(ValidationError):
        TablePatchFile.model_validate({"doc_id": "x", "patches": [{**patch, "find": ""}]})   # find rỗng
    with pytest.raises(ValidationError):
        TablePatchFile.model_validate({"doc_id": "x", "patches": [{**patch, "extra": 1}]})   # trường lạ


def test_load_patches_missing_file_and_doc_id_mismatch(tmp_path) -> None:
    assert load_patches("khong-co", tmp_path) == []
    (tmp_path / "doc-a.yaml").write_text(yaml.safe_dump({"doc_id": "doc-b", "patches": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_patches("doc-a", tmp_path)


def test_shipped_patch_files_are_valid() -> None:
    names = sorted(p.stem for p in PATCHES_DIR.glob("*.yaml"))
    assert names == ["10iv-operation-en", "6ave-operation-en", "f54-installation-en", "f86-installation-en",
                     "f86-operation-en"]
    assert [len(load_patches(n)) for n in names] == [0, 0, 4, 9, 0]
    assert [len(load_text_patches(n)) for n in names] == [1, 1, 0, 0, 1]
    for name in names:
        patches = [*load_patches(name), *load_text_patches(name)]
        assert all(p.evidence and p.reason for p in patches) and len({p.patch_id for p in patches}) == len(patches)
