"""T-07 section path theo số đánh; heading không đánh số là label_heading."""
import pytest

from app.modules.doc_ingest.normalize.sections import parse_heading
from app.modules.doc_ingest.pipeline import run_normalization
from app.modules.doc_ingest.profile import load_profile
from tests.doc_ingest.f54 import f54_docs
from tests.doc_ingest.synthetic import SynPage

DEFAULT = load_profile("default")


@pytest.mark.parametrize(("text", "numbers", "strong"), [
    ("1.2 Dimension", (1, 2), True), ("CHAPTER 2.", (2,), True), ("PART 2: WIRING - CONNECTION", (2,), True),
    ("chương 3 Lắp đặt", (3,), True), ("PART 1:CONTROLLER OVERVIEW", (1,), True), ("2.9.1AXIS", (2, 9, 1), True), ("3 Installation", (3,), False),
    ("320 mm", (320,), False),
])
def test_parse_heading(text: str, numbers: tuple[int, ...], strong: bool) -> None:
    heading = parse_heading(text, DEFAULT)
    assert heading is not None and (heading.numbers, heading.strong) == (numbers, strong)


@pytest.mark.parametrize("text", ["Notes:", "1.2 3", "Figure 1-1. Front view", "320", "PART 1.2 X"])
def test_not_a_numbered_heading(text: str) -> None:
    assert parse_heading(text, DEFAULT) is None


def _paths() -> dict[str, tuple[str, list[str], str, list[str]]]:
    p1 = (SynPage(1).text("section_header", "CHAPTER 2.", 60).text("section_header", "2.1 POWER", 100)
          .text("text", "Supply 24V", 130).text("section_header", "Note:", 160).text("text", "Use a fuse", 190))
    p2 = (SynPage(2).text("text", "Continued text", 60).text("section_header", "2.2.1 HIGH", 100)
          .text("section_header", "2.9.1AXIS", 140).text("section_header", "3.1 OTHER", 180))
    result = run_normalization([p1.to_doc(), p2.to_doc()], "syn", DEFAULT)
    return {e.text: (e.normalized_type, e.section_path, e.section_path_source, e.flags)
            for e in result.normalized or [] if e.text}


def test_numbering_opens_and_closes_levels_across_pages() -> None:
    paths = _paths()
    assert paths["CHAPTER 2."] == ("heading", ["CHAPTER 2."], "numbering", [])
    assert paths["2.1 POWER"][1] == ["CHAPTER 2.", "2.1 POWER"]
    assert paths["Supply 24V"][1:3] == (["CHAPTER 2.", "2.1 POWER"], "inherited")
    assert paths["Continued text"][1] == ["CHAPTER 2.", "2.1 POWER"]
    assert paths["2.2.1 HIGH"] == ("heading", ["CHAPTER 2.", "2.2.1 HIGH"], "numbering", ["section_parent_missing"])
    assert paths["3.1 OTHER"][1] == ["3.1 OTHER"]


def test_unnumbered_heading_is_label_heading_and_keeps_path() -> None:
    result = run_normalization([SynPage(1).text("section_header", "2.1 POWER", 60)
                                .text("section_header", "Note:", 100).text("text", "Use a fuse", 130).to_doc()],
                               "syn", DEFAULT)
    by_text = {e.text: e for e in result.normalized or []}
    assert (by_text["Note:"].normalized_type, by_text["Note:"].section_path) == ("label_heading", ["2.1 POWER"])
    assert (by_text["Use a fuse"].label_heading, by_text["Use a fuse"].section_path) == ("Note:", ["2.1 POWER"])


def test_glued_ocr_number_is_accepted_with_flag() -> None:
    assert "heading_spacing" in _paths()["2.9.1AXIS"][3]


def test_before_any_heading_path_source_is_none() -> None:
    result = run_normalization([SynPage(1).text("text", "Intro", 60).to_doc()], "syn", DEFAULT)
    [element] = result.normalized or []
    assert (element.section_path, element.section_path_source) == ([], "none")


def _page_with_late_figure(x: tuple[float, float] = (85.0, 500.0), stray_above: bool = False) -> list:
    """Trang: ghi chú cuối mục trước (y=220), heading 2.4.4 (y=300), đoạn văn; hình + caption ở đầu trang (y=60–210)
    nhưng Docling xếp cuối trang (F54 trang 44, Figure 52)."""
    from app.modules.doc_ingest.normalize.docling_reader import read_items

    page = SynPage(1).text("text", "Note: terminals", 220).text("section_header", "2.4.4 Y43 output", 300)
    page.text("text", "From the Y43 pin", 330)
    if stray_above:
        page.text("text", "Side text at top", 40, x=(85.0, 500.0))
    page.picture(60, 190, x=x)
    page.text("caption", "Figure 52. Motor wiring", 200, 210, x=x)
    return read_items([page.to_doc()], "syn")


def _order(items) -> list[str]:
    return [i.text or i.label for i in items]


def test_figure_above_heading_moves_to_previous_section() -> None:
    """T-07 (I-40a): hình nằm trên heading nhưng xếp sau → lên trước phần tử đầu tiên nằm dưới nó, thuộc mục trước."""
    from app.modules.doc_ingest.normalize.recorder import Recorder
    from app.modules.doc_ingest.normalize.sections import fix_figures_above_heading

    items, flags = fix_figures_above_heading(_page_with_late_figure(), {1}, DEFAULT, Recorder())
    assert _order(items) == ["picture", "Figure 52. Motor wiring", "Note: terminals", "2.4.4 Y43 output",
                             "From the Y43 pin"]
    assert sorted(flags) == sorted(i.element_id for i in items[:2])
    assert all(f == ["reading_order_fixed"] for f in flags.values())


@pytest.mark.parametrize("case", ["ocr_page", "other_column", "stray_above"])
def test_figure_above_heading_kept_when_rule_does_not_apply(case: str) -> None:
    from app.modules.doc_ingest.normalize.recorder import Recorder
    from app.modules.doc_ingest.normalize.sections import fix_figures_above_heading

    raw = _page_with_late_figure(x=(85.0, 500.0) if case != "other_column" else (505.0, 590.0),
                                 stray_above=case == "stray_above")
    items, flags = fix_figures_above_heading(raw, set() if case == "ocr_page" else {1}, DEFAULT, Recorder())
    assert _order(items) == _order(raw) and not flags


def test_f54_part_and_numbered_sections() -> None:
    result = run_normalization(f54_docs({167, 168, 169}), "f54", DEFAULT)
    headings = [(e.text, e.section_path) for e in result.normalized or [] if e.normalized_type == "heading"]
    assert headings == [("PART 5 PARAMETERS TABLE", ["PART 5 PARAMETERS TABLE"]),
                        ("5.1 Axis parameters", ["PART 5 PARAMETERS TABLE", "5.1 Axis parameters"]),
                        ("5.2 Spindle parameters", ["PART 5 PARAMETERS TABLE", "5.2 Spindle parameters"])]
    table = next(e for e in result.normalized or [] if e.pdf_page_index == 168 and e.normalized_type == "table_segment")
    assert table.section_path == ["PART 5 PARAMETERS TABLE", "5.1 Axis parameters"] and table.table_ref is not None
