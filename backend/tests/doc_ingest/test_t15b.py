"""T-15b (2026-11-25): hàng đầu trang có ô khoá rỗng là phần nối tiếp của hàng cuối trang trước → gộp vào hàng đó.

Điều kiện hẹp: trang liền kề, là hàng dữ liệu đầu tiên của đoạn, hàng đích có ô khoá, và chữ nối tiếp không bắt đầu
bằng chữ hoa (hàng chú giải mới có ô khoá là biểu tượng ảnh thì không gộp)."""
from tests.doc_ingest.f54 import run_docs
from tests.doc_ingest.synthetic import SynPage


def _codes(run, *codes):
    return [r for r in run.review if r.code in codes]


def test_t15b_page_top_continuation_merges_into_previous_page_last_row() -> None:
    page1 = SynPage(1).table([["Port", "Pins", "Description"], ["CN1", "- A - B", "Power pins"],
                              ["CN2", "- D+ - D-", "Included: - D+ : signal"]], top=100)
    page2 = SynPage(2).table([["", "", "- D- : reverse signal - FG : shield"], ["CN3", "- X1", "Input"]],
                             top=100, header_rows=())
    run = run_docs([page1.to_doc(), page2.to_doc()], doc_id="syn")
    table = run.tables[0]
    assert [s.pdf_page_index for s in table.segments] == [1, 2]
    keyed = {r.cells[0].text: r for r in table.rows if not r.is_header and r.cells[0].text}
    assert keyed["CN2"].cells[2].text == "Included: - D+ : signal - D- : reverse signal - FG : shield"
    assert keyed["CN3"].cells[1].text == "- X1"
    assert [r.cells[0].text for r in table.rows if not r.is_header] == ["CN1", "CN2", "CN3"]
    assert _codes(run, "orphan_row") == []
    assert [e.rule_id for e in run.log if e.rule_id == "T-15b"] == ["T-15b"]


def test_t15b_merges_continuation_that_starts_lowercase_mid_sentence() -> None:
    page1 = SynPage(1).table([["Port", "Pins", "Description"], ["CN10", "- P2- - P2+", "- P2- : output pins, combine with (PUL+)"]],
                             top=100)
    page2 = SynPage(2).table([["", "", "to broadcast pulse signal. - FG : shield wire"], ["CN11", "- Z3-", "Control axis 3"]],
                             top=100, header_rows=())
    run = run_docs([page1.to_doc(), page2.to_doc()], doc_id="syn")
    keyed = {r.cells[0].text: r for r in run.tables[0].rows if not r.is_header and r.cells[0].text}
    assert keyed["CN10"].cells[2].text.endswith("(PUL+) to broadcast pulse signal. - FG : shield wire")
    assert _codes(run, "orphan_row") == []


def test_t15b_no_merge_when_row_starts_with_capital_letter_like_icon_legend_row() -> None:
    page1 = SynPage(1).table([["Icon", "Name", "Description"], ["CW", "Cw", "Tool magazine run clockwise"]], top=100)
    page2 = SynPage(2).table([["", "Ccw", "Tool magazine run counter clockwise"], ["", "Stop", "Stop run"]],
                             top=100, header_rows=())
    run = run_docs([page1.to_doc(), page2.to_doc()], doc_id="syn")
    assert [e.rule_id for e in run.log if e.rule_id == "T-15b"] == []
    assert _codes(run, "orphan_row") != []


def test_t15b_no_merge_when_row_is_not_first_data_row_of_the_page() -> None:
    page1 = SynPage(1).table([["Port", "Pins", "Description"], ["CN1", "- A", "Power"]], top=100)
    page2 = SynPage(2).table([["CN2", "- B", "Input"], ["", "", "wrapped"]], top=100, header_rows=())
    run = run_docs([page1.to_doc(), page2.to_doc()], doc_id="syn")
    rows = [r for r in run.tables[0].rows if not r.is_header]
    # hàng 'wrapped' nối vào CN2 theo T-15 trong cùng trang, không phải T-15b
    assert [r.cells[0].text for r in rows] == ["CN1", "CN2"]
    assert rows[1].cells[2].text == "Input wrapped"
    assert [e.rule_id for e in run.log if e.rule_id == "T-15b"] == []


def test_t15b_does_not_touch_tables_without_page_top_continuation() -> None:
    page1 = SynPage(1).table([["Port", "Pins", "Description"], ["CN1", "- A", "Power"]], top=100)
    page2 = SynPage(2).table([["CN2", "- B", "Input"]], top=100, header_rows=())
    run = run_docs([page1.to_doc(), page2.to_doc()], doc_id="syn")
    assert [e.rule_id for e in run.log if e.rule_id == "T-15b"] == []
    assert [r.cells[0].text for r in run.tables[0].rows if not r.is_header] == ["CN1", "CN2"]
