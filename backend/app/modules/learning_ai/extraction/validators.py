"""Kiểm tra hậu-LLM, hoàn toàn deterministic. Chạy trước khi record được submit review.

Mục tiêu: bắt các lỗi LLM hay mắc mà schema strict không bắt được:
  - bịa ID tin nhắn / trang tài liệu
  - gán staff_confirmed cho câu do khách nói
  - mã registry ngoài danh mục (với các field không inject enum vì danh mục lớn)
  - classification không khớp với nội dung (parameter dùng trong bước nhưng không có trong parameter_ids)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..schemas.common import AssertionBasis
from ..schemas.content import ParameterConfigContent, ProcedureContent, TroubleshootingContent, WiringContent
from ..schemas.knowledge_record import KnowledgeRecord
from ..schemas.registry import RegistrySnapshot


class Role(str, Enum):
    STAFF = "staff"
    CUSTOMER = "customer"
    SYSTEM = "system"
    DOCUMENT = "document"


@dataclass(frozen=True)
class SourceView:
    """Chỉ mục locator → vai trò của một nguồn đã ẩn danh. Không cần nạp văn bản để validate."""
    source_id: str
    units: dict[str, Role]
    segment_locators: frozenset[str] = frozenset()  # locator thuộc segment đang trích xuất (pass 1)


@dataclass
class Issue:
    severity: str          # "error" chặn submit/approve | "warning" hiển thị cho reviewer
    code: str
    path: str
    message: str


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def add(self, severity: str, code: str, path: str, message: str) -> None:
        self.issues.append(Issue(severity, code, path, message))


# basis → những vai trò BẮT BUỘC phải có trong evidence
_REQUIRED_ROLES: dict[AssertionBasis, set[Role]] = {
    AssertionBasis.STAFF_CONFIRMED: {Role.STAFF},
    AssertionBasis.CUSTOMER_REPORTED: {Role.CUSTOMER},
    AssertionBasis.DOCUMENT_CONFIRMED: {Role.DOCUMENT},
    AssertionBasis.OUTCOME_VERIFIED: {Role.STAFF, Role.CUSTOMER},
}


def validate_evidence(record: KnowledgeRecord, sources: dict[str, SourceView], report: ValidationReport) -> None:
    for path, claim in record.iter_claims():
        roles: set[Role] = set()
        for ev in claim.evidence:
            src = sources.get(ev.source_id or "")
            if src is None:
                report.add("error", "unknown_source", path, f"source_id={ev.source_id!r} không tồn tại")
                continue
            role = src.units.get(ev.locator)
            if role is None:
                report.add("error", "hallucinated_locator", path, f"locator {ev.locator!r} không có trong nguồn")
                continue
            if src.segment_locators and ev.locator not in src.segment_locators:
                report.add("warning", "outside_segment", path, f"{ev.locator} nằm ngoài segment đã tách")
            roles.add(role)
        missing = _REQUIRED_ROLES.get(claim.basis, set()) - roles
        if claim.evidence and missing:
            report.add("error", "basis_role_mismatch", path,
                       f"basis={claim.basis.value} nhưng evidence thiếu vai trò {[r.value for r in missing]}")


def validate_registry(record: KnowledgeRecord, reg: RegistrySnapshot, report: ValidationReport) -> None:
    c, a = record.classification, record.applicability
    checks: list[tuple[str, str, list[str]]] = [
        ("classification.intents", "intents", c.intents),
        ("classification.topic", "topic", [c.topic]),
        ("classification.control_interface", "control_interface", c.control_interface),
        ("classification.spec_attributes", "spec_attributes", c.spec_attributes),
        ("classification.connector_ids", "connector_ids", c.connector_ids),
        ("classification.parameter_ids", "parameter_ids", c.parameter_ids),
        ("classification.alarm_codes", "alarm_codes", c.alarm_codes),
        ("applicability.product_models", "product_models", a.product_models),
        ("applicability.excluded_models", "product_models", a.excluded_models),
    ]
    for path, fld, values in checks:
        for bad in reg.unknown(fld, values):
            report.add("error", "unknown_code", path, f"{bad!r} không có trong registry {reg.version}")
    if a.model_family and not reg.models_of_family(a.model_family):
        report.add("error", "unknown_family", "applicability.model_family", a.model_family)

    # Nhất quán classification ↔ content: mã dùng trong nội dung phải xuất hiện trong classification,
    # nếu không filter theo parameter_ids / alarm_codes ở retrieval sẽ bỏ sót record.
    used_params, used_conns, used_alarms = _codes_used_in_content(record)
    for kind, used, declared in (("parameter_ids", used_params, c.parameter_ids),
                                 ("connector_ids", used_conns, c.connector_ids),
                                 ("alarm_codes", used_alarms, c.alarm_codes)):
        missing = used - set(declared)
        if missing:
            report.add("error", "classification_incomplete", f"classification.{kind}",
                       f"nội dung dùng {sorted(missing)} nhưng classification không khai báo")


def _codes_used_in_content(record: KnowledgeRecord) -> tuple[set[str], set[str], set[str]]:
    p: set[str] = set(); cn: set[str] = set(); al: set[str] = set()
    ct = record.content
    if isinstance(ct, ParameterConfigContent):
        p |= {s.parameter_id for s in ct.settings}
    elif isinstance(ct, ProcedureContent):
        for s in ct.steps:
            p |= set(s.parameter_ids)
    elif isinstance(ct, WiringContent):
        cn |= {x.from_connector for x in ct.connections}
    elif isinstance(ct, TroubleshootingContent):
        al |= set(ct.symptom.alarm_codes)
    return p, cn, al


def validate_record(record: KnowledgeRecord, sources: dict[str, SourceView],
                    reg: RegistrySnapshot) -> ValidationReport:
    report = ValidationReport()
    validate_evidence(record, sources, report)
    validate_registry(record, reg, report)
    if record.provenance.registry_version != reg.version:
        report.add("warning", "registry_drift", "provenance.registry_version",
                   f"trích xuất với {record.provenance.registry_version}, đang validate với {reg.version}")
    return report
