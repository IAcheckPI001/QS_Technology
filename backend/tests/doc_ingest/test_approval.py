"""Nhóm HA: approval / HITL (D-08, H-1…H-9) + GT-13, GT-15 (phần chạy được không cần builder)."""
from datetime import datetime, timezone
from itertools import product

import pytest
from pydantic import ValidationError

from app.modules.doc_ingest.review.approval import (TRANSITIONS, TransitionError, bulk_approve_section,
                                                    carry_over, content_hash, is_served, open_blocking,
                                                    publishable, table_unit_payload, transition)
from app.modules.doc_ingest.schemas.normalized import LogicalTable, ReviewItem
from app.modules.doc_ingest.schemas.review import ApprovalRecord, DocState, KnowledgeUnit, UnitState
from tests.doc_ingest.f54 import f54_docs, run_docs, table_on
from tests.doc_ingest.synthetic import SynPage, param_rows

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)
U = UnitState


def unit(unit_id: str, unit_type: str = "text", state: UnitState = U.PENDING_REVIEW, **kw) -> KnowledgeUnit:
    return KnowledgeUnit(unit_id=unit_id, unit_type=unit_type, content_hash=kw.pop("content_hash", f"c-{unit_id}"),
                         evidence_hash="e", state=state, **kw)


def table_unit(table: LogicalTable, state: UnitState = U.PENDING_REVIEW) -> KnowledgeUnit:
    return KnowledgeUnit(unit_id=table.logical_table_id, unit_type="parameter",
                         content_hash=content_hash(table_unit_payload(table)),
                         evidence_hash=content_hash([s.element_id for s in table.segments]), state=state)


def review_item(target: str, *, blocking: bool = True, code: str = "column_count_mismatch") -> ReviewItem:
    return ReviewItem(item_id="rq-9001", element_id="f54:p169:e002", code=code, blocking=blocking,
                      blocks="chunk", target=target, detail="giả lập")


# ------------------------------------------------------------------ HA-01, HA-02

@pytest.mark.parametrize(("start", "to"), list(product(UnitState, UnitState)))
def test_ha01_only_declared_transitions_are_allowed(start: UnitState, to: UnitState) -> None:
    current = unit("u1", state=start)
    if to in TRANSITIONS[start]:
        moved, _ = transition(current, to, actor="reviewer.a", now=NOW)
        assert moved.state == to
    else:
        with pytest.raises(TransitionError):
            transition(current, to, actor="reviewer.a", now=NOW)


def test_ha02_served_only_when_document_active_and_unit_approved() -> None:
    served = [(d, u) for d, u in product(DocState, UnitState) if is_served(d, u)]
    assert served == [(DocState.ACTIVE, U.APPROVED)]


# ------------------------------------------------------------------ HA-03 (GT-13), HA-05 (GT-15)

@pytest.fixture(scope="module")
def axis_table() -> LogicalTable:
    return table_on(run_docs(f54_docs({167, 168, 169})), 167)


def test_ha03_gt13_blocking_item_prevents_approval(axis_table: LogicalTable) -> None:
    pending = table_unit(axis_table)
    blocking = open_blocking([review_item(f"{axis_table.logical_table_id}:r60")], [axis_table.logical_table_id])
    with pytest.raises(TransitionError, match="column_count_mismatch"):
        transition(pending, U.APPROVED, actor="reviewer.a", blocking=blocking, now=NOW)
    non_blocking = open_blocking([review_item("f54:t004:r60", blocking=False)], ["f54:t004"])
    approved, record = transition(pending, U.APPROVED, actor="reviewer.a", blocking=non_blocking, now=NOW)
    assert approved.state == U.APPROVED and record is not None


def test_ha03_open_blocking_matches_unit_ids_exactly() -> None:
    items = [review_item("f54:t004:r2"), review_item("f54:t0041:r2"), review_item("f54:t004")]
    assert [i.target for i in open_blocking(items, ["f54:t004"])] == ["f54:t004:r2", "f54:t004"]


def test_ha05_gt15_rerun_keeps_or_resets_approval(axis_table: LogicalTable) -> None:
    approved, record = transition(table_unit(axis_table), U.APPROVED, actor="reviewer.a", now=NOW)
    assert record is not None
    other = unit("f54:t009", state=U.APPROVED)
    other_record = ApprovalRecord(unit_id=other.unit_id, unit_type=other.unit_type, reviewer="reviewer.a",
                                  approved_at=NOW, unit_content_hash=other.content_hash,
                                  evidence_hash=other.evidence_hash)
    previous = [record, other_record]

    rerun = table_on(run_docs(f54_docs({167, 168, 169})), 167)
    kept = carry_over([table_unit(rerun, U.DRAFT), other.model_copy(update={"state": U.DRAFT})], previous)
    assert [u.state for u in kept.units] == [U.APPROVED, U.APPROVED]
    assert set(kept.reasons.values()) == {"id"}

    docs = f54_docs({167, 168, 169})
    cell = next(c for c in docs[1]["tables"][0]["data"]["table_cells"] if c["text"] == "#8010")
    value = next(c for c in docs[1]["tables"][0]["data"]["table_cells"]
                 if c["start_row_offset_idx"] == cell["start_row_offset_idx"] and c["start_col_offset_idx"] == 3)
    value["text"] = "4"
    edited = table_on(run_docs(docs), 167)
    changed = carry_over([table_unit(edited, U.DRAFT), other.model_copy(update={"state": U.DRAFT})], previous)
    assert [u.state for u in changed.units] == [U.PENDING_REVIEW, U.APPROVED]
    assert changed.reasons[edited.logical_table_id] == "hash_changed"


def test_ha05b_approval_survives_table_id_shift(axis_table: LogicalTable) -> None:
    _, record = transition(table_unit(axis_table), U.APPROVED, actor="reviewer.a", now=NOW)
    assert record is not None and record.unit_id == "f54:t001"
    extra = SynPage(100).table([["Key", "Description", "Value"], *param_rows(1, 4)], top=100).to_doc()
    shifted = table_on(run_docs([extra, *f54_docs({167, 168, 169})]), 167)
    assert shifted.logical_table_id == "f54:t002"
    result = carry_over([table_unit(shifted, U.DRAFT)], [record])
    assert [u.state for u in result.units] == [U.APPROVED]
    assert result.reasons == {"f54:t002": "hash"} and result.matched_records == {"f54:t002": "f54:t001"}


def test_ha05b_identical_content_is_ambiguous_and_record_used_once() -> None:
    record = ApprovalRecord(unit_id="old", unit_type="text", reviewer="reviewer.a", approved_at=NOW,
                            unit_content_hash="c-same", evidence_hash="e")
    twins = [unit("a", content_hash="c-same", state=U.DRAFT), unit("b", content_hash="c-same", state=U.DRAFT)]
    result = carry_over(twins, [record])
    assert [u.state for u in result.units] == [U.PENDING_REVIEW, U.PENDING_REVIEW]
    assert result.reasons == {"a": "ambiguous", "b": "ambiguous"}
    other_type = carry_over([unit("a", "warning", content_hash="c-same", state=U.DRAFT)], [record])
    assert other_type.reasons == {"a": "new"} and other_type.units[0].state == U.DRAFT


# ------------------------------------------------------------------ HA-04, HA-06, HA-07, HA-08, HA-09

def test_ha04_dependency_must_be_approved_before_publish() -> None:
    warning = unit("w1", "warning", state=U.PENDING_REVIEW)
    wiring = unit("d1", "wiring", state=U.APPROVED, depends_on=["w1"])
    assert publishable([warning, wiring], DocState.ACTIVE) == []
    approved_warning, _ = transition(warning, U.APPROVED, actor="reviewer.a", now=NOW)
    assert publishable([approved_warning, wiring], DocState.ACTIVE) == ["w1", "d1"]


def test_ha06_conflict_group_publishes_neither_side() -> None:
    port_table = unit("u-port", "pinout", state=U.APPROVED, conflict_group="cg-1")
    figure = unit("u-fig", "figure_fact", state=U.CONFLICT, conflict_group="cg-1")
    assert publishable([port_table, figure], DocState.ACTIVE) == []


def test_ha07_bulk_section_approval_refuses_high_risk_and_flagged() -> None:
    section = ["2. Wiring", "2.3 Sensor"]
    units = [
        unit("u-text", section_path=[*section, "2.3.1"]),
        unit("u-param", "parameter", section_path=section),
        unit("u-flagged", section_path=section, flags=["text_coverage_gap"]),
        unit("u-blocked", section_path=section),
        unit("u-elsewhere", section_path=["5. Parameters"]),
    ]
    result = bulk_approve_section(units, section, actor="reviewer.a",
                                  review=[review_item("u-blocked:r1")], now=NOW)
    states = {u.unit_id: u.state for u in result.units}
    assert states == {"u-text": U.APPROVED, "u-param": U.PENDING_REVIEW, "u-flagged": U.PENDING_REVIEW,
                      "u-blocked": U.PENDING_REVIEW, "u-elsewhere": U.PENDING_REVIEW}
    assert result.refused == {"u-param": "high_risk", "u-flagged": "high_risk", "u-blocked": "blocking_review_item"}
    assert [(r.unit_id, r.mode) for r in result.records] == [("u-text", "bulk_section")]


def test_ha08_only_approved_units_are_publishable() -> None:
    units = [unit(f"u-{s.value}", state=s) for s in UnitState]
    assert publishable(units, DocState.ACTIVE) == ["u-approved"]
    assert publishable(units, DocState.STAGING) == []


def test_ha09_approval_requires_named_reviewer_and_records_hashes() -> None:
    pending = unit("u1")
    for actor in ("", "   ", "system:auto"):
        with pytest.raises(TransitionError):
            transition(pending, U.APPROVED, actor=actor, now=NOW)
    _, record = transition(pending, U.APPROVED, actor=" reviewer.a ", now=NOW)
    assert record is not None
    assert (record.reviewer, record.approved_at, record.unit_content_hash, record.evidence_hash) == (
        "reviewer.a", NOW, "c-u1", "e")
    with pytest.raises(ValidationError):
        ApprovalRecord(unit_id="u1", unit_type="text", reviewer=" ", approved_at=NOW, unit_content_hash="c",
                       evidence_hash="e")
