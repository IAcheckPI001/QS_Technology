"""Tầng C: thay đoạn nhạy cảm bằng placeholder ổn định. Hàm thuần.

Placeholder đánh số theo giá trị trong phạm vi một document: cùng giá trị → cùng placeholder
("anh Minh" ở m3 và m9 đều là [PERSON_1]) để Segmenter vẫn hiểu quan hệ. Giá trị gốc
KHÔNG được lưu lại.
"""
from __future__ import annotations

import re
import unicodedata

from .schemas import FindingType, PiiSpan

PLACEHOLDER_PREFIX: dict[FindingType, str] = {
    FindingType.PERSON_NAME: "PERSON",
    FindingType.ORGANIZATION: "ORG",
    FindingType.ADDRESS: "ADDRESS",
    FindingType.PHONE: "PHONE",
    FindingType.EMAIL: "EMAIL",
    FindingType.NATIONAL_ID: "ID",
    FindingType.TAX_CODE: "TAX",
    FindingType.BANK_ACCOUNT: "BANK",
    FindingType.IP_ADDRESS: "IP",
    FindingType.DEVICE_SERIAL: "SERIAL",
    FindingType.OTHER_PII: "PII",
    FindingType.PRICE_AMOUNT: "PRICE",
    FindingType.QUOTE: "PRICE",
    FindingType.DISCOUNT: "DISCOUNT",
    FindingType.PAYMENT_TERMS: "PAYMENT",
}
PLACEHOLDER = re.compile(r"\[[A-Z]+_\d+\]")


def _key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


class Redactor:
    def __init__(self) -> None:
        self._assigned: dict[tuple[str, str], str] = {}
        self._counters: dict[str, int] = {}

    def placeholder(self, kind: FindingType, value: str) -> str:
        prefix = PLACEHOLDER_PREFIX.get(kind, "PII")
        key = (prefix, _key(value))
        if key not in self._assigned:
            self._counters[prefix] = self._counters.get(prefix, 0) + 1
            self._assigned[key] = f"[{prefix}_{self._counters[prefix]}]"
        return self._assigned[key]

    def redact_spans(self, text: str, spans: list[PiiSpan]) -> str:
        """spans phải không chồng lấn (xem pii_patterns.merge_spans)."""
        for s in sorted(spans, key=lambda s: s.start, reverse=True):
            text = text[:s.start] + self.placeholder(s.type, text[s.start:s.end]) + text[s.end:]
        return text

    def redact_value(self, text: str, value: str, kind: FindingType) -> str:
        """Thay mọi lần xuất hiện (không phân biệt hoa/thường, theo ranh giới từ).

        Ưu tiên không lọt hơn chính xác: "minh" trong "minh họa" cũng bị thay.
        """
        if not value or PLACEHOLDER.fullmatch(value):
            return text
        pattern = re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)", re.IGNORECASE)
        return pattern.sub(lambda _: self.placeholder(kind, value), text)
