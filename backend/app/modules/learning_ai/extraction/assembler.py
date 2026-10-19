"""Ghép DTO của LLM thành KnowledgeRecord draft. Hệ thống (không phải LLM) gán ID, provenance, privacy."""
from __future__ import annotations

from dataclasses import dataclass

from ..schemas.common import AssertionBasis
from ..schemas.knowledge_record import KnowledgeRecord, PrivacyInfo, Provenance, Visibility
from ..schemas.llm_output import ExtractedRecord


@dataclass(frozen=True)
class ExtractionRun:
    run_id: str
    extractor_model: str
    prompt_version: str
    registry_version: str


def assemble_draft(dto: ExtractedRecord, *, source_id: str, run: ExtractionRun,
                   pii_types_detected: list[str]) -> KnowledgeRecord:
    data = dto.model_dump(mode="python")
    record = KnowledgeRecord(
        title=data["title"],
        summary=data["summary"],
        classification=data["classification"],
        applicability=data["applicability"],
        content=data["content"],
        provenance=Provenance(source_ids=[source_id], extraction_run_id=run.run_id,
                              extractor_model=run.extractor_model, prompt_version=run.prompt_version,
                              registry_version=run.registry_version),
        privacy=PrivacyInfo(
            redaction_applied=True,
            pii_types_detected=pii_types_detected,
            contains_customer_specific=dto.contains_customer_specific,
            visibility=Visibility.RESTRICTED if dto.contains_customer_specific else Visibility.INTERNAL,
        ),
    )
    for _, claim in record.iter_claims():
        for ev in claim.evidence:
            if ev.source_id is None:
                ev.source_id = source_id
        if claim.basis == AssertionBasis.REVIEWER_CONFIRMED:   # phòng thủ: LLM không có quyền này
            claim.basis = AssertionBasis.INFERRED
    return record
