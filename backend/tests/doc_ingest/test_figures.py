"""Hình: T-18 nhãn sát hình, T-14 vùng crop, T-09 screenshot, T-10 ứng viên watermark, T-11 caption.
SYN cho từng luật; F54 (có `objects.json`) và F86 OCR (không có) cho ca thật."""
import importlib.util
from pathlib import Path
from typing import Any

import pytest

from app.modules.doc_ingest.pipeline import (
    RunResult, crop_requests, load_objects, load_raw_dir, load_s0, load_words, run_normalization, table_hash,
)
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.normalized import NormalizedElement
from tests.doc_ingest.f54 import F54_DIR, f54_docs
from tests.doc_ingest.synthetic import SynPage

DEFAULT = load_profile("default")
F86_DIR = Path(__file__).resolve().parent / "fixtures" / "docling" / "f86_ocr"


def _run(pages: list[SynPage], objects: dict[int, Any] | None = None) -> RunResult:
    return run_normalization([p.to_doc() for p in pages], "syn", DEFAULT, None, None, objects)


def _by_text(result: RunResult, text: str) -> NormalizedElement:
    return next(e for e in result.normalized or [] if e.text == text)


def _by_type(result: RunResult, kind: str) -> list[NormalizedElement]:
    return [e for e in result.normalized or [] if e.normalized_type == kind]


def _codes(result: RunResult) -> list[str]:
    return [r.code for r in result.tables.review]


def _box(x0: float, y0: float, x1: float, y1: float, px: tuple[int, int] | None = None) -> dict[str, Any]:
    box: dict[str, Any] = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
    if px:
        box.update(px_w=px[0], px_h=px[1])
    return box


# ------------------------------------------------------------------ T-18 nhãn sát hình

def test_short_label_above_picture_in_top_band_is_figure_text() -> None:
    """F86 trang 8: `320 mm` gắn page_header, cách hình 3 pt, ở dải trên."""
    page = SynPage(8).text("page_header", "320 mm", 56, 69, x=(281, 320))
    pic = page.picture(72, 380, x=(129, 538))
    result = _run([page])
    label, picture = _by_text(result, "320 mm"), _by_type(result, "picture")[0]
    assert (label.normalized_type, label.content_layer, label.parent_element_id, label.flags) == (
        "figure_text", "body", picture.element_id, ["figure_text_attached"])
    assert "furniture_unconfirmed" not in _codes(result)
    assert pic


def test_body_label_overlapping_picture_edge_is_figure_text() -> None:
    """F86 trang 9: `320 mm` là text body, đè mép trên hình 2 pt."""
    page = SynPage(9)
    page.picture(230, 583, x=(65, 547))
    page.text("text", "320 mm", 228, 238, x=(280, 314))
    assert _by_text(_run([page]), "320 mm").normalized_type == "figure_text"


def test_sentences_headings_captions_and_far_text_are_not_attached() -> None:
    page = SynPage(3).text("section_header", "2.1 POWER SUPPLY", 80, 92)
    page.picture(100, 400)
    (page.text("text", "Mount with four screws.", 404, 414, x=(200, 400))
         .text("section_header", "Notes:", 405, 415, x=(100, 160))
         .text("caption", "Figure 2. Front", 406, 416, x=(410, 490))
         .text("text", "24V", 440, 450, x=(200, 230)))
    result = _run([page])
    assert _by_text(result, "2.1 POWER SUPPLY").normalized_type == "heading"
    assert _by_text(result, "Mount with four screws.").normalized_type == "text"
    assert _by_text(result, "Notes:").normalized_type == "label_heading"
    assert _by_text(result, "24V").normalized_type == "text"           # cách hình 40 pt
    assert not [e for e in result.normalized or [] if "figure_text_attached" in e.flags]


def test_repeated_footer_next_to_picture_stays_furniture() -> None:
    pages = []
    for n in (1, 2, 3):
        page = SynPage(n)
        page.picture(600, 752)
        pages.append(page.text("page_footer", "ACME CO.,LTD", 758, 770, x=(200, 300)))
    footers = [e for e in _run(pages).normalized or [] if e.text == "ACME CO.,LTD"]
    assert {(e.normalized_type, e.flags[0]) for e in footers} == {("furniture", "furniture_repeated")}


def test_label_goes_to_the_nearer_picture() -> None:
    page = SynPage(4)
    page.picture(100, 300, x=(100, 300))
    page.picture(310, 500, x=(100, 300))
    page.text("text", "M4", 302, 309, x=(150, 170))      # cách hình 1: 2 pt, hình 2: 1 pt
    result = _run([page])
    first, second = _by_type(result, "picture")
    assert _by_text(result, "M4").parent_element_id == second.element_id
    assert first.element_id != second.element_id


# ------------------------------------------------------------------ T-14 vùng crop

def test_crop_extends_by_bitmap_vector_and_label_but_not_page_frame() -> None:
    page = SynPage(1)
    page.picture(100, 400, x=(85, 500))
    page.text("text", "320 mm", 85, 95, x=(250, 300))       # nhãn T-18 phía trên
    objects = {1: {"bitmaps": [_box(70, 110, 480, 390, (900, 600))],
                   "paths": [_box(470, 150, 520, 160),        # đường kích thước kéo ra 20 pt
                             _box(30, 40, 580, 760)]}}        # khung trang: vượt quá 36 pt
    picture = _by_type(_run([page], objects), "picture")[0]
    assert picture.image is not None
    assert picture.image.crop_sources == ["docling", "bitmap", "vector", "label"]
    assert picture.image.crop_bbox.model_dump() == {"x0": 58.0, "y0": 73.0, "x1": 532.0, "y1": 412.0}


def test_crop_without_object_info_uses_bbox_and_padding() -> None:
    page = SynPage(1)
    page.picture(100, 400, x=(5, 500))
    result = _run([page])
    picture = _by_type(result, "picture")[0]
    assert picture.image is not None and picture.image.crop_sources == ["docling"]
    assert picture.image.crop_bbox.model_dump() == {"x0": 0.0, "y0": 88.0, "x1": 512.0, "y1": 412.0}
    assert any(e.rule_id == "T-14" and "no_object_info" in e.reason for e in result.tables.log)
    [request] = crop_requests(result)
    assert (request.page, request.native_px_per_pt) == (1, 0.0)


# ------------------------------------------------------------------ T-09 screenshot

def test_empty_table_covered_by_bitmap_is_screenshot() -> None:
    page = SynPage(18)
    table = page.empty_table(490, 694, x=(140, 500))
    page.text("caption", "Figure 15. Homing sensor status", 706, 718, x=(161, 480), parent=table)
    objects = {18: {"bitmaps": [_box(141, 492, 500, 695, (480, 272))], "paths": []}}
    result = _run([page], objects)
    [shot] = _by_type(result, "screenshot")
    assert shot.source_element_type == "table" and shot.image is not None
    assert shot.caption_element_id == _by_text(result, "Figure 15. Homing sensor status").element_id
    assert "empty_table" not in _codes(result) and result.tables.tables == []


def test_empty_table_without_bitmap_keeps_empty_table_review() -> None:
    page = SynPage(18)
    page.empty_table(490, 694)
    result = _run([page], {18: {"bitmaps": [], "paths": []}})
    assert "empty_table" in _codes(result) and not _by_type(result, "screenshot")


# ------------------------------------------------------------------ T-10 ứng viên watermark

_WATERMARK = _box(199, 319, 441, 473, (671, 427))


def _watermark_pages(picture: tuple[float, float, float, float], caption: bool = False) -> RunResult:
    pages = [SynPage(n).text("text", f"Body {n}", 100) for n in (1, 2, 3)]
    x0, top, x1, bottom = picture
    pic = pages[2].picture(top, bottom, x=(x0, x1))
    if caption:
        pages[2].text("caption", "Figure 9. Logo", bottom + 4, bottom + 14, parent=pic)
    return _run(pages, {n: {"bitmaps": [dict(_WATERMARK)], "paths": []} for n in (1, 2, 3)})


def test_picture_inside_repeated_bitmap_is_watermark_candidate() -> None:
    """F54 trang 171: Docling chỉ khoanh một phần watermark (IoU 0,53) nhưng picture nằm trọn trong nó."""
    result = _watermark_pages((216, 364, 425, 458))
    [mark] = _by_type(result, "watermark_candidate")
    assert mark.flags == ["watermark_candidate"] and mark.source_element_type == "picture"
    assert any(e.rule_id == "T-10" and e.element_id == "bitmap:671x427" for e in result.tables.log)


def test_watermark_with_caption_is_conflict_not_candidate() -> None:
    result = _watermark_pages((216, 364, 425, 458), caption=True)
    assert not _by_type(result, "watermark_candidate") and "watermark_conflict" in _codes(result)


def test_real_picture_larger_than_watermark_is_kept() -> None:
    result = _watermark_pages((90, 124, 526, 440))           # F54 trang 9: watermark phủ 27% picture
    assert len(_by_type(result, "picture")) == 1 and "watermark_conflict" not in _codes(result)


def test_logo_moving_and_rotating_across_pages_is_repeated() -> None:
    """F86: logo 412×262 px ở vị trí khác nhau mỗi trang, cỡ 94×148 pt (trang 13–14 xoay 148×94)."""
    boxes = {9: _box(507, 580, 601, 728, (412, 262)), 13: _box(232, 572, 380, 666, (412, 262)),
             15: _box(502, 286, 596, 434, (412, 262))}
    pages = [SynPage(n) for n in boxes]
    pages[1].picture(574, 664, x=(234, 378))
    result = _run(pages, {n: {"bitmaps": [box], "paths": []} for n, box in boxes.items()})
    assert len(_by_type(result, "watermark_candidate")) == 1


def test_image_reused_at_different_sizes_is_not_repeated() -> None:
    """F86: ảnh 275×275 px dùng lại trong các hình thật, mỗi lần một cỡ."""
    boxes = {15: _box(128, 373, 482, 517, (275, 275)), 16: _box(113, 59, 499, 221, (275, 275)),
             17: _box(105, 64, 506, 291, (275, 275))}
    pages = [SynPage(n) for n in boxes]
    pages[2].picture(66, 289, x=(107, 504))
    result = _run(pages, {n: {"bitmaps": [box], "paths": []} for n, box in boxes.items()})
    assert not _by_type(result, "watermark_candidate") and "watermark_conflict" not in _codes(result)


def test_bitmap_on_fewer_pages_is_not_repeated() -> None:
    pages = [SynPage(n) for n in (1, 2)]
    pages[1].picture(364, 458, x=(216, 425))
    result = _run(pages, {n: {"bitmaps": [dict(_WATERMARK)], "paths": []} for n in (1, 2)})
    assert not _by_type(result, "watermark_candidate")


# ------------------------------------------------------------------ T-11 caption

def test_figure_caption_attached_to_table_moves_to_picture_above() -> None:
    """F54 trang 11: `Figure 5` là caption của bảng bên dưới; hình nằm phía trên."""
    page = SynPage(11)
    page.picture(119, 417, x=(85, 554))
    page.table([["Port", "Functions"], ["CN1", "Input"]], top=450, cols=[(90, 200), (220, 540)])
    table = "#/tables/0"
    page.text("caption", "Figure 5. F54 controller I/O ports", 429, 441, x=(251, 390), parent=table)
    result = _run([page])
    picture, caption = _by_type(result, "picture")[0], _by_text(result, "Figure 5. F54 controller I/O ports")
    assert (caption.parent_element_id, caption.flags) == (picture.element_id, ["caption_relinked"])
    assert picture.caption_element_id == caption.element_id
    assert picture.caption_link is not None and picture.caption_link.model_dump() == {"source": "rule",
                                                                                     "rule_id": "T-11"}
    assert _by_type(result, "table_segment")[0].caption_element_id is None


def test_side_picture_in_the_same_row_is_not_the_caption_target() -> None:
    """F86 trang 9: dải hình ở lề phải bắt đầu cao hơn caption nhưng không nằm phía trên nó."""
    page = SynPage(9)
    main = page.picture(230, 583, x=(65, 547))
    page.picture(590, 718, x=(516, 592))
    page.text("caption", "Figure 1-6. Details dimension", 595, 609, x=(161, 417), parent=main)
    result = _run([page])
    caption = _by_text(result, "Figure 1-6. Details dimension")
    assert caption.parent_element_id == _by_type(result, "picture")[0].element_id and caption.flags == []


def test_caption_without_parent_links_to_picture_above() -> None:
    page = SynPage(17)
    page.picture(24, 290, x=(128, 593))
    page.text("caption", "Figure 2-10. Wiring diagram", 305, 319, x=(137, 474))
    result = _run([page])
    assert _by_type(result, "picture")[0].caption_link is not None
    assert _by_text(result, "Figure 2-10. Wiring diagram").flags == ["caption_relinked"]


def test_caption_with_no_candidate_is_ambiguous() -> None:
    page = SynPage(5).text("caption", "Figure 7. Missing drawing", 100, 112)
    assert "caption_ambiguous" in _codes(_run([page]))


def test_table_caption_links_to_nearest_table() -> None:
    page = SynPage(6).text("caption", "Table 3. Ports", 100, 112, x=(200, 400))
    page.table([["Port", "Functions"], ["CN1", "Input"]], top=118, cols=[(90, 200), (220, 540)])
    result = _run([page])
    table = _by_type(result, "table_segment")[0]
    assert table.caption_element_id == _by_text(result, "Table 3. Ports").element_id


# ------------------------------------------------------------------ ca thật

def _f54() -> tuple[RunResult, RunResult]:
    docs = f54_docs()
    pages = sorted(int(next(iter(d["pages"]))) for d in docs)
    words = load_words(F54_DIR, pages)
    with_objects = run_normalization(docs, "f54", DEFAULT, words, None, load_objects(F54_DIR, pages))
    return with_objects, run_normalization(f54_docs(), "f54", DEFAULT, words)


def test_f54_figures() -> None:
    result, without = _f54()
    by_id = {e.element_id: e for e in result.normalized or []}
    p9 = by_id["f54:p009:e003"].image
    assert p9 is not None and p9.crop_bbox.x0 <= 54.8 and p9.crop_bbox.x1 >= 561.7   # bitmap gồm "4 - M4"
    assert by_id["f54:p011:e006"].parent_element_id == "f54:p011:e004"                 # Figure 5
    assert by_id["f54:p018:e010"].normalized_type == "screenshot"                      # Figure 15
    assert by_id["f54:p171:e003"].normalized_type == "watermark_candidate"
    assert {"empty_table", "caption_ambiguous", "watermark_conflict"}.isdisjoint(_codes(result))
    assert all(v.passed for v in result.validation)
    assert [table_hash(t) for t in result.tables.tables] == [table_hash(t) for t in without.tables.tables]


def test_f86_dimension_labels_outside_pictures_become_figure_text() -> None:
    result = run_normalization(load_raw_dir(F86_DIR), "f86", load_profile("qs_controller"), None,
                               load_s0(F86_DIR))
    labels = {e.element_id: e for e in result.normalized or [] if e.text == "320 mm"}
    assert labels["f86:p008:e001"].parent_element_id == "f86:p008:e002"
    assert labels["f86:p009:e004"].parent_element_id == "f86:p009:e005"
    assert all(e.normalized_type == "figure_text" for e in labels.values())
    assert "furniture_unconfirmed" not in {r.code for r in result.tables.review if r.element_id in labels}
    relinked = [e.text for e in result.normalized or [] if "caption_relinked" in e.flags]
    assert len(relinked) == 2 and all(t and t.startswith("Figure 2-1") for t in relinked)    # p17: Docling không gắn


F54_PDF = Path(__file__).resolve().parents[3] / "docs" / "ai" / "doc_ingest_spike" / "source" / \
    "F54_Operation Manual (English Version)_V.02.pdf"


@pytest.mark.skipif(importlib.util.find_spec("pypdfium2") is None or not F54_PDF.is_file(),
                    reason="cần pypdfium2 (.venv-ingest) và PDF F54 trong docs/ai/doc_ingest_spike/source/")
def test_render_crops_writes_original_and_preview(tmp_path: Path) -> None:
    from app.modules.doc_ingest.parse.docling_runner import extract_objects, render_crops
    from app.modules.doc_ingest.pipeline import apply_rendered

    assert extract_objects(F54_PDF, [9])[9]["bitmaps"] == load_objects(F54_DIR, [9])[9]["bitmaps"]
    result = run_normalization(f54_docs({9}), "f54", DEFAULT, None, None, load_objects(F54_DIR, [9]))
    apply_rendered(result, render_crops(F54_PDF, crop_requests(result), tmp_path))
    image = next(e.image for e in result.normalized or [] if e.image is not None)
    assert image.original_path == "normalized/images/f54_p009_e003/original.png"
    assert (tmp_path / image.original_path).is_file() and (tmp_path / (image.preview_path or "")).is_file()
    assert image.scale is not None and 3.0 <= image.scale <= 4.0
    assert image.px_w is not None and abs(image.px_w - (image.crop_bbox.x1 - image.crop_bbox.x0) * image.scale) <= 2
