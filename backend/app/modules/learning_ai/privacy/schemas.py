"""Hợp đồng dữ liệu của bước privacy: DTO đầu ra Ollama và kết quả do hệ thống tạo.

LLM chỉ BÁO CÁO finding; hệ thống quyết định che hay gắn cờ theo category.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import Field

from ..ingestion.source_document import SourceDocument
from ..schemas.common import StrictModel


class PrivacyCheckUnavailable(Exception):
    """Không kiểm tra được privacy đầy đủ → không được xử lý tiếp (fail-closed)."""


class FindingCategory(str, Enum):
    PII = "pii"
    PRICING = "pricing"
    POLICY = "policy"
    CUSTOMER_SPECIFIC = "customer_specific"


class FindingType(str, Enum):
    # pii
    PERSON_NAME = "person_name"
    ORGANIZATION = "organization"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    NATIONAL_ID = "national_id"
    TAX_CODE = "tax_code"
    BANK_ACCOUNT = "bank_account"
    IP_ADDRESS = "ip_address"
    DEVICE_SERIAL = "device_serial"
    OTHER_PII = "other_pii"
    # pricing
    PRICE_AMOUNT = "price_amount"
    DISCOUNT = "discount"
    QUOTE = "quote"
    PAYMENT_TERMS = "payment_terms"
    # policy
    WARRANTY = "warranty"
    RETURN_POLICY = "return_policy"
    INTERNAL_POLICY = "internal_policy"
    CONTRACT_TERM = "contract_term"
    # customer_specific
    SITE_CONFIG = "site_config"
    OTHER = "other"


class SensitivityFlag(str, Enum):
    PRICING = "pricing"
    POLICY_COMMITMENT = "policy_commitment"
    CUSTOMER_SPECIFIC = "customer_specific"


CATEGORY_FLAG: dict[FindingCategory, SensitivityFlag] = {
    FindingCategory.PRICING: SensitivityFlag.PRICING,
    FindingCategory.POLICY: SensitivityFlag.POLICY_COMMITMENT,
    FindingCategory.CUSTOMER_SPECIFIC: SensitivityFlag.CUSTOMER_SPECIFIC,
}
# Category bị thay bằng placeholder; còn lại chỉ gắn cờ.
REDACTED_CATEGORIES = frozenset({FindingCategory.PII, FindingCategory.PRICING})
# Thực thể được thay ở MỌI message của document, kể cả nơi model bỏ sót.
DOCUMENT_WIDE_TYPES = frozenset({
    FindingType.PERSON_NAME, FindingType.ORGANIZATION, FindingType.ADDRESS, FindingType.PHONE,
    FindingType.EMAIL, FindingType.NATIONAL_ID, FindingType.TAX_CODE, FindingType.BANK_ACCOUNT,
    FindingType.IP_ADDRESS, FindingType.DEVICE_SERIAL, FindingType.OTHER_PII,
})


# ---------------- DTO đầu ra Ollama (mỗi cửa sổ) ----------------
class Finding(StrictModel):
    locator: str = Field(description="Locator của message chứa đoạn nhạy cảm, vd 'm3'")
    category: FindingCategory
    type: FindingType
    text: str = Field(description="Chuỗi con NGUYÊN VĂN trong message")


class SensitivityOutput(StrictModel):
    reviewed_locators: list[str] = Field(description="Mọi locator mục tiêu đã được đọc")
    findings: list[Finding]


# ---------------- Nội bộ ----------------
@dataclass(frozen=True)
class PiiSpan:
    start: int
    end: int
    category: FindingCategory
    type: FindingType


class PrivacyResult(StrictModel):
    document: SourceDocument
    checker_model: str
    redaction_applied: bool
    pii_types_detected: list[FindingType]
    flags_by_locator: dict[str, list[SensitivityFlag]]
    unverified_findings: int = Field(description="Finding của LLM bị loại vì text/locator không khớp nguồn")
    residual_redactions: int = Field(description="Số span tầng D còn bắt được sau tầng A–C")
