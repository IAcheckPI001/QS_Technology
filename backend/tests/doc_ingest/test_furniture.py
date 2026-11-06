"""T-17 xác nhận header/footer và chữ trong hình (I-21): luật chung, chạy trên SYN và F86 OCR."""
from pathlib import Path

from app.modules.doc_ingest.pipeline import RunResult, load_raw_dir, load_s0, run_normalization
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.normalized import NormalizedElement
from tests.doc_ingest.synthetic import SynPage

DEFAULT = load_profile("default")
F86_DIR = Path(__file__).resolve().parent / "fixtures" / "docling" / "f86_ocr"
FOOTER, HEADER = 760.0, 20.0     # trong dải dưới / trên (12% của 792 pt)


def _pages(numbers: range | list[int]) -> list[SynPage]:
    return [SynPage(n).text("text", f"Body text on page {n}", 300) for n in numbers]


def _run(pages: list[SynPage], profile=DEFAULT) -> RunResult:
    return run_normalization([p.to_doc() for p in pages], "syn", profile)


def _element(result: RunResult, text: str) -> NormalizedElement:
    return next(e for e in result.normalized or [] if e.text == text)


def _codes(result: RunResult) -> list[str]:
    return [r.code for r in result.tables.review]


def test_footer_repeated_on_three_pages_is_furniture_without_review() -> None:
    pages = _pages(range(1, 4))
    for p in pages:
        p.text("page_footer", "ACME CO.,LTD", FOOTER, x=(35, 200))
    result = _run(pages)
    footers = [e for e in result.normalized or [] if e.text == "ACME CO.,LTD"]
    assert {(e.content_layer, e.normalized_type, tuple(e.flags)) for e in footers} == {
        ("furniture", "furniture", ("furniture_repeated",))}
    assert [(k.band, k.key, k.pages) for k in result.furniture_keys or []] == [("bottom", "acme co.,ltd", [1, 2, 3])]
    assert not {"furniture_reclassified", "furniture_unconfirmed"} & set(_codes(result))


def test_digits_count_as_equal_so_page_numbers_repeat() -> None:
    pages = _pages(range(5, 8))
    for p in pages:
        p.text("page_footer", f"PAGE{p.page - 2}", FOOTER, x=(514, 560))   # OCR: `PAGE3`
    result = _run(pages)
    assert [k.key for k in result.furniture_keys or []] == ["page #"]


def test_line_merged_from_repeated_strings_is_furniture() -> None:
    pages = _pages(range(1, 5))
    for p in pages[:3]:
        p.text("page_footer", "ACME CO.,LTD", FOOTER, x=(35, 200)).text("page_footer", f"PAGE {p.page}", FOOTER,
                                                                         x=(514, 560))
    pages[3].text("page_footer", "ACME CO.,LTD PAGE 4", FOOTER, x=(35, 560))
    result = _run(pages)
    assert _element(result, "ACME CO.,LTD PAGE 4").flags == ["furniture_composed"]
    assert "furniture_unconfirmed" not in _codes(result)


def test_unique_numbered_page_header_returns_to_body_as_heading() -> None:
    result = _run([SynPage(7).text("page_header", "1.1 APPERANCE", HEADER).text("text", "Front view", 300)])
    heading = _element(result, "1.1 APPERANCE")
    assert (heading.content_layer, heading.normalized_type) == ("body", "heading")
    assert heading.flags == ["furniture_demoted", "section_parent_missing"]     # trang chỉ có 1.1
    assert heading.section_path == ["1.1 APPERANCE"]
    assert _element(result, "Front view").section_path == ["1.1 APPERANCE"]
    [item] = [r for r in result.tables.review if r.code == "furniture_reclassified"]
    assert (item.blocking, item.element_id) == (False, heading.element_id)


def test_unique_non_heading_header_stays_furniture_and_is_flagged() -> None:
    result = _run([SynPage(8).text("page_header", "320 mm", HEADER + 10)])
    dim = _element(result, "320 mm")
    assert (dim.content_layer, dim.flags) == ("furniture", ["furniture_unconfirmed"])
    [item] = [r for r in result.tables.review if r.code == "furniture_unconfirmed"]
    assert not item.blocking


def test_body_text_repeated_in_band_is_promoted_to_furniture() -> None:
    pages = _pages(range(1, 4))
    for p in pages:
        p.text("text", "www.example.com", FOOTER)
    result = _run(pages)
    promoted = [e for e in result.normalized or [] if e.text == "www.example.com"]
    assert all(e.content_layer == "furniture" and e.flags == ["furniture_repeated", "furniture_promoted"]
               for e in promoted)
    assert all(e.content_layer == "body" for e in result.normalized or [] if e.text.startswith("Body text"))


def test_repeated_heading_label_is_not_promoted() -> None:
    pages = _pages(range(1, 4))
    for p in pages:
        p.text("section_header", "Notes:", HEADER)
    result = _run(pages)
    assert all(e.content_layer == "body" for e in result.normalized or [] if e.text == "Notes:")


def test_text_inside_picture_is_figure_text_not_furniture_or_heading() -> None:
    page = SynPage(15).text("section_header", "2.2 SENSOR", 150)
    pic = page.picture(200, 500)
    page.text("page_header", "QS TECHNOLOGY", 220, parent=pic).text("section_header", "i-    ns    dpn", 300,
                                                                     parent=pic)
    result = _run([page])
    logo, junk = _element(result, "QS TECHNOLOGY"), _element(result, "i-    ns    dpn")
    picture = next(e for e in result.normalized or [] if e.normalized_type == "picture")
    for e in (logo, junk):
        assert (e.content_layer, e.normalized_type, e.parent_element_id) == ("body", "figure_text",
                                                                              picture.element_id)
    assert junk.section_path == ["2.2 SENSOR"]
    assert not {"furniture_reclassified", "furniture_unconfirmed"} & set(_codes(result))


def test_profile_pattern_covers_runs_too_short_to_repeat() -> None:
    pages = _pages(range(1, 3))
    for p in pages:
        p.text("page_footer", "ACME CO.,LTD", FOOTER)
    assert _codes(_run(pages)).count("furniture_unconfirmed") == 2
    profile = DEFAULT.model_copy(update={"furniture_patterns": [r"ACME CO\.,LTD"]})
    result = _run(pages, profile)
    assert {tuple(e.flags) for e in result.normalized or [] if e.text == "ACME CO.,LTD"} == {("furniture_pattern",)}
    assert "furniture_unconfirmed" not in _codes(result)


def test_f86_ocr_headings_tagged_as_page_header_return_to_body() -> None:
    raw = load_raw_dir(F86_DIR)
    result = run_normalization(raw, "f86", load_profile("qs_controller"), None, load_s0(F86_DIR))
    by_text = {e.text: e for e in result.normalized or [] if e.content_layer == "body"}
    for text in ("1.1 APPERANCE", "1.2 DIMENSION", "CHAPTER 2.", "2.1 POWER SUPPLY", "2.3.3 6-WIRE-NPN TYPE"):
        assert by_text[text].normalized_type == "heading" and "furniture_demoted" in by_text[text].flags, text
    assert by_text["2.1 POWER SUPPLY"].section_path == ["CHAPTER 2.", "2.1 POWER SUPPLY"]
    assert {k.example for k in result.furniture_keys or []} >= {"QS TECHNOLOGY CO.,LTD"}
    assert "page #" in {k.key for k in result.furniture_keys or []}
    furniture = {e.text for e in result.normalized or [] if e.content_layer == "furniture"}
    assert {"QS TECHNOLOGY CO.,LTD", "PAGE 5", "QS TECHNOLOGY CO.,LTD PAGE 4"} <= furniture
    assert "320 mm" not in furniture       # nhãn kích thước sát hình: T-18 gắn vào hình (test_figures)
    figure = [e for e in result.normalized or [] if e.normalized_type == "figure_text"]
    assert len(figure) > 300 and all(e.parent_element_id for e in figure)
    assert "i-    ns    dpn" not in {e.text for e in result.normalized or [] if e.normalized_type == "heading"}
