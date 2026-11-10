"""Bước B: độ khớp profile (B1) và chấm điểm theo nhãn mẫu (B3, B4)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.modules.doc_ingest.eval.labels import DocLabels
from app.modules.doc_ingest.eval.profile_fit import code_shape, profile_fit
from app.modules.doc_ingest.eval.score import score_run
from app.modules.doc_ingest.pipeline import run_normalization, write_run
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.run import RunSource
from tests.doc_ingest.f54 import f54_docs
from tests.doc_ingest.synthetic import SynPage

QS = load_profile("qs_controller")
DEFAULT = load_profile("default")
EVAL_DIR = Path(__file__).resolve().parent / "fixtures" / "eval"


# ------------------------------------------------------------------ B1 độ khớp profile

def test_code_shape() -> None:
    assert [code_shape(t) for t in ("#4140", "P01-02", "CN10", "G59.1")] == ["#9", "P9-9", "CN9", "G9.9"]


def _codes_page(n: int = 25) -> SynPage:
    page = SynPage(1)
    for i in range(n):
        page.text("text", f"Set P{i:02d}-01 and #4{i:03d} before start.", 60 + 20 * i)
    return page


def test_default_profile_with_codes_and_unknown_shapes() -> None:
    fit = profile_fit(run_normalization([_codes_page().to_doc()], "syn", DEFAULT))
    assert {"default_profile_with_codes", "unknown_code_shapes"} <= set(fit.signals)
    shapes = {s.shape: s.count for s in fit.unknown_shapes}
    assert shapes["P9-9"] == 25 and shapes["#9"] == 25
    fit_qs = profile_fit(run_normalization([_codes_page().to_doc()], "syn", QS))
    assert "default_profile_with_codes" not in fit_qs.signals
    assert {s.shape for s in fit_qs.unknown_shapes} == {"P9-9"}     # `#` đã nhận, `P01-01` vẫn lạ
    assert fit_qs.param_tokens == {"#": 25}


def test_near_miss_high() -> None:
    page = SynPage(1)
    for i in range(6):
        page.text("text", f"Call M10{i} now.", 60 + 20 * i)
    fit = profile_fit(run_normalization([page.to_doc()], "syn", QS))
    assert "near_miss_high" in fit.signals and fit.near_miss[0].count == 1


def test_big_picture_with_sentences_signals_swallowed_text() -> None:
    page = SynPage(1)
    pic = page.picture(40, 760, x=(30.0, 580.0))
    for i in range(3):
        page.text("text", "Đầu tiên nhấn vào nút AUTO trên bảng điều khiển của thiết bị để chuyển chế độ", 100 + 40 * i,
                  parent=pic)
    page.text("text", "Short label", 600, parent=pic)
    fit = profile_fit(run_normalization([page.to_doc()], "syn", DEFAULT))
    assert "picture_swallows_text" in fit.signals and fit.page_pictures_with_text == [1]


def test_diagram_labels_do_not_signal() -> None:
    page = SynPage(1)
    pic = page.picture(40, 760, x=(30.0, 580.0))
    for i in range(30):
        page.text("text", f"CN{i} FG", 100 + 20 * i, parent=pic)
    assert "picture_swallows_text" not in profile_fit(run_normalization([page.to_doc()], "syn", DEFAULT)).signals


def test_f54_fixture_fit_has_no_ocr_signals() -> None:
    fit = profile_fit(run_normalization(f54_docs(), "f54", QS))
    assert not {"ocr_majority", "ocr_lang_mismatch", "picture_swallows_text", "near_miss_high"} & set(fit.signals)
    assert fit.param_tokens["M"] >= 12


# ------------------------------------------------------------------ B3 chấm điểm

def _run_dir(tmp_path: Path) -> Path:
    page = SynPage(1)
    page.text("list_item", "M1920: Homing sensor for X axis", 100, x=(103.0, 500.0))
    page.text("list_item", "o M1920 = 0 : NC", 120, x=(139.0, 500.0))
    page.text("text", "Call macro M0100 after homing.", 160)          # bẫy: M-code 4 chữ số
    page.text("text", "This is not available on F54 controller.", 200)
    result = run_normalization([page.to_doc()], "syn", QS)
    write_run(tmp_path, result, doc_id="syn", run_id="t", created_at=datetime(2026, 11, 9), source=RunSource(),
              timings={}, versions={})
    return tmp_path


def _labels(**page_extra: object) -> DocLabels:
    page = {"page": 1,
            "param_refs": [{"label": "M1920", "prefix": "M", "kind": "single", "codes": [1920], "role": "definition"},
                           {"label": "M1920", "prefix": "M", "kind": "single", "codes": [1920], "role": "value_option"}],
            "list_children": [{"child": "o M1920 = 0", "parent": "M1920:"}],
            "applicability": ["not available on F54 controller"],
            "body_snippets": ["Homing sensor for X axis", "This sentence is missing"]}
    page.update(page_extra)
    return DocLabels.model_validate({"doc_id": "syn", "source_pdf": "x.pdf", "labeled_by": "test", "method": "test",
                                     "pages": [page]})


def test_score_counts_fp_roles_lists_applicability_content(tmp_path: Path) -> None:
    report = score_run(_run_dir(tmp_path), _labels())
    g = report.groups["text_layer"]
    assert (g.t12.tp, g.t12.fp, g.t12.fn) == (2, 1, 0)        # M0100 là FP
    assert g.t12.precision == round(2 / 3, 4) and g.t12.recall == 1.0 and g.t12_role_accuracy == 1.0
    assert (g.t08_correct, g.t08_wrong, g.t08_missing) == (1, 0, 0)
    assert (g.t13.tp, g.t13.fn) == (1, 0)
    assert (g.content_found, g.content_total) == (1, 2)
    assert report.provisional and report.gate_passed is False
    failed = {c.name for c in report.gate if c.passed is False}
    assert failed == {"T-12 precision", "Nội dung thân giữ lại"}
    assert report.details["t12_fp"] == ["p1 M[100] (single)"]


def test_wrong_role_and_wrong_parent_are_reported(tmp_path: Path) -> None:
    run_dir = _run_dir(tmp_path)
    labels = _labels(param_refs=[
        {"label": "M1920", "prefix": "M", "kind": "single", "codes": [1920], "role": "mention"},
        {"label": "M1920", "prefix": "M", "kind": "single", "codes": [1920], "role": "value_option"},
        {"label": "M0100", "prefix": "M", "kind": "single", "codes": [100], "role": "mention"}],
        list_children=[{"child": "o M1920 = 0", "parent": "Other parent"}])
    report = score_run(run_dir, labels)
    g = report.groups["text_layer"]
    assert g.t12_role_accuracy == round(2 / 3, 4) and g.t08_wrong == 1
    assert report.details["t12_role"] == ["p1 M1920: dự đoán definition"]


def test_label_files_are_valid() -> None:
    files = sorted(EVAL_DIR.glob("*.labels.json"))
    assert {f.name for f in files} >= {"f54.labels.json", "f10t.labels.json", "f86.labels.json",
                                       "f86_italliation.labels.json"}
    for f in files:
        labels = DocLabels.model_validate(json.loads(f.read_text(encoding="utf-8")))
        assert labels.pages and labels.verified is False       # chưa được team xác nhận
