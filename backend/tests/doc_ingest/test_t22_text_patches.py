"""T-22: tiêu đề bị OCR hỏng được phát hiện và vá chữ (Giai đoạn 1b kế hoạch fix, 2026-11-25)."""
from __future__ import annotations

from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.normalize.text_patches import apply_text_patches
from app.modules.doc_ingest.pipeline import RunResult, run_normalization
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.normalize.docling_reader import read_items
from app.modules.doc_ingest.schemas.table_patch import TextPatch
from tests.doc_ingest.synthetic import SynPage
from tests.doc_ingest.test_text_frames import _s0

PROFILE = load_profile("qs_controller")
GARBLED = "ES    S    EM"
FULL = "3.4.2 ASSIGN MACHINE, AUXILIARY COORDINATES TO SPECIFIED COORDINATE SYSTEM"


def _page(text: str = GARBLED) -> SynPage:
    page = SynPage(71).text("section_header", text, 40, x=(34.0, 542.0))
    page.text("text", "Select the axis and press APPLY MACH button.", 120)
    return page


def _run(page: SynPage, ocr: bool = True) -> RunResult:
    return run_normalization([page.to_doc()], "10iv", PROFILE, s0=_s0(page.page, ocr=ocr))


def _codes(result: RunResult) -> list[str]:
    return [r.code for r in result.tables.review]


def _patch(**kw) -> TextPatch:
    base = dict(patch_id="T01", page=71, find="ES S EM", replace=FULL, reason="OCR hỏng", evidence="re-OCR 2x/3x")
    return TextPatch(**{**base, **kw})


def test_garbled_heading_on_ocr_page_is_a_blocking_review() -> None:
    result = _run(_page())
    [item] = [r for r in result.tables.review if r.code == "heading_garbled"]
    assert item.blocking and item.blocks == "chunk"


def test_clean_wide_heading_text_page_and_missing_ocr_are_not_flagged() -> None:
    assert "heading_garbled" not in _codes(_run(_page("ASTRO 6AV")))               # chữ lớn, không có chuỗi khoảng trắng
    assert "heading_garbled" not in _codes(_run(_page(), ocr=False))               # trang có text layer
    assert "heading_garbled" not in _codes(_run(_page(FULL)))                      # tiêu đề đầy đủ


def test_patch_replaces_the_line_logs_it_and_removes_the_review() -> None:
    items = read_items([_page().to_doc()], "10iv")
    rec = Recorder()
    out = apply_text_patches(items, [_patch()], rec)
    assert [i.text for i in out if i.page == 71][0] == FULL and not rec.review
    entry = next(e for e in rec.log if e.rule_id == "T-22")
    assert entry.before == {"text": GARBLED} and entry.after["text"] == FULL and entry.after["patch_id"] == "T01"


def test_unmatched_or_ambiguous_patch_is_a_blocking_review_and_changes_nothing() -> None:
    items = read_items([_page().to_doc()], "10iv")
    for patch in (_patch(find="khong co"), _patch(page=9)):
        rec = Recorder()
        out = apply_text_patches(items, [patch], rec)
        assert [i.text for i in out] == [i.text for i in items]
        assert [r.code for r in rec.review] == ["text_patch_unmatched"] and rec.review[0].blocking
    page = SynPage(71).text("section_header", GARBLED, 40, x=(34.0, 542.0)).text("section_header", GARBLED, 80, x=(34.0, 542.0))
    rec = Recorder()
    apply_text_patches(read_items([page.to_doc()], "10iv"), [_patch()], rec)
    assert [r.code for r in rec.review] == ["text_patch_unmatched"] and "2 lines" in rec.review[0].detail
