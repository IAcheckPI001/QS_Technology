"""T-08 list cha–con v1 (contract T-08, sửa 2026-11-09): GT-07 trên F54 và ca tổng hợp."""
from __future__ import annotations

from app.modules.doc_ingest.pipeline import RunResult, list_summary, run_normalization
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.normalized import NormalizedElement
from tests.doc_ingest.f54 import f54_docs
from tests.doc_ingest.synthetic import SynPage

DEFAULT = load_profile("default")
L1, L2, L3 = 103.0, 139.0, 157.0   # lề F54: cấp 1, cấp 2 (glyph `o`), thêm một cấp


def _li(page: SynPage, text: str, top: float, x0: float, marker: str | None = None) -> SynPage:
    page.text("list_item", text, top, x=(x0, 500.0))
    if marker is not None:
        page.texts[-1]["marker"] = marker
    return page


def _run(*pages: SynPage) -> RunResult:
    return run_normalization([p.to_doc() for p in pages], "syn", DEFAULT)


def _by_text(result: RunResult) -> dict[str, NormalizedElement]:
    return {e.text: e for e in result.normalized or [] if e.text}


def _parent(result: RunResult, text: str) -> str | None:
    """Text của list_item cha (None nếu cấp 1)."""
    by_id = {e.element_id: e for e in result.normalized or []}
    info = _by_text(result)[text].list_info
    assert info is not None
    return by_id[info.parent_element_id].text if info.parent_element_id else None


def _codes(result: RunResult) -> list[tuple[str, str]]:
    by_id = {e.element_id: e for e in result.normalized or []}
    return [(r.code, by_id[r.element_id].text or "") for r in result.tables.review if r.code.startswith("list_")]


# ------------------------------------------------------------------ GT-07 (F54 trang 19)

def test_gt07_f54_page19_parents_and_children() -> None:
    result = run_normalization(f54_docs({19}), "f54", load_profile("qs_controller"))
    items = [e for e in result.normalized or [] if e.list_info is not None]
    parents = [e for e in items if (e.text or "").startswith("M19")]
    assert [p.text.split(":")[0] for p in parents if p.text] == ["M1920", "M1921", "M1922", "M1923"]
    for parent in parents:
        kids = [e for e in items if e.list_info and e.list_info.parent_element_id == parent.element_id]
        code = (parent.text or "").split(":")[0]
        assert [k.text.split(":")[0].strip() for k in kids if k.text] == [f"o {code} = 0", f"o {code} = 1"]
        assert all(k.list_info and k.list_info.depth == 1 and k.list_info.marker == "o" for k in kids)
        assert parent.list_info is not None and parent.list_info.depth == 0
    # text nguyên văn: con M1921 vẫn thiếu `)` như trong PDF
    assert "o M1921 = 0 : Normally closed sensor (NC" in [e.text for e in items]
    assert _codes(result) == []


# ------------------------------------------------------------------ luật cơ bản

def test_indent_at_least_18pt_is_child_without_glyph() -> None:
    page = SynPage(1)
    _li(page, "Parent", 100, L1)
    _li(page, "Deeper item", 120, L1 + 18)
    result = _run(page)
    assert _parent(result, "Deeper item") == "Parent"
    info = _by_text(result)["Deeper item"].list_info
    assert info is not None and (info.depth, info.marker, info.indent_x) == (1, None, L1 + 18)


def test_glyph_makes_child_only_with_small_indent() -> None:
    page = SynPage(1)
    _li(page, "Parent", 100, L1)
    _li(page, "o small indent", 120, L1 + 10)
    assert _parent(_run(page), "o small indent") == "Parent"


def test_same_margin_after_child_is_sibling() -> None:
    page = SynPage(1)
    _li(page, "Parent", 100, L1)
    _li(page, "a) first", 120, L2)
    _li(page, "b) second", 140, L2)
    _li(page, "Next top", 160, L1)
    result = _run(page)
    assert (_parent(result, "a) first"), _parent(result, "b) second"), _parent(result, "Next top")) == (
        "Parent", "Parent", None)


def test_three_levels() -> None:
    page = SynPage(1)
    _li(page, "Top", 100, L1)
    _li(page, "o Mid", 120, L2)
    _li(page, "▪ Leaf", 140, L3)
    _li(page, "o Mid 2", 160, L2)
    result = _run(page)
    assert (_parent(result, "▪ Leaf"), _parent(result, "o Mid 2")) == ("o Mid", "Top")
    leaf = _by_text(result)["▪ Leaf"].list_info
    assert leaf is not None and leaf.depth == 2
    assert list_summary(result)["max_depth"] == 2


def test_operation_is_not_a_glyph() -> None:
    page = SynPage(1)
    _li(page, "Parent", 100, L1)
    _li(page, "operation mode", 120, L1 + 10)
    result = _run(page)
    assert _parent(result, "operation mode") is None
    assert _codes(result) == [("list_level_ambiguous", "operation mode")]


def test_top_level_list_with_other_indent_has_no_parent() -> None:
    page = SynPage(1).text("section_header", "Functions in offset screen:", 80)
    _li(page, "Work set: Set the parameters", 100, 121.0)
    _li(page, "Tool set: Set the height", 120, 121.0)
    result = _run(page)
    assert {_parent(result, t) for t in ("Work set: Set the parameters", "Tool set: Set the height")} == {None}
    assert _codes(result) == []


# ------------------------------------------------------------------ ngắt khối, qua trang

def test_heading_or_text_breaks_the_block() -> None:
    page = SynPage(1)
    _li(page, "Parent", 100, L1)
    page.text("text", "A paragraph between.", 120)
    _li(page, "Deep after text", 140, L2)
    page.text("section_header", "Note:", 160)
    _li(page, "Deep after label", 180, L2)
    result = _run(page)
    assert (_parent(result, "Deep after text"), _parent(result, "Deep after label")) == (None, None)
    assert _codes(result) == []   # không có glyph → cấp 1, không review


def test_glyph_item_without_parent_is_orphan() -> None:
    page = SynPage(1)
    _li(page, "Parent", 100, L1)
    page.text("text", "A paragraph between.", 120)
    _li(page, "o child after text", 140, L2)
    _li(page, "o sibling after text", 160, L2)
    _li(page, "Back to level 1", 180, L1)
    result = _run(page)
    assert _parent(result, "o child after text") is None
    assert _parent(result, "Back to level 1") is None
    assert _codes(result) == [("list_orphan", "o child after text"),
                              ("list_level_ambiguous", "o sibling after text")]


def _page_end_with_list(furniture: bool) -> tuple[SynPage, SynPage]:
    p1 = SynPage(1)
    _li(p1, "#4142: Z axis movement type", 680, L1)
    _li(p1, "o #4142 = 0 : linear", 697, L2)
    p2 = SynPage(2)
    if furniture:
        p2.text("page_header", "Model: F54", 35)
    _li(p2, "o #4142 = 1 : circular", 67, L2)
    _li(p2, "#4143: A axis movement type", 103, L1)
    return p1, p2


def test_cross_page_continuation() -> None:
    for furniture in (True, False):
        result = _run(*_page_end_with_list(furniture))
        assert _parent(result, "o #4142 = 1 : circular") == "#4142: Z axis movement type"
        assert "list_cross_page" in _by_text(result)["o #4142 = 1 : circular"].flags
        assert _parent(result, "#4143: A axis movement type") is None
        assert _codes(result) == []


def test_no_cross_page_when_previous_page_ends_with_text() -> None:
    p1, p2 = _page_end_with_list(False)
    p1.text("text", "Closing paragraph.", 720)
    result = _run(p1, p2)
    assert _parent(result, "o #4142 = 1 : circular") is None
    assert _codes(result) == [("list_orphan", "o #4142 = 1 : circular")]


def test_no_cross_page_when_pages_not_adjacent() -> None:
    p1, p2 = _page_end_with_list(False)
    p3 = SynPage(3)
    p3.texts, p3.children = p2.texts, p2.children
    for t in p3.texts:
        t["prov"][0]["page_no"] = 3
    result = _run(p1, p3)
    assert _parent(result, "o #4142 = 1 : circular") is None


# ------------------------------------------------------------------ tài liệu lộn xộn

def test_dash_glyph_used_for_top_level_is_not_child() -> None:
    page = SynPage(1)
    for i, text in enumerate(("- first", "- second", "- third")):
        _li(page, text, 100 + 20 * i, L1)
    result = _run(page)
    assert {_parent(result, t) for t in ("- first", "- second", "- third")} == {None}
    assert {_by_text(result)[t].list_info.marker for t in ("- first", "- third")} == {"-"}  # type: ignore[union-attr]
    assert _codes(result) == []


def test_dedent_to_unknown_margin_is_ambiguous() -> None:
    page = SynPage(1)
    _li(page, "Top", 100, L1)
    _li(page, "o Child", 120, L2)
    _li(page, "Between levels", 140, 121.0)
    result = _run(page)
    assert _parent(result, "Between levels") is None
    assert _codes(result) == [("list_level_ambiguous", "Between levels")]


def test_mixed_markers_among_siblings_are_flagged() -> None:
    page = SynPage(1)
    _li(page, "Parent", 100, L1)
    _li(page, "o one", 120, L2)
    _li(page, "- two", 140, L2)
    result = _run(page)
    assert _parent(result, "- two") == "Parent"
    assert all("list_marker_mixed" in _by_text(result)[t].flags for t in ("o one", "- two"))
    assert _codes(result) == []


def test_docling_marker_used_when_text_has_no_glyph() -> None:
    page = SynPage(1)
    _li(page, "Bullet text", 100, L1, marker="-")
    _li(page, "Empty marker", 120, L1, marker="")
    by_text = _by_text(_run(page))
    assert by_text["Bullet text"].list_info.marker == "-"     # type: ignore[union-attr]
    assert by_text["Empty marker"].list_info.marker is None   # type: ignore[union-attr]


def test_non_list_elements_have_no_list_info() -> None:
    page = SynPage(1).text("text", "Plain", 80)
    _li(page, "Item", 100, L1)
    by_text = _by_text(_run(page))
    assert by_text["Plain"].list_info is None
    assert list_summary(_run(page)) == {"list_items": 1, "children": 0, "max_depth": 0, "orphans": 0, "ambiguous": 0}
