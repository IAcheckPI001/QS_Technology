"""Nhóm HC: header classification (D-03, T-03…T-05) + GT-19."""
import copy

import pytest

from app.modules.doc_ingest.review.approval import table_unit_payload
from tests.doc_ingest.f54 import f54_docs, row_by_key, run_docs, run_f54, table_on
from tests.doc_ingest.synthetic import SynPage, param_rows

HEADER = ["Key", "Description", "Value"]


@pytest.fixture(scope="module")
def f54_run():
    return run_f54()


def _continued(first_rows, second_rows, *, second_header=(0,), profile="default", **second_kwargs):
    first = SynPage(1).table([HEADER, *first_rows], top=600, row_h=15)
    second = SynPage(2).table(second_rows, top=70, header_rows=second_header, **second_kwargs)
    return run_docs([first.to_doc(), second.to_doc()], profile, doc_id="syn")


def _t05_steps(run) -> list[str]:
    return [e.reason for e in run.log if e.rule_id == "T-05"]


def test_hc01_repeated_header_is_marked_not_data() -> None:
    run = _continued(param_rows(1, 4), [HEADER, *param_rows(10, 3)])
    assert len(run.tables) == 1
    repeated = run.tables[0].rows[5]
    assert repeated.is_header and repeated.repeated_header and repeated.segment == 1
    assert _t05_steps(run) == ["row repeats the logical table header (step a)"]
    assert run.review == []


def test_hc02_gt19_token_shape_demotes_without_code_patterns(f54_run) -> None:
    row = row_by_key(table_on(f54_run, 167), "#4140 - #4147")
    assert row.is_header is False
    assert _t05_steps(f54_run) == ["header flag demoted to data (step b)"]


@pytest.mark.parametrize(("profile", "decision"), [("qs_controller", "c"), ("default", "d")])
def test_hc03_too_few_rows_falls_back_to_profile_or_review(profile: str, decision: str) -> None:
    run = _continued(param_rows(1, 1), param_rows(10, 2), profile=profile)
    flagged = run.tables[0].rows[2]
    if decision == "c":
        assert flagged.is_header is False
        assert _t05_steps(run) == ["header flag demoted to data (step c)"]
        assert run.review == []
    else:
        assert flagged.is_header is True
        assert [(r.code, r.blocks, r.target) for r in run.review] == [
            ("header_demotion_unsure", "chunk", f"syn:t001:{flagged.row_id}")]


def test_hc04_unsure_blocks_only_its_own_table() -> None:
    first = SynPage(1).table([HEADER, *param_rows(1, 1)], top=600)
    second = SynPage(2).table(param_rows(10, 2), top=70)
    other = SynPage(7).table([HEADER, *param_rows(50, 4)], top=100)
    run = run_docs([first.to_doc(), second.to_doc(), other.to_doc()], doc_id="syn")
    assert [(r.code, r.target.split(":r")[0]) for r in run.review] == [("header_demotion_unsure", "syn:t001")]


@pytest.mark.parametrize(("keys", "demoted"), [
    (["#0001", "#0002", "#0003", "AB-1", "AB-2"], True),    # 3/5 = 60 %
    (["#0001", "#0002", "AB-1", "AB-2"], False),            # 2/4 = 50 %
])
def test_hc05_shape_majority_threshold(keys: list[str], demoted: bool) -> None:
    rows = [[k, f"Setting {i}", "1"] for i, k in enumerate(keys)]
    run = _continued(rows, [["#0099", "Flagged", "2"]])
    flagged = run.tables[0].rows[-1]
    assert flagged.is_header is (not demoted)
    assert bool(run.review) is (not demoted)


def test_hc06_real_headers_are_never_demoted(f54_run) -> None:
    for page, header in [(11, ["Port", "Functions"]), (14, ["Add", "Name", "Function"]),
                         (40, ["Add", "Name", "Function"])]:
        table = table_on(f54_run, page)
        assert table.rows[0].is_header and [c.text for c in table.rows[0].cells] == header
    assert [r for r in f54_run.review if r.code == "header_demotion_unsure"] == []


def test_hc07_continuations_inherit_header(f54_run) -> None:
    flags = {t.logical_table_id: t.flags for t in f54_run.tables if len(t.segments) > 1}
    inherited = sorted(f"{tid}:{f}" for tid, fs in flags.items() for f in fs if f.startswith("header_inherited"))
    assert inherited == ["f54:t004:header_inherited:segment1", "f54:t004:header_inherited:segment2",
                         "f54:t005:header_inherited:segment1", "f54:t006:header_inherited:segment1"]


def test_hc08_headerless_table_does_not_invent_header() -> None:
    run = run_docs([SynPage(1).table(param_rows(1, 4), top=100, header_rows=()).to_doc()], doc_id="syn")
    table = run.tables[0]
    assert [c.header_text for c in table.columns] == [None, None, None]
    assert {c.header_source for c in table.columns} == {"none"}
    assert [(r.code, r.blocks) for r in run.review] == [("header_missing", "fact")]


def test_hc09_more_docling_columns_is_ambiguous() -> None:
    cols4 = [(90.0, 150.0), (180.0, 300.0), (330.0, 400.0), (430.0, 540.0)]
    run = _continued(param_rows(1, 4), [["#0010", "a", "b", "c"]] * 3, second_header=(), cols=cols4)
    assert len(run.tables) == 2
    assert [r.code for r in run.review] == ["ambiguous_continuation", "header_missing"]


def test_hc09_heading_between_starts_new_table() -> None:
    first = SynPage(1).table([HEADER, *param_rows(1, 4)], top=600)
    second = SynPage(2).text("section_header", "5.2 Next section", 60).table([HEADER, *param_rows(9, 3)], top=90)
    run = run_docs([first.to_doc(), second.to_doc()], doc_id="syn")
    assert len(run.tables) == 2 and run.review == []


def test_hc09_distinct_header_on_aligned_segment_is_never_silent() -> None:
    run = _continued(param_rows(1, 4), [["Name", "Type", "Unit"], *param_rows(9, 3)])
    assert len(run.tables) == 1
    assert [r.code for r in run.review] == ["header_demotion_unsure"]


def _scale_docs(docs, factor: float):
    scaled = copy.deepcopy(docs)
    for doc in scaled:
        for page in doc["pages"].values():
            page["size"] = {k: v * factor for k, v in page["size"].items()}
        for kind in ("texts", "tables", "pictures"):
            for item in doc.get(kind, []):
                for prov in item.get("prov", []):
                    prov["bbox"].update({k: prov["bbox"][k] * factor for k in "ltrb"})
                for cell in (item.get("data") or {}).get("table_cells", []):
                    cell["bbox"].update({k: cell["bbox"][k] * factor for k in "ltrb"})
    return scaled


def test_hc10_decisions_are_scale_invariant() -> None:
    docs = f54_docs({167, 168, 169, 170, 171})
    base, scaled = run_docs(docs), run_docs(_scale_docs(docs, 1.5))
    assert [table_unit_payload(t) for t in scaled.tables] == [table_unit_payload(t) for t in base.tables]
    assert [t.flags for t in scaled.tables] == [t.flags for t in base.tables]
    assert [(r.code, r.target) for r in scaled.review] == [(r.code, r.target) for r in base.review]
