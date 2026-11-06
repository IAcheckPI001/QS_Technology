"""Nhóm AP: applicability (D-04, T-13) + GT-04 (ParamRef, T-12), GT-05 (phần applicability)."""
import pytest
from pydantic import ValidationError

from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.normalized import ApplicabilityCandidate
from app.modules.doc_ingest.technical_refs.applicability import detect_applicability
from app.modules.doc_ingest.technical_refs.params import matches, overlapping, parse_param_ref
from tests.doc_ingest.f54 import row_by_key, run_f54, table_on

DEFAULT = load_profile("default")


@pytest.fixture(scope="module")
def qs_run():
    return run_f54("qs_controller")


def _general(run):
    return next(t for t in run.tables if [s.pdf_page_index for s in t.segments] == [170, 171])


# ------------------------------------------------------------------ AP-01 … AP-07

def test_ap01_schema_rejects_unknown_status_and_fields() -> None:
    with pytest.raises(ValidationError):
        ApplicabilityCandidate(status="maybe", note="x", condition_text="x")
    with pytest.raises(ValidationError):
        ApplicabilityCandidate.model_validate({"status": "not_available", "note": "x", "condition_text": "x", "extra": 1})


def test_ap01_detected_models_and_interfaces_come_from_registry(qs_run) -> None:
    vocab = DEFAULT.vocabulary
    for table in qs_run.tables:
        for row in table.rows:
            for item in row.applicability_candidates:
                assert set(item.models) <= set(vocab.product_models)
                assert set(item.interfaces) <= set(vocab.control_interface)


def test_ap02_not_available_on_f54(qs_run) -> None:
    row = row_by_key(_general(qs_run), "#0136")
    [item] = row.applicability_candidates
    assert (item.status, item.models, item.condition_text) == ("not_available", ["F54"], "F54 controller")
    assert item.note in row.cells[1].text
    unmatched = [r for r in qs_run.review if r.code == "applicability_model_unmatched"
                 and r.target == f"{_general(qs_run).logical_table_id}:{row.row_id}"]
    assert unmatched == []


@pytest.mark.parametrize("key", ["#4132", "#4133", "#4134"])
def test_ap03_touch_controller_is_conditional_and_flagged(qs_run, key: str) -> None:
    table = _general(qs_run)
    row = row_by_key(table, key)
    [item] = row.applicability_candidates
    assert (item.status, item.models, item.interfaces, item.condition_text) == (
        "conditional", [], [], "touch controller")
    codes = [(r.code, r.blocks) for r in qs_run.review if r.target == f"{table.logical_table_id}:{row.row_id}"]
    assert codes == [("applicability_note", "fact"), ("applicability_model_unmatched", "fact")]


def test_ap04_no_parameter_row_is_dropped(qs_run) -> None:
    for page in (167, 169, 170):
        table = table_on(qs_run, page)
        data = [r for r in table.rows if not r.is_header]
        assert all(r.param_ref is not None for r in data), table.logical_table_id
        assert "param_table" in table.flags
    general = _general(qs_run)
    assert sum(1 for r in general.rows if r.applicability_candidates) == 7   # #0136 + 6 dòng touch controller


@pytest.mark.parametrize(("text", "status", "models"), [
    ("Không áp dụng cho F86", "not_available", ["F86"]),
    ("Chỉ áp dụng cho 6AH", "available_only", ["6AH"]),
    ("(Only available on Astro 6AV)", "available_only", ["6AV"]),
    ("Not supported on F10T or F86E.", "not_available", ["F10T", "F86E"]),
])
def test_ap05_lexicon_en_vi_and_aliases(text: str, status: str, models: list[str]) -> None:
    [match] = detect_applicability(text, DEFAULT)
    assert (match.candidate.status, match.candidate.models, match.unmatched) == (status, models, False)


def test_ap05_interface_condition_resolves_to_registry_key() -> None:
    [match] = detect_applicability("Available on EtherCAT models", DEFAULT)
    assert (match.candidate.status, match.candidate.interfaces) == ("available_only", ["ethercat"])


def test_ap06_unknown_model_keeps_fact_and_blocks_fact_only() -> None:
    [match] = detect_applicability("Speed limit (Not available on Z99)", DEFAULT)
    item = match.candidate
    assert (item.status, item.models, item.condition_text, match.unmatched) == (
        "not_available", [], "Z99", True)


@pytest.mark.parametrize("text", ["Shows the available memory", "Select from the available options",
                                  "Unavailable on startup", "Values available once homing is done"])
def test_ap07_no_false_positive(text: str) -> None:
    assert detect_applicability(text, DEFAULT) == []


# ------------------------------------------------------------------ GT-04 ParamRef (profile qs_controller)

PREFIXES = ["#", "M"]


def test_gt04_list_range_and_namespace() -> None:
    lst = parse_param_ref("#8030, #8032 #8034, #8036", PREFIXES, 64).ref
    assert lst is not None and (lst.kind, lst.codes, lst.range_start) == ("list", [8030, 8032, 8034, 8036], None)
    rng = parse_param_ref("#0000 - #0007", PREFIXES, 64).ref
    assert rng is not None and (rng.kind, rng.codes) == ("range", list(range(8)))
    single = parse_param_ref("M1920", PREFIXES, 64).ref
    assert single is not None and not matches(single, "#", 1920) and matches(single, "M", 1920)
    assert parse_param_ref("#3", PREFIXES, 64).ref.codes == parse_param_ref("#0003", PREFIXES, 64).ref.codes


def test_gt04_code_8033_matches_only_its_row(qs_run) -> None:
    spindle = next(t for t in qs_run.tables if t.segments[0].pdf_page_index == 169)
    hits = [r.cells[0].text for r in spindle.rows if r.param_ref and matches(r.param_ref, "#", 8033)]
    assert hits == ["#8031, #8033 #8035, #8037"]


def test_gt04_codes_never_overlap_within_a_table(qs_run) -> None:
    for table in qs_run.tables:
        refs = [(r.row_id, r.param_ref) for r in table.rows if r.param_ref]
        assert overlapping(refs) == []
    assert [r for r in qs_run.review if r.code in {"param_unparseable", "param_code_overlap"}] == []


@pytest.mark.parametrize(("text", "error"), [
    ("#0001 - M0005", "mixed_prefix"), ("#0009 - #0002", "range_not_increasing"),
    ("#0001, M0002", "mixed_prefix"), ("#0001 - #0004, #0008", "unrecognized_pattern"), ("#12a", "unrecognized_pattern"),
])
def test_gt04_unparseable_patterns(text: str, error: str) -> None:
    assert parse_param_ref(text, PREFIXES, 64).error == error


def test_gt04_long_range_is_flagged() -> None:
    parsed = parse_param_ref("#0000 - #0099", PREFIXES, 64)
    assert parsed.ref is not None and parsed.flags == ("range_too_long",)


def test_default_profile_parses_no_parameter_codes() -> None:
    run = run_f54("default")
    assert all(r.param_ref is None for t in run.tables for r in t.rows)
