import pytest

from app.modules.learning_ai.review.conflict_detector import detect_rule_conflicts
from app.modules.learning_ai.review.lifecycle import (TransitionError, approval_gate, assert_editable,
                                                      new_revision, transition)
from app.modules.learning_ai.schemas.common import Applicability, ApplicabilityScope, AssertionBasis, EvidenceRef
from app.modules.learning_ai.schemas.knowledge_record import ConflictRef, RecordStatus

from tests.learning_ai.builders import staff

S = RecordStatus


def _codes(report) -> set[str]:
    return {i.code for i in report.issues}


def test_rule_conflict_on_overlapping_models(make_param_record, reg):
    new = make_param_record(value="10")
    other = make_param_record(value="20", status=S.APPROVED)

    conflicts, semantic = detect_rule_conflicts(new, [other], reg)

    assert semantic == []
    assert len(conflicts) == 1
    assert conflicts[0].field_path == "param:P01|cond=-"
    assert conflicts[0].against_id == str(other.record_id)


def test_no_conflict_when_models_do_not_overlap(make_param_record, reg):
    conflicts, semantic = detect_rule_conflicts(
        make_param_record(value="10"), [make_param_record(value="20", models=["G10"])], reg)

    assert conflicts == [] and semantic == []


def test_unstructured_candidate_goes_to_semantic_review(make_param_record, make_procedure_record, reg):
    procedure = make_procedure_record()

    conflicts, semantic = detect_rule_conflicts(make_param_record(), [procedure], reg)

    assert conflicts == []
    assert semantic == [procedure]


def test_approval_gate_passes_confirmed_record(make_param_record):
    assert approval_gate(make_param_record()).ok


@pytest.mark.parametrize("applicability, code", [
    (Applicability(scope=ApplicabilityScope.SPECIFIC_MODELS, product_models=["F86"],
                   basis=AssertionBasis.INFERRED), "unconfirmed_inference"),
    (Applicability(scope=ApplicabilityScope.SPECIFIC_MODELS, product_models=["F86"],
                   basis=AssertionBasis.STAFF_CONFIRMED, evidence=[EvidenceRef(locator="m2")]), "unbound_evidence"),
    (Applicability(scope=ApplicabilityScope.ALL_MODELS, **staff()), "unsafe_generalization"),
    (Applicability(scope=ApplicabilityScope.SPECIFIC_MODELS, product_models=["F86"],
                   unresolved_mentions=["F99"], **staff()), "unresolved_models"),
])
def test_approval_gate_blocks(make_param_record, applicability, code):
    report = approval_gate(make_param_record(applicability=applicability))

    assert not report.ok
    assert code in _codes(report)


def test_approval_gate_blocks_open_conflict(make_param_record):
    record = make_param_record(conflicts=[ConflictRef(
        conflict_id="c1", against_kind="knowledge_record", against_id="x", field_path="param:P01|cond=-",
        description="khác giá trị", detected_by="rule")])

    assert "open_conflict" in _codes(approval_gate(record))


def test_transition_requires_human_and_passing_gate(make_param_record):
    pending = transition(make_param_record(), S.PENDING_REVIEW, actor="system:extractor")

    with pytest.raises(TransitionError):
        transition(pending, S.APPROVED, actor="system:bot", gate=approval_gate(pending))
    with pytest.raises(TransitionError):
        transition(pending, S.APPROVED, actor="reviewer@qs")

    approved = transition(pending, S.APPROVED, actor="reviewer@qs", gate=approval_gate(pending))
    assert approved.lifecycle.status == S.APPROVED
    assert approved.lifecycle.approved_by == "reviewer@qs"
    assert [e.to_status for e in approved.lifecycle.history] == [S.PENDING_REVIEW, S.APPROVED]
    assert pending.lifecycle.status == S.PENDING_REVIEW


def test_invalid_transition_is_rejected(make_param_record):
    with pytest.raises(TransitionError):
        transition(make_param_record(), S.APPROVED, actor="reviewer@qs")


def test_approved_revision_is_immutable_and_revised(make_param_record):
    approved = make_param_record(status=S.APPROVED)

    with pytest.raises(TransitionError):
        assert_editable(approved)

    revised = new_revision(approved, actor="reviewer@qs", change_summary="cập nhật giá trị")
    assert revised.record_id == approved.record_id
    assert revised.revision_id != approved.revision_id
    assert revised.versioning.version == 2
    assert revised.versioning.parent_revision_id == approved.revision_id
    assert revised.lifecycle.status == S.DRAFT


def test_new_revision_requires_approved_source(make_param_record):
    with pytest.raises(TransitionError):
        new_revision(make_param_record(), actor="reviewer@qs", change_summary="x")
