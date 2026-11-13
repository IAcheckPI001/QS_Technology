"""T-20 khung chữ (I-36) và chép verdict duyệt khi build lại (`build --carry-review`)."""
from __future__ import annotations

from pathlib import Path

from app.modules.doc_ingest.build.builder import CarrySource, carry_review
from app.modules.doc_ingest.pipeline import RunResult, run_normalization
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.chunk import ChunkReviewEntry, ChunkReviewFile
from app.modules.doc_ingest.schemas.normalized import NormalizedElement
from app.modules.doc_ingest.schemas.run import DocumentProfile, PageProfile
from tests.doc_ingest.chunk_helpers import Doc, build
from tests.doc_ingest.synthetic import SynPage

PROFILE = load_profile("qs_controller")
LEFT, RIGHT = (85.0, 300.0), (350.0, 556.0)


def _s0(page: int, ocr: bool = False) -> DocumentProfile:
    return DocumentProfile(ocr_mode="auto", page_labels_present=False, pages=[PageProfile(
        page=page, text_chars=0 if ocr else 900, bad_char_ratio=0.0, rotation=0, bitmap_area_ratio=0.3,
        vector_path_count=10, text_layer="missing" if ocr else "ok", ocr=ocr, ocr_applied=ocr)])


def _page() -> SynPage:
    """Bố cục F54 PART 4: cột trái "Description images" (ảnh), cột phải "Instructions" bị Docling nhận là picture."""
    page = SynPage(115).text("section_header", "4.3.3 Go to any command line", 80)
    desc = page.picture(100, 600, x=LEFT)
    page.text("section_header", "Description images", 105, parent=desc, x=LEFT)
    page.text("text", "Model: F54", 120, parent=desc, x=LEFT)
    frame = page.picture(100, 650, x=RIGHT)
    page.text("section_header", "Instructions", 110, parent=frame, x=RIGHT)
    page.text("text", "Model: F54", 125, parent=frame, x=RIGHT)
    page.text("section_header", "Step 1:", 140, parent=frame, x=RIGHT)
    page.text("text", "From the editing screen, press the right arrow button.", 160, parent=frame, x=RIGHT)
    page.text("caption", "Step 2: Press GO TO LINE button", 360, parent=frame, x=RIGHT)
    page.text("caption", "Figure 9. GO TO LINE screen", 600, parent=frame, x=RIGHT)
    return page


def _run(s0: DocumentProfile | None) -> RunResult:
    return run_normalization([_page().to_doc()], "f54", PROFILE, s0=s0)


def _all(result: RunResult, text: str) -> list[NormalizedElement]:
    return [e for e in result.normalized or [] if e.text == text]


def _pictures(result: RunResult) -> list[NormalizedElement]:
    return [e for e in result.normalized or [] if e.normalized_type in ("picture", "screenshot")]


def test_instruction_frame_on_text_layer_page_returns_text_to_body() -> None:
    result = _run(_s0(115))
    desc, frame = _pictures(result)
    assert "text_frame" in frame.flags and "text_frame" not in desc.flags
    for text in ("Step 1:", "From the editing screen, press the right arrow button."):
        [e] = _all(result, text)
        assert e.normalized_type not in ("figure_text", "caption") and e.parent_element_id is None
        assert "frame_text_released" in e.flags
        assert e.section_path == ["4.3.3 Go to any command line"]
    order = [e.text for e in result.normalized or [] if "frame_text_released" in e.flags]
    assert order == ["Step 1:", "From the editing screen, press the right arrow button.",
                     "Step 2: Press GO TO LINE button"]   # thứ tự đọc, caption bước không bị kéo lên cạnh hình
    # Tiêu đề khung lặp ở mỗi khung: vẫn là chữ trong hình (không cắt chuỗi bước, không gắn T-18 lại).
    [title] = _all(result, "Instructions")
    assert (title.normalized_type, title.parent_element_id) == ("figure_text", frame.element_id)
    model_frame = [e for e in _all(result, "Model: F54") if e.parent_element_id == frame.element_id]
    assert len(model_frame) == 1 and model_frame[0].normalized_type == "figure_text"


def test_image_frame_without_sentence_or_step_keeps_figure_text() -> None:
    result = _run(_s0(115))
    desc, _ = _pictures(result)
    [label] = _all(result, "Description images")
    assert (label.normalized_type, label.parent_element_id) == ("figure_text", desc.element_id)
    model_desc = [e for e in _all(result, "Model: F54") if e.parent_element_id == desc.element_id]
    assert len(model_desc) == 1 and model_desc[0].normalized_type == "figure_text"


def test_step_caption_becomes_text_but_figure_caption_stays() -> None:
    result = _run(_s0(115))
    [step] = _all(result, "Step 2: Press GO TO LINE button")
    assert step.normalized_type != "caption" and "frame_text_released" in step.flags
    [figure] = _all(result, "Figure 9. GO TO LINE screen")
    assert figure.normalized_type == "caption" and "frame_text_released" not in figure.flags


def test_diagram_with_label_fragments_is_not_a_frame() -> None:
    """F54 trang 50: sơ đồ có heading bị nuốt + hàng chục mảnh "(" ")" — không phải khung chữ."""
    page = SynPage(50).text("section_header", "2.5.1 I/O link board wiring diagram", 80)
    pic = page.picture(100, 700)
    page.text("section_header", "2.5.1.1 I/O Link board wiring diagram (LOW INPUT)", 110, parent=pic)
    for i in range(20):
        page.text("text", "(" if i % 2 == 0 else ")", 150 + i * 20, parent=pic)
    result = run_normalization([page.to_doc()], "f54", PROFILE, s0=_s0(50))
    assert not [e for e in result.normalized or [] if "frame_text_released" in e.flags]


def test_step_caption_of_ordinary_screenshot_does_not_make_a_frame() -> None:
    """F54 trang 95: ảnh chụp màn hình có caption "Step 1: …" và một mảnh chữ — giữ nguyên như cũ."""
    page = SynPage(95).text("section_header", "3.1 Auto home", 80)
    pic = page.picture(100, 400)
    page.text("text", "achine", 200, parent=pic)
    page.text("caption", "Step 1: On the main screen, select MANUAL MODE button.", 410, parent=pic)
    result = run_normalization([page.to_doc()], "f54", PROFILE, s0=_s0(95))
    assert not [e for e in result.normalized or [] if "frame_text_released" in e.flags]
    [junk] = _all(result, "achine")
    assert junk.normalized_type == "figure_text"


def test_frame_with_title_and_only_step_caption_is_a_frame() -> None:
    """I-44, F54 trang 153: khung "Instructions" + "Model: …" + caption "Step 3: …" (không còn chữ thân) là khung chữ;
    ảnh chụp màn hình chỉ có caption bước mà không có tiêu đề khung thì không."""
    page = SynPage(153).text("section_header", "4.10.2 Date & Time setting", 60)
    frame = page.picture(66, 636, x=RIGHT)
    page.text("section_header", "Instructions", 80, parent=frame, x=RIGHT)
    page.text("text", "Model: F54, F86, Astro 6A, Astro 10i", 95, parent=frame, x=RIGHT)
    page.text("caption", "Step 3: Set the time value, then press the SET TIME button.", 120, parent=frame, x=RIGHT)
    shot = page.picture(66, 600, x=LEFT)
    page.text("caption", "Step 4: Press the SAVE button.", 610, parent=shot, x=LEFT)
    result = run_normalization([page.to_doc()], "f54", PROFILE, s0=_s0(153))
    framed = [e for e in _pictures(result) if "text_frame" in e.flags]
    assert len(framed) == 1 and framed[0].bbox is not None and framed[0].bbox.x0 >= RIGHT[0] - 1
    [step] = _all(result, "Step 3: Set the time value, then press the SET TIME button.")
    assert step.normalized_type != "caption" and "frame_text_released" in step.flags
    [other] = _all(result, "Step 4: Press the SAVE button.")
    assert "frame_text_released" not in other.flags


def test_ocr_page_or_missing_s0_does_not_release() -> None:
    for s0 in (_s0(115, ocr=True), None):
        result = _run(s0)
        [step] = _all(result, "Step 1:")
        assert step.normalized_type == "figure_text"
        assert all("text_frame" not in p.flags for p in _pictures(result))
        assert not [e for e in result.normalized or [] if "frame_text_released" in e.flags]


def _loose_page() -> SynPage:
    """F54 trang 100: Docling chỉ gom khung ảnh; tiêu đề khung "Instructions" + "Model: F54" nằm ngoài picture."""
    page = SynPage(100).text("section_header", "3.4 Start program from any line", 80)
    desc = page.picture(100, 600, x=LEFT)
    page.text("section_header", "Description images", 105, parent=desc, x=LEFT)
    page.text("section_header", "Instructions", 110, x=RIGHT)
    page.text("text", "Model: F54", 125, x=RIGHT)
    page.text("section_header", "Step 1:", 140, x=RIGHT)
    page.text("text", "Ex: We want to run program from line 100.", 160, x=RIGHT)
    return page


def test_loose_frame_title_and_model_line_become_figure_text() -> None:
    """I-37: nhãn khung không được gom không vào text thân và không cắt chuỗi bước."""
    result = run_normalization([_loose_page().to_doc()], "f54", PROFILE, s0=_s0(100))
    [desc] = _pictures(result)
    for text in ("Instructions", "Model: F54"):
        [e] = _all(result, text)
        assert (e.normalized_type, e.parent_element_id) == ("figure_text", desc.element_id)
        assert "frame_label_attached" in e.flags
    [step] = _all(result, "Ex: We want to run program from line 100.")
    assert step.normalized_type == "text" and step.label_heading == "Step 1:"
    assert [log.rule_id for log in result.tables.log if log.rule_id == "T-20"] == ["T-20", "T-20"]


def test_loose_frame_title_needs_model_line_text_page_and_picture() -> None:
    # "Instructions:" + danh sách là nội dung thật (F54 trang 111).
    page = SynPage(111).text("section_header", "4.3 Program screen", 80)
    page.picture(100, 300)
    page.text("section_header", "Instructions:", 320).text("list_item", "Execute program (4.3.2)", 340)
    result = run_normalization([page.to_doc()], "f54", PROFILE, s0=_s0(111))
    [title] = _all(result, "Instructions:")
    assert title.normalized_type == "label_heading" and not title.flags
    # Trang OCR và trang không có picture: không đổi.
    ocr = run_normalization([_loose_page().to_doc()], "f54", PROFILE, s0=_s0(100, ocr=True))
    assert _all(ocr, "Instructions")[0].normalized_type == "label_heading"
    bare = SynPage(100).text("section_header", "Instructions", 110).text("text", "Model: F54", 125)
    result = run_normalization([bare.to_doc()], "f54", PROFILE, s0=_s0(100))
    assert [e.normalized_type for e in result.normalized or []] == ["label_heading", "text"]


def test_model_line_right_above_picture_becomes_its_figure_text() -> None:
    """F54 trang 105: "Model: F54 controller" là tiêu đề khung của ảnh màn hình ngay dưới."""
    page = SynPage(105).text("section_header", "4.2 Coordinate screen", 80)
    page.text("text", "On the coordinate screen, the user can view the machine coordinates.", 100)
    page.text("section_header", "Model: F54 controller", 130)
    page.picture(150, 500)
    page.text("text", "Model: F54 is the controller described in this manual.", 520)
    result = run_normalization([page.to_doc()], "f54", PROFILE, s0=_s0(105))
    [picture] = _pictures(result)
    [label] = _all(result, "Model: F54 controller")
    assert (label.normalized_type, label.parent_element_id) == ("figure_text", picture.element_id)
    assert picture.label_heading is None            # ảnh thuộc khối mô tả phía trước, không mở khối mới
    [sentence] = _all(result, "Model: F54 is the controller described in this manual.")
    assert sentence.normalized_type == "text"       # dòng model không đứng ngay trên hình: giữ nguyên
    # F54 trang 148: ảnh chụp màn hình là bảng Docling 0 cell.
    page = SynPage(148).text("section_header", "Model: F54 controller", 100)
    page.empty_table(120, 400)
    result = run_normalization([page.to_doc()], "f54", PROFILE, s0=_s0(148))
    [label] = _all(result, "Model: F54 controller")
    assert label.normalized_type == "figure_text" and "frame_label_attached" in label.flags


def test_carry_review_matches_by_hash_and_section_not_key(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("heading", "3 Setup", path=("3 Setup",))
    doc.add("text", "Short overview of the setup section.", path=("3 Setup",))
    doc.add("label_heading", "How to set:", path=("3 Setup",), label="How to set:")
    doc.add("list_item", "Press A.", path=("3 Setup",), label="How to set:", depth=0)
    old = build(doc, tmp_path).chunks
    review = ChunkReviewFile(doc_id="d", reviews=[
        ChunkReviewEntry(chunk_key=c.chunk_key, content_hash=c.content_hash, verdict="ok", note=f"n{i}", reviewer="r")
        for i, c in enumerate(old)])
    review.reviews[-1] = review.reviews[-1].model_copy(update={"verdict": "fix"})
    # Bộ mới: thêm một chunk ở đầu (key dịch), sửa nội dung chunk cuối, đổi mục của một chunk.
    extra = old[0].model_copy(update={"content_hash": "new", "section_path": ["0 Intro"]})
    shifted = [c.model_copy(update={"chunk_key": f"d:B{i + 1:04d}", "chunk_index": i + 1}) for i, c in enumerate(old)]
    shifted[-1] = shifted[-1].model_copy(update={"content_hash": "edited"})
    new = [extra.model_copy(update={"chunk_key": "d:B0000", "chunk_index": 0}), *shifted]
    out, carried = carry_review(new, "d", CarrySource(review=review, chunks=old))
    assert carried == len(old) - 1
    assert [e.chunk_key for e in out.reviews] == [c.chunk_key for c in new]
    assert out.reviews[0].verdict == "pending" and out.reviews[-1].verdict == "pending"   # mới / đã đổi
    assert [e.note for e in out.reviews[1:-1]] == [f"n{i}" for i in range(len(old) - 1)]
    assert all(e.content_hash == c.content_hash for e, c in zip(out.reviews, new))
    moved = [shifted[0].model_copy(update={"section_path": ["9 Other"]})]
    assert carry_review(moved, "d", CarrySource(review=review, chunks=old))[1] == 0


def test_carry_review_skips_stale_and_pending_entries(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("heading", "3 Setup", path=("3 Setup",))
    doc.add("text", "Short overview of the setup section.", path=("3 Setup",))
    old = build(doc, tmp_path).chunks
    stale = ChunkReviewFile(doc_id="d", reviews=[
        ChunkReviewEntry(chunk_key=old[0].chunk_key, content_hash="older", verdict="ok")])
    assert carry_review(old, "d", CarrySource(review=stale, chunks=old))[1] == 0
    pending = ChunkReviewFile(doc_id="d", reviews=[
        ChunkReviewEntry(chunk_key=old[0].chunk_key, content_hash=old[0].content_hash)])
    assert carry_review(old, "d", CarrySource(review=pending, chunks=old))[1] == 0
    assert carry_review(old, "d", None)[1] == 0
