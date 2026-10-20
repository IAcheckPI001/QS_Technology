from app.modules.learning_ai.extraction.assembler import ExtractionRun, assemble_draft
from app.modules.learning_ai.extraction.validators import validate_record
from app.modules.learning_ai.schemas.common import Applicability, ApplicabilityScope, AssertionBasis, EvidenceRef
from app.modules.learning_ai.schemas.content import KnowledgeType, ParameterConfigContent, ParameterSetting
from app.modules.learning_ai.schemas.knowledge_record import RecordStatus, Visibility
from app.modules.learning_ai.schemas.llm_output import extraction_model_for
from app.modules.learning_ai.schemas.registry import RegistrySnapshot

from tests.learning_ai.builders import RAW_REGISTRY, REGISTRY_VERSION, SOURCE_ID, staff

RUN = ExtractionRun(run_id="run-1", extractor_model="test-model", prompt_version="p-1",
                    registry_version=REGISTRY_VERSION)


def _dto(*, customer_specific: bool = False):
    model = extraction_model_for(KnowledgeType.PARAMETER_CONFIG)
    return model(
        title="Cài đặt tốc độ",
        summary="Đặt P01",
        classification={"intents": ["setup"], "topic": "configuration", "parameter_ids": ["P01"]},
        applicability={"scope": "specific_models", "product_models": ["F86"], "basis": "reviewer_confirmed"},
        content={"goal": "Chỉnh tốc độ", "settings": [
            {"parameter_id": "P01", "value": "10", "basis": "staff_confirmed", "evidence": [{"locator": "m2"}]}]},
        contains_customer_specific=customer_specific,
    )


def _codes(report) -> set[str]:
    return {i.code for i in report.issues}


def test_assemble_draft_binds_source_and_strips_reviewer_basis():
    record = assemble_draft(_dto(), source_id=SOURCE_ID, run=RUN, pii_types_detected=["phone"],
                            redaction_applied=True)

    assert record.lifecycle.status == RecordStatus.DRAFT
    assert record.provenance.source_ids == [SOURCE_ID]
    assert record.content.settings[0].evidence[0].source_id == SOURCE_ID
    assert record.applicability.basis == AssertionBasis.INFERRED
    assert record.privacy.visibility == Visibility.INTERNAL
    assert record.privacy.pii_types_detected == ["phone"]


def test_assemble_draft_restricts_customer_specific_content():
    record = assemble_draft(_dto(customer_specific=True), source_id=SOURCE_ID, run=RUN, pii_types_detected=[],
                            redaction_applied=False)

    assert record.privacy.visibility == Visibility.RESTRICTED


def test_validate_record_accepts_consistent_record(make_param_record, sources, reg):
    report = validate_record(make_param_record(), sources, reg)

    assert report.ok
    assert report.issues == []


def test_validate_record_rejects_hallucinated_locator(make_param_record, sources, reg):
    record = make_param_record(applicability=Applicability(
        scope=ApplicabilityScope.SPECIFIC_MODELS, product_models=["F86"], **staff(locator="m99")))

    assert "hallucinated_locator" in _codes(validate_record(record, sources, reg))


def test_validate_record_rejects_basis_role_mismatch(make_param_record, sources, reg):
    record = make_param_record(applicability=Applicability(
        scope=ApplicabilityScope.SPECIFIC_MODELS, product_models=["F86"], **staff(locator="m1")))

    report = validate_record(record, sources, reg)
    assert not report.ok
    assert "basis_role_mismatch" in _codes(report)


def test_validate_record_rejects_unknown_registry_code(make_param_record, sources, reg):
    report = validate_record(make_param_record(parameter_id="P99"), sources, reg)

    assert "unknown_code" in _codes(report)


def test_validate_record_rejects_incomplete_classification(make_param_record, sources, reg):
    record = make_param_record(content=ParameterConfigContent(goal="Chỉnh", settings=[
        ParameterSetting(parameter_id="P02", value="1", basis=AssertionBasis.STAFF_CONFIRMED,
                         evidence=[EvidenceRef(source_id=SOURCE_ID, locator="m2")])]))

    assert "classification_incomplete" in _codes(validate_record(record, sources, reg))


def test_validate_record_warns_on_registry_drift(make_param_record, sources):
    newer = RegistrySnapshot.from_dict(RAW_REGISTRY, "reg-test-2")

    report = validate_record(make_param_record(), sources, newer)
    assert report.ok
    assert _codes(report) == {"registry_drift"}
