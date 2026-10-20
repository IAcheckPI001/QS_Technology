"""Dữ liệu dựng sẵn cho test learning_ai: registry nhỏ, factory record và fake provider/repository."""
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.modules.learning_ai.schemas.common import (Applicability, ApplicabilityScope, AssertionBasis,
                                                    Classification, EvidenceRef)
from app.modules.learning_ai.schemas.content import (ParameterConfigContent, ParameterSetting, ProcedureContent,
                                                     ProcedureStep, SafetyWarning, Severity)
from app.modules.learning_ai.schemas.knowledge_record import (KnowledgeRecord, Lifecycle, PrivacyInfo, Provenance,
                                                              RecordStatus)

REGISTRY_VERSION = "reg-test-1"
SOURCE_ID = "src-1"

RAW_REGISTRY = {
    "intents": ["setup", "troubleshoot"],
    "topics": ["configuration", "installation"],
    "product_models": ["F54", "F86", "G10"],
    "control_interface": ["modbus"],
    "spec_attributes": ["rated_power"],
    "connectors": ["CN1", "CN2"],
    "parameters": ["P01", "P02"],
    "alarm_codes": ["E01"],
    "_aliases": {"parameters": {"P01": ["Pr.01"]}},
    "_model_families": {"F-series": ["F54", "F86"]},
}


def staff(locator: str = "m2", source_id: str | None = SOURCE_ID) -> dict:
    return {"basis": AssertionBasis.STAFF_CONFIRMED,
            "evidence": [EvidenceRef(source_id=source_id, locator=locator)]}


def doc(locator: str = "p1:b1") -> dict:
    return {"basis": AssertionBasis.DOCUMENT_CONFIRMED,
            "evidence": [EvidenceRef(source_id=SOURCE_ID, locator=locator)]}


def provenance() -> Provenance:
    return Provenance(source_ids=[SOURCE_ID], extraction_run_id="run-1", extractor_model="test-model",
                      prompt_version="p-1", registry_version=REGISTRY_VERSION)


def specific(models: list[str]) -> Applicability:
    return Applicability(scope=ApplicabilityScope.SPECIFIC_MODELS, product_models=models, **staff())


def param_record(*, value: str = "10", parameter_id: str = "P01", models: list[str] | None = None,
                 status: RecordStatus = RecordStatus.DRAFT, **overrides) -> KnowledgeRecord:
    data = dict(
        title="Cài đặt tốc độ",
        summary="Đặt P01 để chỉnh tốc độ",
        classification=Classification(intents=["setup"], topic="configuration", parameter_ids=[parameter_id]),
        applicability=specific(models or ["F86"]),
        content=ParameterConfigContent(
            goal="Chỉnh tốc độ",
            settings=[ParameterSetting(parameter_id=parameter_id, value=value, unit="Hz", **staff())]),
        provenance=provenance(),
        lifecycle=Lifecycle(status=status),
        privacy=PrivacyInfo(redaction_applied=True),
    )
    data.update(overrides)
    return KnowledgeRecord(**data)


def procedure_record(*, status: RecordStatus = RecordStatus.DRAFT) -> KnowledgeRecord:
    """6 bước dài: 1–2 cùng phase, bước 5 phụ thuộc bước 3, DANGER gắn bước 1, WARNING gắn bước 6."""
    steps = [ProcedureStep(step_no=n, action=f"Thao tác bước {n} " + "x" * 400,
                           phase="Chuẩn bị" if n <= 2 else None,
                           depends_on=[3] if n == 5 else [], **staff())
             for n in range(1, 7)]
    warnings = [
        SafetyWarning(warning_id="W1", severity=Severity.DANGER, text="Ngắt nguồn trước khi mở vỏ",
                      applies_to_steps=[1], **doc()),
        SafetyWarning(warning_id="W2", severity=Severity.WARNING, text="Không siết quá lực",
                      applies_to_steps=[6], **doc()),
    ]
    return KnowledgeRecord(
        title="Lắp đặt biến tần",
        summary="Quy trình lắp đặt",
        classification=Classification(intents=["setup"], topic="installation"),
        applicability=specific(["F86"]),
        content=ProcedureContent(goal="Lắp đặt", steps=steps, safety_warnings=warnings),
        provenance=provenance(),
        lifecycle=Lifecycle(status=status),
        privacy=PrivacyInfo(redaction_applied=True),
    )


# ---------------- ingestion / privacy ----------------
Responder = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class Row:
    user_message: str | None
    staff_message: str | None


class FakeProvider:
    model = "fake-ollama"

    def __init__(self, responder: Responder) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responder = responder

    async def chat_complete_json(self, messages, response_format=None):
        payload = json.loads(messages[-1]["content"])
        self.calls.append(payload)
        return self._responder(payload)


def finding(locator: str, category: str, kind: str, text: str) -> dict[str, str]:
    return {"locator": locator, "category": category, "type": kind, "text": text}


def reviewing(*findings: dict[str, str]) -> Responder:
    """Responder hợp lệ: xác nhận đã đọc mọi target, trả finding thuộc cửa sổ này."""
    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        locators = [t["locator"] for t in payload["targets"]]
        texts = {t["locator"]: t["text"] for t in payload["targets"]}
        own = [f for f in findings if f["locator"] in locators and f["text"] in texts[f["locator"]]]
        return {"reviewed_locators": locators, "findings": own}
    return respond


def word_count(text: str) -> int:
    return len(text.split())


class FakeRepository:
    def __init__(self, rows):
        self.rows = rows

    async def list_for_session(self, *, session_id):
        return self.rows
