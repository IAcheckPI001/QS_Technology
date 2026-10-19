"""Vòng đời record và approval gate.

Quy tắc bất biến: revision đã APPROVED không bao giờ bị sửa nội dung. Muốn sửa → new_revision()
tạo DRAFT mới cùng record_id, version+1. Khi revision mới được duyệt, revision cũ → SUPERSEDED
(thực hiện trong cùng transaction ở repository, kèm outbox event cho indexer).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..extraction.validators import ValidationReport
from ..schemas.common import ApplicabilityScope, AssertionBasis
from ..schemas.content import Severity, TroubleshootingContent
from ..schemas.knowledge_record import (ConflictStatus, KnowledgeRecord, RecordStatus, ReviewEvent,
                                        Visibility)

S = RecordStatus
TRANSITIONS: dict[RecordStatus, set[RecordStatus]] = {
    S.DRAFT: {S.PENDING_REVIEW, S.REJECTED},
    S.PENDING_REVIEW: {S.APPROVED, S.REJECTED, S.DRAFT},   # DRAFT = request_changes
    S.APPROVED: {S.SUPERSEDED, S.ARCHIVED},
    S.REJECTED: set(),
    S.SUPERSEDED: set(),
    S.ARCHIVED: set(),
}
EDITABLE = {S.DRAFT, S.PENDING_REVIEW}
_SAFETY_OK_BASIS = {AssertionBasis.DOCUMENT_CONFIRMED, AssertionBasis.STAFF_CONFIRMED,
                    AssertionBasis.REVIEWER_CONFIRMED}


class TransitionError(Exception):
    pass


def approval_gate(record: KnowledgeRecord) -> ValidationReport:
    """Điều kiện chặn approve. Chạy SAU validate_record() và SAU conflict detection."""
    r = ValidationReport()
    for path, claim in record.iter_claims():
        if claim.basis == AssertionBasis.INFERRED:
            r.add("error", "unconfirmed_inference", path, "reviewer phải xác nhận, sửa hoặc xóa ý suy luận")
        if any(ev.source_id is None for ev in claim.evidence):
            r.add("error", "unbound_evidence", path, "evidence chưa gắn source_id")
    for i, w in enumerate(record.content.safety_warnings if hasattr(record.content, "safety_warnings") else []):
        if w.basis not in _SAFETY_OK_BASIS:
            r.add("error", "weak_safety_basis", f"content.safety_warnings[{i}]",
                  "cảnh báo an toàn phải đến từ tài liệu, nhân viên hoặc reviewer")
        if w.severity == Severity.DANGER and not w.text:
            r.add("error", "empty_danger", f"content.safety_warnings[{i}]", "")

    a = record.applicability
    if a.scope == ApplicabilityScope.ALL_MODELS and a.basis not in {AssertionBasis.DOCUMENT_CONFIRMED,
                                                                    AssertionBasis.REVIEWER_CONFIRMED}:
        r.add("error", "unsafe_generalization", "applicability",
              "all_models chỉ được duyệt khi tài liệu hoặc reviewer xác nhận")
    if a.unresolved_mentions:
        r.add("error", "unresolved_models", "applicability.unresolved_mentions",
              f"cần map vào registry hoặc xóa: {a.unresolved_mentions}")
    if a.scope == ApplicabilityScope.UNDETERMINED:
        r.add("warning", "undetermined_scope", "applicability",
              "sẽ chỉ được trả về khi truy vấn không nêu model, kèm cảnh báo")

    for c in record.conflicts:
        if c.status == ConflictStatus.OPEN:
            r.add("error", "open_conflict", f"conflicts[{c.conflict_id}]", c.description)

    if isinstance(record.content, TroubleshootingContent) and not any(
            x.resolved_in_source or x.basis == AssertionBasis.DOCUMENT_CONFIRMED for x in record.content.causes):
        r.add("warning", "unverified_resolution", "content.causes",
              "không nguyên nhân nào được xác nhận đã giải quyết ca gốc")
    if record.privacy.visibility == Visibility.RESTRICTED:
        r.add("warning", "restricted", "privacy", "record sẽ KHÔNG vào index chính thức")
    return r


def transition(record: KnowledgeRecord, to: RecordStatus, *, actor: str, note: str | None = None,
               gate: ValidationReport | None = None) -> KnowledgeRecord:
    cur = record.lifecycle.status
    if to not in TRANSITIONS[cur]:
        raise TransitionError(f"{cur.value} → {to.value} không hợp lệ")
    if to == S.APPROVED:
        if actor.startswith("system:"):
            raise TransitionError("chỉ người được duyệt record")
        if gate is None or not gate.ok:
            raise TransitionError("approval_gate chưa đạt")
    new = record.model_copy(deep=True)
    new.lifecycle.status = to
    new.lifecycle.history.append(ReviewEvent(actor=actor, action=f"to_{to.value}",
                                             from_status=cur, to_status=to, note=note))
    if to == S.APPROVED:
        new.lifecycle.approved_by = actor
        new.lifecycle.approved_at = datetime.now(timezone.utc)
    return new


def assert_editable(record: KnowledgeRecord) -> None:
    if record.lifecycle.status not in EDITABLE:
        raise TransitionError(f"record {record.lifecycle.status.value} là bất biến; dùng new_revision()")


def new_revision(approved: KnowledgeRecord, *, actor: str, change_summary: str) -> KnowledgeRecord:
    if approved.lifecycle.status != S.APPROVED:
        raise TransitionError("chỉ tạo revision mới từ bản đã duyệt")
    new = approved.model_copy(deep=True)
    new.revision_id = uuid4()
    new.versioning.version = approved.versioning.version + 1
    new.versioning.parent_revision_id = approved.revision_id
    new.versioning.change_summary = change_summary
    new.lifecycle = type(approved.lifecycle)(created_by=actor)
    new.conflicts = []
    return new
