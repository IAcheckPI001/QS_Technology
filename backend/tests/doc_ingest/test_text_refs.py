"""T-12/T-13 trên text và T-08 v1.1 (contract T-12, T-13, T-08; sửa 2026-11-09)."""
from __future__ import annotations

import pytest

from app.modules.doc_ingest.pipeline import RunResult, ref_summary, run_normalization
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.technical_refs.params import find_param_refs
from tests.doc_ingest.f54 import f54_docs
from tests.doc_ingest.synthetic import SynPage

QS = load_profile("qs_controller")
DEFAULT = load_profile("default")


def _scan(text: str):
    return find_param_refs(text, QS.param_prefixes, QS.param_text_patterns, QS.thresholds.max_range_len)


# ------------------------------------------------------------------ quét mã

@pytest.mark.parametrize("text, kind, codes, role", [
    ("M1920: Homing sensor status configuration parameter for X axis", "single", [1920], "definition"),
    ("o M1920 = 0 : Normally closed sensor (NC)", "single", [1920], "value_option"),
    ("o #4141= 0 : Y axis moves in linear direction", "single", [4141], "value_option"),
    ("#4140: X axis movement type", "single", [4140], "definition"),
    ("Number of pulses per 1mm movement: (#12010, #12011, #12012, #12013)", "list", [12010, 12011, 12012, 12013],
     "mention"),
    ("#4140 - #4147 Axis type", "range", list(range(4140, 4148)), "mention"),
    ("#8090\n- #8097 Axis dir signal delay", "range", list(range(8090, 8098)), "mention"),
    ("The cause is that the travel limit set in parameter #14006 is incorrect", "single", [14006], "mention"),
])
def test_single_list_range_and_role(text: str, kind: str, codes: list[int], role: str) -> None:
    scan = _scan(text)
    [ref] = scan.refs
    assert (ref.kind, ref.codes, ref.role) == (kind, codes, role)
    assert text[ref.start:ref.end] == ref.label
    assert scan.errors == [] and scan.near_miss == []


def test_and_splits_a_list_and_other_prefix_is_separate() -> None:
    scan = _scan("configure M1925, M1926 and M1927, then #4140")
    assert [(r.kind, r.label) for r in scan.refs] == [("list", "M1925, M1926"), ("single", "M1927"),
                                                     ("single", "#4140")]


@pytest.mark.parametrize("text, near", [
    ("When command M100 is called, the coolant is off", ["M100"]),
    ("2.4.3 Y42 output signal (M8)", ["M8"]),
    ("o Ex: If M100H3 is called", ["M100H"]),
    ("configure parameter M195..", ["M195"]),      # F54 trang 94: lỗi đánh máy của tài liệu
    ("screw 4 - M4", ["M4"]),
])
def test_m_codes_pins_and_typos_are_not_parameters(text: str, near: list[str]) -> None:
    scan = _scan(text)
    assert scan.refs == [] and scan.near_miss == near


def test_bad_range_and_mixed_range_list_are_unparseable() -> None:
    assert _scan("#4147 - #4140").errors == [("#4147 - #4140", "range_not_increasing")]
    assert _scan("#8150, #8152 - #8160").errors == [("#8150, #8152 - #8160", "unrecognized_pattern")]


def test_long_range_is_flagged() -> None:
    scan = _scan("#1000 - #1100 reserved")
    assert scan.refs[0].kind == "range" and scan.too_long == ["#1000 - #1100"]


def test_default_profile_scans_nothing() -> None:
    scan = find_param_refs("M1920: Homing", DEFAULT.param_prefixes, DEFAULT.param_text_patterns, 64)
    assert scan.refs == [] and scan.near_miss == []


# ------------------------------------------------------------------ trong pipeline

def _run(page: SynPage, profile=QS) -> RunResult:
    return run_normalization([page.to_doc()], "syn", profile)


def _by_text(result: RunResult):
    return {e.text: e for e in result.normalized or [] if e.text}


def _codes(result: RunResult) -> list[str]:
    return [r.code for r in result.tables.review if r.code not in ("furniture_unconfirmed",)]


def test_refs_attached_to_text_list_heading_but_not_figure_text() -> None:
    page = SynPage(1)
    pic = page.picture(300, 500)
    page.text("section_header", "2.6.4.5 Axis movement type (#4140)", 60)
    page.text("text", "Configure parameter #4140 first.", 90)
    page.text("list_item", "#4140: X axis movement type", 120, x=(103.0, 500.0))
    page.text("text", "#4150 inside the screenshot", 350, parent=pic)
    result = _run(page)
    by_text = _by_text(result)
    assert [r.role for r in by_text["2.6.4.5 Axis movement type (#4140)"].param_refs] == ["mention"]
    assert [r.role for r in by_text["Configure parameter #4140 first."].param_refs] == ["mention"]
    assert [r.role for r in by_text["#4140: X axis movement type"].param_refs] == ["definition"]
    assert by_text["#4150 inside the screenshot"].param_refs == []
    summary = ref_summary(result)
    assert (summary["text_param_refs"], summary["role_definition"], summary["role_mention"]) == (3, 1, 2)


def test_unparseable_range_in_text_is_reviewed() -> None:
    page = SynPage(1).text("text", "Set #4147 - #4140 to zero.", 80)
    assert _codes(_run(page)) == ["param_unparseable"]


def test_applicability_on_text() -> None:
    page = SynPage(1).text("text", "This function is not available on F54 controller.", 80)
    result = _run(page)
    [candidate] = _by_text(result)["This function is not available on F54 controller."].applicability_candidates
    assert candidate.status == "not_available" and candidate.note == "not available on F54 controller"
    assert "applicability_note" in _codes(result)
    assert ref_summary(result)["applicability_text"] == 1


def _list_page(child_code: str) -> SynPage:
    page = SynPage(1)
    page.text("list_item", "M1951: Enable/Disable workpiece homing feature", 100, x=(103.0, 500.0))
    page.text("list_item", f"o {child_code} = 0 : Disable", 120, x=(139.0, 500.0))
    page.text("list_item", f"o {child_code} = 1 : Enable", 140, x=(139.0, 500.0))
    return page


def test_list_param_mismatch_parent_child() -> None:
    result = _run(_list_page("M1950"))            # F54 trang 96: lỗi soạn thảo của tài liệu
    assert _codes(result) == ["list_param_mismatch", "list_param_mismatch"]
    assert ref_summary(result)["list_param_mismatch"] == 2
    assert _codes(_run(_list_page("M1951"))) == []


def test_f54_page19_refs_roles() -> None:
    result = run_normalization(f54_docs({19}), "f54", QS)
    roles = {(e.text or "")[:16]: [r.role for r in e.param_refs] for e in result.normalized or [] if e.param_refs}
    assert roles["M1920: Homing se"] == ["definition"]
    assert roles["o M1920 = 0 : No"] == ["value_option"]
    assert sum(1 for v in roles.values() if v == ["definition"]) == 4
    assert sum(1 for v in roles.values() if v == ["value_option"]) == 8
    assert "list_param_mismatch" not in _codes(result)
