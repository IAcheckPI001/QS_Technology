

"""Khối dùng chung: bằng chứng, mức độ khẳng định, phạm vi áp dụng, phân loại."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AssertionBasis(str, Enum):
    """Ai/cái gì xác nhận một khẳng định. Áp dụng ở mức TỪNG claim, không ở mức record."""
    DOCUMENT_CONFIRMED = "document_confirmed"   # manual / tài liệu chính thức nói rõ
    STAFF_CONFIRMED = "staff_confirmed"         # nhân viên hỗ trợ khẳng định rõ ràng
    OUTCOME_VERIFIED = "outcome_verified"       # nhân viên hướng dẫn + khách xác nhận đã chạy được
    CUSTOMER_REPORTED = "customer_reported"     # chỉ khách mô tả (thường là triệu chứng)
    INFERRED = "inferred"                       # LLM suy luận, không có câu nguồn nói thẳng
    REVIEWER_CONFIRMED = "reviewer_confirmed"   # chỉ người review được gán giá trị này


# INFERRED được phép tồn tại ở draft, nhưng phải được reviewer xử lý trước khi approve.
BASIS_WITHOUT_EVIDENCE = {AssertionBasis.INFERRED, AssertionBasis.REVIEWER_CONFIRMED}


class EvidenceRef(StrictModel):
    """Con trỏ tới nguồn. KHÔNG chứa văn bản gốc (văn bản nằm ở kho nguồn có phân quyền)."""
    source_id: str | None = None  # id mờ của SourceDocument; gắn sau bước LLM, LLM không tự điền
    locator: str = Field(description="ID tin nhắn ('m12') hoặc vị trí tài liệu ('p4:b3'). Mỗi ref một vị trí.")


class Claim(StrictModel):
    basis: AssertionBasis
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _claim_needs_evidence(self):
        if self.basis not in BASIS_WITHOUT_EVIDENCE and not self.evidence:
            raise ValueError(f"basis={self.basis.value} bắt buộc có evidence")
        return self


class ApplicabilityScope(str, Enum):
    SPECIFIC_MODELS = "specific_models"   # liệt kê cụ thể: ["F86"]
    MODEL_FAMILY = "model_family"         # một dòng sản phẩm đã định nghĩa trong registry
    ALL_MODELS = "all_models"             # chỉ hợp lệ khi có tài liệu/reviewer xác nhận
    UNDETERMINED = "undetermined"         # nguồn không đủ để xác định model


class Applicability(Claim):
    scope: ApplicabilityScope
    product_models: list[str] = Field(default_factory=list)
    model_family: str | None = None
    excluded_models: list[str] = Field(default_factory=list)
    firmware: str | None = Field(default=None, description="Ràng buộc firmware nếu nguồn nêu, vd '>=2.1'")
    conditions: list[str] = Field(default_factory=list, description="Điều kiện phần cứng/cấu hình đi kèm")
    unresolved_mentions: list[str] = Field(
        default_factory=list, description="Tên model được nhắc tới nhưng không map được registry")

    @model_validator(mode="after")
    def _scope_consistency(self):
        s = self.scope
        if s == ApplicabilityScope.SPECIFIC_MODELS and not self.product_models:
            raise ValueError("specific_models cần ít nhất một product_model")
        if s == ApplicabilityScope.MODEL_FAMILY and not self.model_family:
            raise ValueError("model_family cần model_family")
        if s in (ApplicabilityScope.ALL_MODELS, ApplicabilityScope.UNDETERMINED) and self.product_models:
            raise ValueError(f"{s.value} không được kèm product_models")
        if set(self.product_models) & set(self.excluded_models):
            raise ValueError("product_models và excluded_models giao nhau")
        return self


class Classification(StrictModel):
    """Mã chuẩn hóa, cùng không gian giá trị với output query extraction.
    product_models KHÔNG nằm ở đây: nguồn sự thật duy nhất là Applicability."""
    intents: list[str] = Field(min_length=1, description="Các intent truy vấn mà record này trả lời được")
    topic: str
    control_interface: list[str] = Field(default_factory=list)
    spec_attribute: list[str] = Field(default_factory=list)
    connector_ids: list[str] = Field(default_factory=list)
    parameter_ids: list[str] = Field(default_factory=list)
    alarm_codes: list[str] = Field(default_factory=list)