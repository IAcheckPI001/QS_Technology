"""T-20b (I-59): khung chữ hướng dẫn "Memo" trên trang OCR (Giai đoạn 1 kế hoạch fix, 2026-11-25)."""
from __future__ import annotations

from app.modules.doc_ingest.pipeline import RunResult, run_normalization
from app.modules.doc_ingest.profile import load_profile
from tests.doc_ingest.synthetic import SynPage
from tests.doc_ingest.test_text_frames import _all, _pictures, _s0

PROFILE = load_profile("qs_controller")
LEFT, RIGHT = (36.0, 323.0), (335.0, 576.0)


def _memo_page() -> SynPage:
    """10iV trang 52: ảnh chụp màn hình bên trái và khung "Memo" bên phải là hai picture riêng."""
    page = SynPage(52).text("section_header", "3.2.1 SWITCH SCREEN", 126)
    shot = page.picture(138, 709, x=LEFT)
    for i, label in enumerate(("Coordinate", "Machine", "Absolute", "Jog")):
        page.text("text", label, 190 + 12 * i, parent=shot, x=LEFT)
    memo = page.picture(138, 709, x=RIGHT)
    page.text("section_header", "Memo", 141, parent=memo, x=RIGHT)
    page.text("text", "Model: ASTRO 10I", 157, parent=memo, x=RIGHT)
    page.text("section_header", "Step 1:", 183, parent=memo, x=RIGHT)
    page.text("text", "From the main screen, select COORD button.", 210, parent=memo, x=RIGHT)
    page.text("section_header", "Step 2:", 446, parent=memo, x=RIGHT)
    page.text("text", "Press FULL SCREEN button.", 473, parent=memo, x=RIGHT)
    page.text("section_header", "Note:", 494, parent=memo, x=RIGHT)
    page.text("text", "Coordinate systems arrangement:", 521, parent=memo, x=RIGHT)
    return page


def _run(page: SynPage, ocr: bool = True) -> RunResult:
    return run_normalization([page.to_doc()], "10iv", PROFILE, s0=_s0(page.page, ocr=ocr))


def _released(result: RunResult) -> list[str]:
    return [e.text for e in result.normalized or [] if "frame_text_released" in e.flags]


def test_memo_panel_on_ocr_page_returns_steps_to_body() -> None:
    result = _run(_memo_page())
    assert _released(result) == ["Step 1:", "From the main screen, select COORD button.", "Step 2:",
                                 "Press FULL SCREEN button.", "Note:", "Coordinate systems arrangement:"]
    framed = [p for p in _pictures(result) if "text_frame_ocr" in p.flags]
    assert len(framed) == 1 and framed[0].bbox is not None and framed[0].bbox.x0 >= RIGHT[0] - 1
    # Tiêu đề khung và dòng model vẫn là chữ trong hình; nhãn của ảnh màn hình bên trái không đổi.
    assert _all(result, "Memo")[0].normalized_type == "figure_text"
    assert _all(result, "Model: ASTRO 10I")[0].normalized_type == "figure_text"
    assert _all(result, "Machine")[0].normalized_type == "figure_text"


def test_same_page_with_text_layer_is_unchanged_and_flag_is_plain_text_frame() -> None:
    result = _run(_memo_page(), ocr=False)
    assert _released(result)[0] == "Step 1:"
    assert [p for p in _pictures(result) if "text_frame" in p.flags and "text_frame_ocr" not in p.flags]
    assert not [p for p in _pictures(result) if "text_frame_ocr" in p.flags]


def test_one_picture_covering_screenshot_and_memo_releases_only_the_step_column() -> None:
    """F54 trang 78: một picture phủ ảnh màn hình (trái) và cột Memo (phải); chữ của màn hình ở lại là figure_text."""
    page = SynPage(78).text("section_header", "3.10.1 System information", 80)
    pic = page.picture(40, 500, x=(36.0, 576.0))
    for i, label in enumerate(("HARDWARE", "NC Verison: 2.0.00", "HMI Verison: Integrate", "Free Space: 3708 Mbytes")):
        page.text("text", label, 100 + 12 * i, parent=pic, x=(160.0, 260.0))
    page.text("section_header", "Step 3:", 80, parent=pic, x=(314.0, 400.0))
    page.text("text", "Press DATA I/O button. You can select to load data.", 106, parent=pic, x=(315.0, 570.0))
    page.text("section_header", "Step 4:", 317, parent=pic, x=(315.0, 400.0))
    page.text("text", "Press PLC DATA button.", 344, parent=pic, x=(316.0, 570.0))
    result = _run(page)
    assert _released(result) == ["Step 3:", "Press DATA I/O button. You can select to load data.", "Step 4:",
                                 "Press PLC DATA button."]
    for text in ("HARDWARE", "NC Verison: 2.0.00", "HMI Verison: Integrate", "Free Space: 3708 Mbytes"):
        assert _all(result, text)[0].normalized_type == "figure_text"


def test_released_ocr_frame_text_does_not_shift_the_text_margin() -> None:
    from app.modules.doc_ingest.normalize.figures import text_margin
    from app.modules.doc_ingest.normalize.docling_reader import read_items

    page = _memo_page()
    for i in range(4):   # lề thân văn bản ở x0 = 35 (≥ 3 dòng)
        page.text("text", f"Body line number {i} of the page text.", 720 + i * 12, x=(35.0, 300.0))
    from app.modules.doc_ingest.normalize.figures import release_text_frames
    from app.modules.doc_ingest.normalize.recorder import Recorder

    items = read_items([page.to_doc()], "10iv")
    run = release_text_frames(items, set(), PROFILE, Recorder(), {page.page})
    assert any(i.frame_released for i in run.items)
    assert text_margin(run.items) == 35.0


def test_ocr_picture_with_sentences_but_no_step_label_is_not_a_frame() -> None:
    page = SynPage(60).text("section_header", "2.1 Power supply", 80)
    pic = page.picture(100, 500)
    page.text("text", "Power supply widely used in industry is a switching power supply.", 120, parent=pic)
    page.text("text", "The input voltage must be connected to the FG pin of the controller.", 160, parent=pic)
    result = _run(page)
    assert not _released(result)
    assert all(e.normalized_type == "figure_text" for e in result.normalized or [] if e.parent_element_id)


def test_ocr_screenshot_with_only_a_step_caption_is_not_a_frame() -> None:
    page = SynPage(95).text("section_header", "3.1 Auto home", 80)
    pic = page.picture(100, 400)
    page.text("text", "achine", 200, parent=pic)
    page.text("caption", "Step 1: On the main screen, select MANUAL MODE button.", 410, parent=pic)
    result = _run(page)
    assert not _released(result)
    [junk] = _all(result, "achine")
    assert junk.normalized_type == "figure_text"


def test_ocr_diagram_with_label_fragments_is_not_a_frame() -> None:
    page = SynPage(50).text("section_header", "2.5.1 I/O link board wiring diagram", 80)
    pic = page.picture(100, 700)
    for i in range(20):
        page.text("text", "(" if i % 2 == 0 else ")", 150 + i * 20, parent=pic)
    assert not _released(_run(page))
