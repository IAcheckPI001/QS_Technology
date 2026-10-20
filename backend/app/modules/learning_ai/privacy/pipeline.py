"""Điều phối privacy A → B → C → D cho một SourceDocument.

  A  regex PII có cấu trúc + giá               (pii_patterns)
  B  Ollama theo cửa sổ                        (sensitivity_checker) — bắt buộc, fail-closed
  C  verify + thay placeholder; thực thể PII thay ở MỌI message
  D  chạy lại regex trên kết quả cuối, che nốt nếu còn sót

Chỉ kết quả của pipeline này mới được phép rời server (vd gửi Segmenter).
"""
from __future__ import annotations

import logging
from collections import Counter

from ..ingestion.source_document import SourceDocument
from .pii_patterns import find_regex_spans
from .redactor import Redactor
from .schemas import (CATEGORY_FLAG, DOCUMENT_WIDE_TYPES, REDACTED_CATEGORIES, FindingCategory, FindingType,
                      PrivacyResult, SensitivityFlag)
from .sensitivity_checker import SensitivityChecker

logger = logging.getLogger(__name__)


class PrivacyPipeline:
    def __init__(self, checker: SensitivityChecker) -> None:
        self._checker = checker

    async def run(self, document: SourceDocument) -> PrivacyResult:
        redactor = Redactor()
        pii_types: set[FindingType] = set()
        flags: dict[str, set[SensitivityFlag]] = {}

        # A
        texts: dict[str, str] = {}
        regex_counts: Counter[str] = Counter()
        for unit in document.units:
            spans = find_regex_spans(unit.text)
            texts[unit.locator] = redactor.redact_spans(unit.text, spans)
            for s in spans:
                regex_counts[s.type.value] += 1
                self._record(s.category, s.type, unit.locator, pii_types, flags)
        stage_a = document.with_texts(texts)
        logger.info("privacy stage=A source_id=%s regex_spans=%s", document.source_id, dict(regex_counts))

        # B (raise PrivacyCheckUnavailable → caller dừng)
        outcome = await self._checker.check(stage_a)
        model_counts = Counter(f.category.value for f in outcome.findings)
        logger.info("privacy stage=B source_id=%s model_findings=%s unverified=%d",
                    document.source_id, dict(model_counts), outcome.unverified)

        # C — đoạn dài trước: "Minh ở 12 Nguyễn Trãi" phải được thay trước khi "Minh" làm vỡ nó.
        for f in sorted(outcome.findings, key=lambda f: len(f.text), reverse=True):
            self._record(f.category, f.type, f.locator, pii_types, flags)
            if f.category not in REDACTED_CATEGORIES:
                continue
            targets = texts.keys() if f.type in DOCUMENT_WIDE_TYPES else [f.locator]
            for locator in targets:
                texts[locator] = redactor.redact_value(texts[locator], f.text, f.type)

        # D
        residual = 0
        for locator, text in texts.items():
            spans = find_regex_spans(text)
            if spans:
                residual += len(spans)
                texts[locator] = redactor.redact_spans(text, spans)
        logger.info("privacy stage=D source_id=%s residual=%d pii_types=%s flagged_units=%d",
                    document.source_id, residual, sorted(t.value for t in pii_types), len(flags))

        return PrivacyResult(
            document=document.with_texts(texts),
            checker_model=self._checker.model,
            redaction_applied=True,
            pii_types_detected=sorted(pii_types, key=lambda t: t.value),
            flags_by_locator={k: sorted(v, key=lambda f: f.value) for k, v in sorted(flags.items())},
            unverified_findings=outcome.unverified,
            residual_redactions=residual,
        )

    @staticmethod
    def _record(category: FindingCategory, kind: FindingType, locator: str,
                pii_types: set[FindingType], flags: dict[str, set[SensitivityFlag]]) -> None:
        if category == FindingCategory.PII:
            pii_types.add(kind)
        elif category in CATEGORY_FLAG:
            flags.setdefault(locator, set()).add(CATEGORY_FLAG[category])
