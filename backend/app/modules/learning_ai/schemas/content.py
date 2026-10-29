
"""Phần content theo từng loại tri thức (discriminated union theo `kind`).

Mỗi phần tử có thể bị phản biện (bước, giá trị tham số, cặp đấu dây, nguyên nhân) là một Claim
riêng, có basis + evidence riêng. Đây là điều kiện để reviewer duyệt từng ý và để phát hiện
xung đột bằng code thay vì bằng LLM.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import Field, model_validator

from .common import Claim, StrictModel


class KnowledgeType(str, Enum):
    WIRING = "wiring"
    PROCEDURE = "procedure"
    PARAMETER_CONFIG = "parameter_config"
    TROUBLESHOOTING = "troubleshooting"
    SPEC_FACT = "spec_fact"


class Severity(str, Enum):
    DANGER = "danger"     # nguy hiểm tính mạng / cháy nổ: luôn đi kèm MỌI chunk
    WARNING = "warning"   # hỏng thiết bị
    CAUTION = "caution"   # sai kết quả


class SafetyWarning(Claim):
    warning_id: str = Field(description="ID cục bộ trong record, vd 'W1'")
    severity: Severity
    text: str
    applies_to_steps: list[int] = Field(default_factory=list, description="Rỗng = áp dụng toàn bộ")


class Prerequisite(Claim):
    text: str


class _BaseContent(StrictModel):
    goal: str
    prerequisites: list[Prerequisite] = Field(default_factory=list)
    safety_warnings: list[SafetyWarning] = Field(default_factory=list)


# ---------- Đấu dây ----------
class WiringConnection(Claim):
    from_connector: str = Field(description="connector_id trong registry")
    from_pin: str | None = None
    to_target: str = Field(description="connector_id hoặc tên thiết bị ngoài (PLC, cảm biến...)")
    to_pin: str | None = None
    signal: str | None = None
    note: str | None = None


class WiringContent(_BaseContent):
    kind: Literal["wiring"] = "wiring"
    connections: list[WiringConnection] = Field(min_length=1)
    verification: list[str] = Field(default_factory=list)


# ---------- Quy trình thao tác ----------
class ProcedureStep(Claim):
    step_no: int = Field(ge=1)
    action: str
    expected_result: str | None = None
    phase: str | None = Field(default=None, description="Nhóm logic, vd 'Chuẩn bị', 'Cài đặt', 'Kiểm tra'")
    depends_on: list[int] = Field(
        default_factory=list, description="Phụ thuộc cứng NGOÀI thứ tự tuần tự (vd bước 7 dùng giá trị đặt ở bước 2)")
    parameter_ids: list[str] = Field(default_factory=list)


class ProcedureContent(_BaseContent):
    kind: Literal["procedure"] = "procedure"
    steps: list[ProcedureStep] = Field(min_length=1)
    completion_check: str | None = None

    @model_validator(mode="after")
    def _steps_consistent(self):
        nos = [s.step_no for s in self.steps]
        if nos != list(range(1, len(nos) + 1)):
            raise ValueError("step_no phải liên tục từ 1")
        for s in self.steps:
            if any(d >= s.step_no for d in s.depends_on):
                raise ValueError(f"bước {s.step_no} phụ thuộc bước không đứng trước nó")
        for w in self.safety_warnings:
            if any(n not in nos for n in w.applies_to_steps):
                raise ValueError(f"{w.warning_id} trỏ tới bước không tồn tại")
        return self


# ---------- Cấu hình tham số ----------
class ParameterSetting(Claim):
    parameter_id: str
    value: str
    unit: str | None = None
    condition: str | None = Field(default=None, description="Điều kiện áp dụng giá trị này")
    default_value: str | None = None


class ParameterConfigContent(_BaseContent):
    kind: Literal["parameter_config"] = "parameter_config"
    settings: list[ParameterSetting] = Field(min_length=1)
    apply_method: str | None = Field(default=None, description="vd 'Lưu EEPROM và khởi động lại nguồn'")
    side_effects: list[str] = Field(default_factory=list)


# ---------- Xử lý lỗi ----------
class Symptom(Claim):
    description: str
    alarm_codes: list[str] = Field(default_factory=list)


class CauseResolution(Claim):
    cause: str
    diagnostic_checks: list[str] = Field(default_factory=list)
    resolution_steps: list[str] = Field(min_length=1)
    resolved_in_source: bool = Field(description="Nguyên nhân này có thực sự giải quyết được ca gốc không")


class TroubleshootingContent(_BaseContent):
    kind: Literal["troubleshooting"] = "troubleshooting"
    symptom: Symptom
    causes: list[CauseResolution] = Field(min_length=1)
    escalation: str | None = None


# ---------- Thông số kỹ thuật ----------
class SpecFact(Claim):
    spec_attributes: str
    value: str
    unit: str | None = None
    condition: str | None = None


class SpecFactContent(StrictModel):
    kind: Literal["spec_fact"] = "spec_fact"
    goal: str
    facts: list[SpecFact] = Field(min_length=1)


KnowledgeContent = Annotated[
    Union[WiringContent, ProcedureContent, ParameterConfigContent, TroubleshootingContent, SpecFactContent],
    Field(discriminator="kind"),
]

CONTENT_MODEL_BY_TYPE: dict[KnowledgeType, type[StrictModel]] = {
    KnowledgeType.WIRING: WiringContent,
    KnowledgeType.PROCEDURE: ProcedureContent,
    KnowledgeType.PARAMETER_CONFIG: ParameterConfigContent,
    KnowledgeType.TROUBLESHOOTING: TroubleshootingContent,
    KnowledgeType.SPEC_FACT: SpecFactContent,
}