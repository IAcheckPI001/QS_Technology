"""S0 hồ sơ tài liệu (BL-24): quyết định OCR theo trang, `ocr_required`, V-01 trên trang OCR,
`empty_table`."""
import importlib.util
from pathlib import Path

import pytest

from app.modules.doc_ingest.pipeline import load_words, run_normalization
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.s0 import build_profile, decide, ocr_pages
from tests.doc_ingest.f54 import F54_DIR, f54_docs
from tests.doc_ingest.synthetic import SynPage

DEFAULT = load_profile("default")
SOURCE = Path(__file__).resolve().parents[3] / "docs" / "ai" / "doc_ingest_spike" / "source"
F54_PDF = SOURCE / "F54_Operation Manual (English Version)_V.02.pdf"
F86_PDF = SOURCE / "F86_Operation Manual (English Version).pdf"


def metrics(page: int, chars: int, bad: float = 0.0) -> dict:
    return {"page": page, "text_chars": chars, "bad_char_ratio": bad, "rotation": 0,
            "bitmap_area_ratio": 0.3, "vector_path_count": 12, "page_label": None}


@pytest.mark.parametrize(("chars", "bad", "layer", "ocr"), [
    (0, 0.0, "missing", True), (19, 0.0, "missing", True), (20, 0.0, "ok", False),
    (500, 0.2, "poor", True), (500, 0.05, "ok", False),
])
def test_decide_uses_profile_thresholds(chars: int, bad: float, layer: str, ocr: bool) -> None:
    page = decide(metrics(1, chars, bad), DEFAULT.thresholds)
    assert (page.text_layer, page.ocr) == (layer, ocr)


def test_ocr_mode_controls_which_pages_are_ocr() -> None:
    measured = [metrics(1, 0), metrics(2, 800)]
    assert ocr_pages(build_profile(measured, DEFAULT.thresholds, "auto")) == {1}
    assert ocr_pages(build_profile(measured, DEFAULT.thresholds, "off")) == set()
    assert ocr_pages(build_profile(measured, DEFAULT.thresholds, "force")) == {1, 2}
    auto = build_profile(measured, DEFAULT.thresholds, "auto")
    assert auto.pages[0].docling_config["engine"] == "rapidocr" and auto.pages[1].docling_config == {"do_ocr": False}


def _hybrid_metrics(page: int, chars: int, bitmap: float) -> dict:
    return {**metrics(page, chars), "bitmap_area_ratio": bitmap}


def test_hybrid_page_in_a_scanned_document_is_forced_to_ocr() -> None:
    """10iV trang 96: text layer chỉ có phần "Notes" (321 ký tự), 18% bitmap; 4/5 trang còn lại là bản quét."""
    measured = [_hybrid_metrics(i, 0, 0.5) for i in range(1, 5)] + [_hybrid_metrics(5, 321, 0.18)]
    prof = build_profile(measured, DEFAULT.thresholds, "auto")
    assert prof.pages[4].text_layer == "hybrid" and prof.pages[4].ocr_applied
    assert ocr_pages(prof) == {1, 2, 3, 4, 5}
    assert prof.pages[4].docling_config["engine"] == "rapidocr"


def test_hybrid_rule_needs_scanned_majority_low_text_and_bitmap() -> None:
    mostly_text = [_hybrid_metrics(i, 900, 0.05) for i in range(1, 5)] + [_hybrid_metrics(5, 321, 0.18)]
    assert ocr_pages(build_profile(mostly_text, DEFAULT.thresholds, "auto")) == set()       # tài liệu text layer
    scanned = [_hybrid_metrics(i, 0, 0.5) for i in range(1, 5)]
    for page in (_hybrid_metrics(5, 321, 0.05), _hybrid_metrics(5, 900, 0.18)):             # ít bitmap / nhiều chữ
        assert ocr_pages(build_profile(scanned + [page], DEFAULT.thresholds, "auto")) == {1, 2, 3, 4}
    assert ocr_pages(build_profile(scanned + [_hybrid_metrics(5, 321, 0.18)], DEFAULT.thresholds, "off")) == set()


def _run(mode: str):
    page = SynPage(3).text("caption", "Figure 1-3. Front view", 100)
    s0 = build_profile([metrics(3, 0)], DEFAULT.thresholds, mode)
    return run_normalization([page.to_doc()], "syn", DEFAULT, {3: []}, s0)


def test_page_without_text_layer_gets_ocr_required_and_v01_not_independent() -> None:
    result = _run("auto")
    [item] = [r for r in result.tables.review if r.code == "ocr_required"]
    assert (item.target, item.blocking, item.blocks) == ("syn:p003", True, "chunk")
    assert "OCR applied" in item.detail
    [check] = result.validation
    assert check.passed is None and check.detail["reason"] == "OCR page: no independent text layer"


def test_ocr_off_still_flags_missing_content() -> None:
    [item] = [r for r in _run("off").tables.review if r.code == "ocr_required"]
    assert "OCR not applied" in item.detail and item.blocking


def test_page_with_text_layer_has_no_ocr_flag() -> None:
    docs = f54_docs({14})
    s0 = build_profile([metrics(14, 1500)], DEFAULT.thresholds, "auto")
    result = run_normalization(docs, "f54", DEFAULT, load_words(F54_DIR, [14]), s0)
    assert "ocr_required" not in {r.code for r in result.tables.review}
    assert result.validation[0].passed is True


def test_empty_docling_table_is_a_non_blocking_review_item() -> None:
    result = run_normalization(f54_docs({18}), "f54", DEFAULT)
    [item] = [r for r in result.tables.review if r.code == "empty_table"]
    assert (item.blocking, item.blocks, item.element_id) == (False, "none", item.target)


@pytest.mark.skipif(importlib.util.find_spec("pypdfium2") is None or not (F54_PDF.is_file() and F86_PDF.is_file()),
                    reason="cần pypdfium2 (.venv-ingest) và PDF F54/F86 trong docs/ai/doc_ingest_spike/source/")
def test_measure_real_pdfs() -> None:
    from app.modules.doc_ingest.parse.profile_probe import measure_pages

    f54 = decide(measure_pages(F54_PDF, [14])[0], DEFAULT.thresholds)
    f86 = decide(measure_pages(F86_PDF, [5])[0], DEFAULT.thresholds)
    assert (f54.text_layer, f54.ocr) == ("ok", False) and f54.text_chars > 1000
    assert (f86.text_layer, f86.ocr, f86.text_chars) == ("missing", True, 0)
