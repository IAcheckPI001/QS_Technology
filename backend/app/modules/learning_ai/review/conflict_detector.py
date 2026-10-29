"""Phát hiện xung đột bằng luật trên nội dung có cấu trúc.

Loại tri thức có giá trị rời rạc (tham số, thông số, đấu dây) → so sánh bằng code, chính xác,
rẻ, giải thích được. Procedure/troubleshooting → chỉ trả về danh sách ứng viên cần LLM/reviewer
so sánh ngữ nghĩa; không để LLM tự quyết xung đột.
"""
from __future__ import annotations

import hashlib
import unicodedata

from ..schemas.common import Applicability, ApplicabilityScope
from ..schemas.content import ParameterConfigContent, SpecFactContent, WiringContent
from ..schemas.knowledge_record import ConflictRef, KnowledgeRecord
from ..schemas.registry import RegistrySnapshot


def resolve_models(a: Applicability, reg: RegistrySnapshot) -> set[str] | None:
    """Tập model cụ thể; None = chưa xác định (phải coi là có thể giao nhau)."""
    if a.scope == ApplicabilityScope.UNDETERMINED:
        return None
    if a.scope == ApplicabilityScope.ALL_MODELS:
        models = set(reg.allowed("product_models"))
    elif a.scope == ApplicabilityScope.MODEL_FAMILY:
        models = set(reg.models_of_family(a.model_family or ""))
    else:
        models = set(a.product_models)
    return models - set(a.excluded_models)


def models_overlap(a: Applicability, b: Applicability, reg: RegistrySnapshot) -> bool:
    ma, mb = resolve_models(a, reg), resolve_models(b, reg)
    return True if ma is None or mb is None else bool(ma & mb)


def _norm(s: str | None) -> str:
    return " ".join(unicodedata.normalize("NFC", (s or "")).lower().split())


def _keyed(record: KnowledgeRecord) -> dict[tuple, tuple]:
    ct = record.content
    if isinstance(ct, ParameterConfigContent):
        return {("param", s.parameter_id, _norm(s.condition)): (_norm(s.value), _norm(s.unit)) for s in ct.settings}
    if isinstance(ct, SpecFactContent):
        return {("spec", f.spec_attributes, _norm(f.condition)): (_norm(f.value), _norm(f.unit)) for f in ct.facts}
    if isinstance(ct, WiringContent):
        return {("wire", w.from_connector, _norm(w.from_pin)): (_norm(w.to_target), _norm(w.to_pin))
                for w in ct.connections}
    return {}


def detect_rule_conflicts(new: KnowledgeRecord, approved_candidates: list[KnowledgeRecord],
                          reg: RegistrySnapshot) -> tuple[list[ConflictRef], list[KnowledgeRecord]]:
    """Trả về (xung đột chắc chắn, ứng viên cần so sánh ngữ nghĩa)."""
    conflicts: list[ConflictRef] = []
    semantic: list[KnowledgeRecord] = []
    mine = _keyed(new)
    for other in approved_candidates:
        if other.record_id == new.record_id or not models_overlap(new.applicability, other.applicability, reg):
            continue
        theirs = _keyed(other)
        if not mine or not theirs:
            semantic.append(other)
            continue
        for key in mine.keys() & theirs.keys():
            if mine[key] != theirs[key]:
                cid = hashlib.sha1(f"{new.revision_id}|{other.revision_id}|{key}".encode()).hexdigest()[:16]
                conflicts.append(ConflictRef(
                    conflict_id=cid, against_kind="knowledge_record", against_id=str(other.record_id),
                    against_revision=str(other.revision_id), field_path=f"{key[0]}:{key[1]}|cond={key[2] or '-'}",
                    description=f"giá trị mới {mine[key]} ≠ đã duyệt {theirs[key]}", detected_by="rule"))
    return conflicts, semantic
