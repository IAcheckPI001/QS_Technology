"""Nhóm LT: LogicalTable integrity (D-02) + GT-01, GT-02, GT-03, GT-17, GT-18."""
import re
from collections import Counter

import pytest
from pydantic import ValidationError

from app.modules.doc_ingest.schemas.normalized import LogicalTable
from tests.doc_ingest.f54 import f54_docs, row_by_key, run_docs, run_f54, table_on, texts
from tests.doc_ingest.synthetic import SynPage, param_rows


@pytest.fixture(scope="module")
def f54_run():
    return run_f54()


def _codes(run, *codes):
    return [r for r in run.review if r.code in codes]


# ------------------------------------------------------------------ GT-01, GT-02, GT-03

def test_gt01_port_table_columns_repaired_by_bbox(f54_run) -> None:
    table = table_on(f54_run, 11)
    assert [c.header_text for c in table.columns] == ["Port", "Functions"]
    data = [r for r in table.rows if not r.is_header]
    assert [r.cells[0].text for r in data] == [f"CN{i}" for i in range(1, 11)]
    assert row_by_key(table, "CN3").cells[1].text == "MPG Handle"
    assert "column_order_repaired:segment0" in table.flags


def test_gt02_axis_table_spans_three_pages(f54_run) -> None:
    table = table_on(f54_run, 167)
    assert [s.pdf_page_index for s in table.segments] == [167, 168, 169]
    assert [c.header_text for c in table.columns] == ["Parameter", "Description", "Work range", "Default"]
    demoted = row_by_key(table, "#4140 - #4147")
    assert demoted.is_header is False and demoted.segment == 1
    assert texts(row_by_key(table, "#12160 - #12167"))[2:] == ["", "0"]
    assert texts(row_by_key(table, "#12200 - #12207"))[2:] == ["", "0"]
    per_segment = Counter(r.segment for r in table.rows if not r.is_header)
    assert per_segment == {0: 21, 1: 32, 2: 17}
    assert "empty_column_restored:segment2:col2" in table.flags


def test_gt03_continuations_inherit_header(f54_run) -> None:
    spindle = next(t for t in f54_run.tables if [s.pdf_page_index for s in t.segments] == [169, 170])
    general = next(t for t in f54_run.tables if [s.pdf_page_index for s in t.segments] == [170, 171])
    assert row_by_key(spindle, "#8050, #8052 #8054, #8056").segment == 1
    assert texts(row_by_key(general, "#4136"))[2:] == ["", "15"]
    assert "header_inherited:segment1" in spindle.flags and "header_inherited:segment1" in general.flags


def test_gt17_deterministic(f54_run) -> None:
    again = run_f54()
    assert [t.model_dump_json() for t in again.tables] == [t.model_dump_json() for t in f54_run.tables]
    assert [i.model_dump_json() for i in again.review] == [i.model_dump_json() for i in f54_run.review]
    assert [e.model_dump_json() for e in again.log] == [e.model_dump_json() for e in f54_run.log]


def test_gt18_provenance_every_docling_cell_exactly_once(f54_run) -> None:
    source = Counter()
    for doc in f54_docs():
        for table in doc["tables"]:
            for index, _ in enumerate(table["data"]["table_cells"]):
                source[(int(next(iter(doc["pages"]))), f"{table['self_ref']}/cells/{index}")] += 1
    seen = Counter()
    for table in f54_run.tables:
        for row in table.rows:
            page = table.segments[row.segment].pdf_page_index
            for cell in row.cells:
                for ref in filter(None, [cell.raw_cell_ref, *cell.merged_cell_refs]):
                    seen[(page, ref)] += 1
        for cell in table.unassigned_cells:
            seen[(None, cell.raw_cell_ref)] += 1
    assert seen == source


# ------------------------------------------------------------------ LT-01 … LT-09

def test_lt01_every_row_has_exactly_one_cell_per_column(f54_run) -> None:
    for table in f54_run.tables:
        for row in table.rows:
            assert [c.col for c in row.cells] == list(range(len(table.columns)))
            for cell in row.cells:
                if cell.assigned_by == "empty_fill":
                    assert cell.text == "" and cell.raw_cell_ref is None


def test_lt02_cell_conservation_with_merge_and_unassigned() -> None:
    page = SynPage(1).table([["Key", "Description", "Value"], ["#0001", "First line", "1"],
                             ["", "wrapped line", ""], ["#0002", "Second", "2"]], top=100)
    page.tables[0]["data"]["table_cells"].append(
        {"bbox": {"l": 560.0, "t": 150.0, "r": 600.0, "b": 160.0, "coord_origin": "TOPLEFT"}, "row_span": 1,
         "col_span": 1, "start_row_offset_idx": 3, "end_row_offset_idx": 4, "start_col_offset_idx": 2,
         "end_col_offset_idx": 3, "text": "stray", "column_header": False})
    run = run_docs([page.to_doc()], doc_id="syn")
    source = {f"#/tables/0/cells/{i}" for i in range(len(page.tables[0]["data"]["table_cells"]))}
    table = run.tables[0]
    kept = {c.raw_cell_ref for r in table.rows for c in r.cells if c.raw_cell_ref}
    merged = {ref for r in table.rows for c in r.cells for ref in c.merged_cell_refs}
    unassigned = {c.raw_cell_ref for c in table.unassigned_cells}
    assert kept | merged | unassigned == source
    assert not (kept & merged) and not (kept & unassigned) and not (merged & unassigned)


def test_lt03_table_ids_unique_and_ordered(f54_run) -> None:
    ids = [t.logical_table_id for t in f54_run.tables]
    assert all(re.fullmatch(r"f54:t\d{3}", i) for i in ids)
    assert ids == [f"f54:t{n:03d}" for n in range(1, len(ids) + 1)]
    firsts = [(t.segments[0].pdf_page_index, t.segments[0].bbox.y0) for t in f54_run.tables]
    assert firsts == sorted(firsts)


def test_lt04_row_ids_stable_through_t15_merge() -> None:
    page = SynPage(1).table([["Key", "Description", "Value"], ["#0001", "Line one", "1"],
                             ["", "continues here", ""], ["#0002", "Line two", "2"]], top=100)
    run = run_docs([page.to_doc()], doc_id="syn")
    rows = run.tables[0].rows
    assert [r.row_id for r in rows] == ["r0", "r1", "r3"]
    assert rows[1].merged_row_ids == ["r2"] and rows[1].cells[1].text == "Line one continues here"
    assert [e.target for e in run.log if e.rule_id == "T-15"] == ["syn:t001:r2"]


def test_lt05_segments_on_consecutive_pages_and_unique(f54_run) -> None:
    owners = Counter(s.element_id for t in f54_run.tables for s in t.segments)
    assert max(owners.values()) == 1
    for table in f54_run.tables:
        pages = [s.pdf_page_index for s in table.segments]
        assert pages == list(range(pages[0], pages[0] + len(pages)))


def test_lt06_no_continuation_across_heading(f54_run) -> None:
    axis = table_on(f54_run, 167)
    assert axis.segments[-1].pdf_page_index == 169
    spindle = next(t for t in f54_run.tables if t.segments[0].pdf_page_index == 169)
    assert spindle.segments[0].element_id != axis.segments[-1].element_id
    assert spindle.columns[0].header_text == "Parameter"


def test_lt06_misaligned_headerless_top_table_is_ambiguous() -> None:
    first = SynPage(1).table([["Key", "Description", "Value"], *param_rows(1, 5)], top=500)
    second = SynPage(2).table(param_rows(10, 4), top=70, x=(84.0, 500.0), header_rows=())
    run = run_docs([first.to_doc(), second.to_doc()], doc_id="syn")
    assert len(run.tables) == 2
    assert [r.code for r in run.review] == ["ambiguous_continuation", "header_missing"]
    assert run.review[0].blocks == "chunk"


def test_lt07_two_header_rows_join_and_block_only_that_table() -> None:
    complex_page = SynPage(1).table([["Group", "Group", "Limit"], ["Key", "Description", "Value"],
                                     *param_rows(1, 4)], top=100, header_rows=(0, 1))
    simple_page = SynPage(3).table([["Key", "Description", "Value"], *param_rows(20, 4)], top=100)
    run = run_docs([complex_page.to_doc(), simple_page.to_doc()], doc_id="syn")
    complex_table, simple_table = run.tables
    assert [c.header_text for c in complex_table.columns] == ["Group / Key", "Group / Description", "Limit / Value"]
    assert [(r.code, r.target, r.blocks) for r in run.review] == [("complex_header", "syn:t001", "chunk")]
    assert "complex_header" not in simple_table.flags


def test_lt08_cell_outside_columns_is_kept_and_blocks() -> None:
    page = SynPage(1).table([["Key", "Description", "Value"], *param_rows(1, 3)], top=100)
    page.tables[0]["data"]["table_cells"].append(
        {"bbox": {"l": 570.0, "t": 120.0, "r": 598.0, "b": 128.0, "coord_origin": "TOPLEFT"}, "row_span": 1,
         "col_span": 1, "start_row_offset_idx": 1, "end_row_offset_idx": 2, "start_col_offset_idx": 2,
         "end_col_offset_idx": 3, "text": "note", "column_header": False})
    run = run_docs([page.to_doc()], doc_id="syn")
    table = run.tables[0]
    assert [(c.text, c.reason) for c in table.unassigned_cells] == [("note", "outside_columns")]
    assert [(r.code, r.blocking, r.blocks) for r in run.review] == [("unassigned_cell", True, "chunk")]


def test_lt09_schema_round_trip_and_rejects_unknown_fields(f54_run) -> None:
    for table in f54_run.tables:
        assert LogicalTable.model_validate_json(table.model_dump_json()) == table
    payload = f54_run.tables[0].model_dump(mode="json")
    payload["rows"][0]["cells"][0]["colour"] = "red"
    with pytest.raises(ValidationError):
        LogicalTable.model_validate(payload)


def test_t01_fallback_when_cell_bridges_whitespace_gap() -> None:
    bridge = {(2, 1): (180.0, 460.0)}   # mô tả tràn qua khe giữa cột 1 và cột 2
    page = SynPage(1).table([["Key", "Description", "Value"], *param_rows(1, 4)], top=100, cell_x=bridge)
    run = run_docs([page.to_doc()], doc_id="syn")
    assert [r.code for r in run.review] == ["column_count_mismatch"]
    assert [c.header_text for c in run.tables[0].columns] == ["Key", "Description", "Value"]


def test_f54_default_profile_has_no_structural_review(f54_run) -> None:
    assert _codes(f54_run, "unassigned_cell", "column_count_mismatch", "ambiguous_continuation",
                  "header_demotion_unsure", "orphan_row", "complex_header") == []
