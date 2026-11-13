"""Lưới an toàn: phân loại nhãn Docling (BL-33, T-16) + V-01 độ phủ text (BL-25 phần V-01, GT-20)."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from app.modules.doc_ingest.pipeline import load_words, run_normalization
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.normalized import ValidationResult
from tests.doc_ingest.f54 import F54_DIR, f54_docs
from tests.doc_ingest.synthetic import PAGE_H, SynPage, param_rows

DEFAULT = load_profile("default")
PDF = (Path(__file__).resolve().parents[3] / "docs" / "ai" / "doc_ingest_spike" / "source"
       / "F54_Operation Manual (English Version)_V.02.pdf")


def _f54(docs=None):
    docs = docs or f54_docs()
    pages = sorted(min(int(n) for n in d["pages"]) for d in docs)
    return run_normalization(docs, "f54", DEFAULT, load_words(F54_DIR, pages))


def _words(*lines: tuple[str, float]) -> list[dict]:
    """Từ giả lập: mỗi dòng (text, y) tách theo khoảng trắng, bbox trong lề trang."""
    words = []
    for text, y in lines:
        x = 90.0
        for token in text.split():
            words.append({"text": token, "bbox": {"x0": x, "y0": y, "x1": x + 6 * len(token), "y1": y + 10}})
            x += 6 * len(token) + 4
    return words


def _syn_doc(page: SynPage, label: str | None = None, index: int = 0) -> dict:
    doc = page.to_doc()
    if label is not None:
        doc["texts"][index]["label"] = label
    return doc


def _codes(result) -> list[str]:
    return [r.code for r in result.tables.review]


# ------------------------------------------------------------------ V-01 trên F54 (GT-20)

def test_gt20_every_f54_page_passes_v01() -> None:
    result = _f54()
    assert [v.target for v in result.validation] == [f"f54:p{p:03d}" for p in result.pages]
    assert all(v.passed for v in result.validation), [(v.target, v.score) for v in result.validation if not v.passed]
    assert "text_coverage_gap" not in _codes(result)


def test_gt20_dropping_a_text_element_flags_the_page() -> None:
    docs = f54_docs()
    page14 = next(d for d in docs if "14" in d["pages"])
    page14 = copy.deepcopy(page14)
    target = max(page14["texts"], key=lambda t: len(t.get("text", "")) if t["label"] == "list_item" else 0)
    target["text"] = ""
    result = _f54([page14 if "14" in d["pages"] else d for d in docs])
    flagged = [r for r in result.tables.review if r.code == "text_coverage_gap"]
    assert [(r.target, r.blocking, r.blocks) for r in flagged] == [("f54:p014", True, "chunk")]
    check = next(v for v in result.validation if v.target == "f54:p014")
    assert check.passed is False and check.detail["missing_count"] > 0


def test_captions_are_read_as_children_of_pictures_and_tables() -> None:
    result = _f54(f54_docs({11}))
    captions = [i.text for i in result.items if i.label == "caption"]
    assert "Figure 5. F54 controller I/O ports" in captions


def test_validation_round_trips_schema() -> None:
    for check in _f54().validation:
        assert ValidationResult.model_validate_json(check.model_dump_json()) == check


# ------------------------------------------------------------------ nhãn Docling (BL-33, T-16)

def _toc_page() -> dict:
    page = SynPage(5).table([["1.1 Overview", "3"], ["1.2 Dimension", "4"]], top=100, header_rows=(),
                            cols=[(90.0, 400.0), (500.0, 540.0)])
    doc = page.to_doc()
    doc["tables"][0]["label"] = "document_index"
    return doc


def test_t16_document_index_is_kept_not_a_logical_table() -> None:
    words = {5: _words(("1.1 Overview 3", 102), ("1.2 Dimension 4", 117))}
    result = run_normalization([_toc_page()], "syn", DEFAULT, words)
    assert result.tables.tables == []
    assert [i.label for i in result.elements.toc] == ["document_index"]
    assert len(result.elements.toc[0].cells) == 4
    assert [e.rule_id for e in result.tables.log] == ["T-16"]
    assert result.tables.review == [] and result.validation[0].passed is True


def test_t16_toc_line_and_title_outside_document_index_are_toc() -> None:
    """I-37 (F54 trang 3): dòng mục lục có chấm dẫn + số trang và tiêu đề "CONTENT" nằm ngoài document_index."""
    page = (SynPage(3).text("section_header", "CONTENT", 80)
            .text("text", "PART 1:CONTROLLER OVERVIEW " + "." * 60 + " 1", 100)
            .text("section_header", "2.5 CONNECTION DIAGRAM PULSE CONTROL" + "…" * 12 + "..15", 115)   # F86: dấu "…"
            .text("text", "Set the value to 1.", 130))
    result = run_normalization([page.to_doc()], "syn", DEFAULT)
    assert [e.normalized_type for e in result.normalized or []] == ["toc", "toc", "toc", "text"]
    assert (result.normalized or [])[3].label_heading is None       # "CONTENT" không thành label heading
    assert (result.normalized or [])[3].section_path == []          # dòng mục lục có số không mở mục
    # Tiêu đề không đứng trước mục lục: giữ nguyên là label heading.
    plain = SynPage(4).text("section_header", "CONTENT", 80).text("text", "This chapter lists the parts.", 100)
    result = run_normalization([plain.to_doc()], "syn", DEFAULT)
    assert [e.normalized_type for e in result.normalized or []] == ["label_heading", "text"]


def test_unsupported_label_is_flagged_and_not_counted() -> None:
    page = SynPage(1).text("text", "x squared plus y squared", 100)
    doc = _syn_doc(page, "formula")
    result = run_normalization([doc], "syn", DEFAULT, {1: _words(("x squared plus y squared", 100))})
    assert [i.label for i in result.elements.unsupported] == ["formula"]
    assert _codes(result) == ["unsupported_element", "text_coverage_gap"]
    first = result.tables.review[0]
    assert (first.target, first.blocking, first.blocks) == ("syn:p001:e000", True, "chunk")
    assert result.validation[0].score == 0.0


def test_v01_detects_duplicated_content() -> None:
    page = SynPage(1).text("text", "Connect the sensor wire", 100).text("text", "Connect the sensor wire", 120)
    result = run_normalization([page.to_doc()], "syn", DEFAULT, {1: _words(("Connect the sensor wire", 100))})
    check = result.validation[0]
    assert check.score == 1.0 and check.passed is False and check.detail["duplicate_ratio"] == 0.5
    assert _codes(result) == ["text_coverage_gap"]


def test_v01_ignores_words_inside_furniture() -> None:
    page = SynPage(1).text("page_header", "Model: X1", 30, 45).text("text", "Body text here", 100)
    words = {1: _words(("Model: X1", 32), ("Body text here", 100), ("Page 7", PAGE_H - 40))}
    page.text("page_footer", "Page 7", PAGE_H - 42, PAGE_H - 28)
    check = run_normalization([page.to_doc()], "syn", DEFAULT, words).validation[0]
    assert (check.score, check.detail["page_tokens"]) == (1.0, 3)


def test_v01_not_run_without_text_layer() -> None:
    page = SynPage(1).table([["Key", "Description", "Value"], *param_rows(1, 3)], top=100)
    result = run_normalization([page.to_doc()], "syn", DEFAULT, {1: []})
    assert result.validation[0].passed is None and "text_coverage_gap" not in _codes(result)
    assert run_normalization([page.to_doc()], "syn", DEFAULT).validation == []


def test_review_ids_are_unique_across_steps() -> None:
    page = SynPage(1).text("text", "formula body", 90).table(param_rows(1, 4), top=120, header_rows=())
    result = run_normalization([_syn_doc(page, "formula")], "syn", DEFAULT, {1: _words(("unrelated words", 300))})
    ids = [r.item_id for r in result.tables.review]
    assert ids == [f"rq-{n:04d}" for n in range(1, len(ids) + 1)]
    assert {"unsupported_element", "header_missing", "text_coverage_gap"} <= set(_codes(result))


# ------------------------------------------------------------------ text layer từ PDF (BL-02b)

@pytest.mark.skipif(importlib.util.find_spec("pypdfium2") is None or not PDF.is_file(),
                    reason="cần pypdfium2 (.venv-ingest) và PDF F54 trong docs/ai/doc_ingest_spike/source/")
def test_page_words_matches_fixture() -> None:
    from app.modules.doc_ingest.parse.docling_runner import extract_words

    fixture = json.loads((F54_DIR / "p014.words.json").read_text(encoding="utf-8"))["words"]
    assert extract_words(PDF, [14])[14] == fixture
