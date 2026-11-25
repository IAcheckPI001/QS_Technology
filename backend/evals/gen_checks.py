"""Kiểm tự động câu trả lời của bước sinh (không gọi LLM). Dùng bởi `run_generation_eval.py`.

Chỉ phát hiện *dấu hiệu* để người chấm ưu tiên: khớp chuỗi không bắt được nhầm cột trong bảng, diễn đạt lại cùng nghĩa
hay thiếu ý. Không thay thế chấm tay (kế hoạch: docs/ai/reports/website_qa_retrieval_eval_plan_2026-11-25.md §9).
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.modules.chatbot.sources import cited_source_ids  # noqa: E402

_CITATION = re.compile(r"\[[^\[\]]*\bS\d+\b[^\[\]]*\]")
_LIST_PREFIX = re.compile(r"(?m)^\s*(?:\d+[.)]|[-*•])\s+")
_NUMBER = re.compile(r"(?<![\w.#])\d+(?:[.,]\d+)?")
# Mã kỹ thuật: #12010, CN1, M1920, AX1.ENA, PUL1+ (chữ rồi số).
_CODE = re.compile(r"#\d+|(?<![\w])[A-Za-z]{1,4}\d+[A-Za-z0-9.+\-]*")
_SENTENCE = re.compile(r"(?<=[.!?;:])\s+|\n+")

_ABSTAIN = (
    "không có thông tin", "chưa có thông tin", "không được đề cập", "không đề cập", "không tìm thấy",
    "chưa tìm thấy", "tài liệu hiện có không", "tài liệu không", "chưa xác định được", "không có trong tài liệu",
    "không có dữ liệu", "chưa có dữ liệu", "chưa có tài liệu", "không có tài liệu", "not mentioned", "no information", "not found in", "does not mention",
)


def compact(text: str) -> str:
    """Dạng so sánh: NFC, chữ thường, bỏ khoảng trắng, `×`→`x`, `,`→`.` giữa hai chữ số."""
    text = unicodedata.normalize("NFC", text or "").lower().replace("×", "x")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return re.sub(r"\s+", "", text)


def strip_markup(answer: str) -> str:
    """Bỏ `[S#]` và số thứ tự danh sách; phần còn lại mới có con số/mã do model viết."""
    return _LIST_PREFIX.sub("", _CITATION.sub("", answer or ""))


def numbers_in(text: str) -> list[str]:
    return list(dict.fromkeys(m.replace(",", ".") for m in _NUMBER.findall(text or "")))


def codes_in(text: str) -> list[str]:
    return list(dict.fromkeys(m.rstrip(".-").upper() for m in _CODE.findall(text or "")))


def _present(token: str, haystack_compact: str) -> bool:
    """Số phải khớp nguyên cụm (220 không khớp trong 2200); mã khớp không phân biệt hoa thường."""
    needle = token.lower()
    return re.search(rf"(?<![\d.]){re.escape(needle)}(?![\d]|\.\d)", haystack_compact) is not None


def facts_found(answer: str, facts: list[str]) -> tuple[list[str], list[str]]:
    """(tìm thấy, thiếu). Fact `re:<mẫu>` là regex trên câu trả lời; còn lại là chuỗi con (dạng `compact`)."""
    haystack = compact(strip_markup(answer))
    found, missing = [], []
    for fact in facts:
        if fact.startswith("re:"):
            ok = re.search(fact[3:], answer or "", flags=re.IGNORECASE) is not None
        else:
            ok = compact(fact) in haystack
        (found if ok else missing).append(fact)
    return found, missing


def invalid_citations(answer: str, source_ids: list[str]) -> list[str]:
    """`[S#]` trong câu trả lời không có trong các nguồn đã đưa cho model."""
    return [s for s in cited_source_ids(answer) if s not in set(source_ids)]


def is_abstention(answer: str) -> bool:
    low = (answer or "").lower()
    return any(phrase in low for phrase in _ABSTAIN)


def tokens_unsupported(text: str, evidence: list[str], ignore: str = "") -> list[str]:
    """Số và mã trong `text` không xuất hiện trong bất kỳ đoạn `evidence` nào (trừ những gì có trong `ignore`,
    thường là câu hỏi của người dùng)."""
    haystack = compact(" ".join(evidence))
    skip = compact(ignore)
    out = []
    for token in [*numbers_in(text), *codes_in(text)]:
        if _present(token, haystack) or _present(token, skip):
            continue
        out.append(token)
    return out


@dataclass
class SentenceCheck:
    sentence: str
    cited: list[str]
    missing: list[str]


def citation_support(answer: str, sources: dict[str, str], question: str = "") -> list[SentenceCheck]:
    """Câu có `[S#]` mà số/mã trong câu không nằm trong chunk được trích (dấu hiệu trích sai chỗ hoặc bịa số)."""
    bad = []
    for sentence in _SENTENCE.split(answer or ""):
        ids = cited_source_ids(sentence)
        if not ids:
            continue
        evidence = [sources[i] for i in ids if i in sources]
        if not evidence:
            continue
        missing = tokens_unsupported(strip_markup(sentence), evidence, ignore=question)
        if missing:
            bad.append(SentenceCheck(sentence.strip(), ids, missing))
    return bad


@dataclass
class AutoFlags:
    facts_total: int = 0
    facts_found: list[str] = field(default_factory=list)
    facts_missing: list[str] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    no_citation: bool = False
    numbers_not_in_context: list[str] = field(default_factory=list)
    unsupported_sentences: list[dict[str, Any]] = field(default_factory=list)
    abstained: bool = False
    expect_abstain: bool = False
    abstain_mismatch: bool = False

    @property
    def needs_review(self) -> bool:
        """Có dấu hiệu lỗi → người chấm đọc kỹ; không có cờ thì chỉ lấy mẫu."""
        return bool(self.facts_missing or self.invalid_citations or self.no_citation or self.numbers_not_in_context
                    or self.unsupported_sentences or self.abstain_mismatch)

    @property
    def fact_recall(self) -> float | None:
        return len(self.facts_found) / self.facts_total if self.facts_total else None

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "needs_review": self.needs_review, "fact_recall": self.fact_recall}


def auto_flags(answer: str, question: str, sources: dict[str, str], facts: list[str] | None = None,
               expect_abstain: bool = False, known: list[str] | None = None) -> AutoFlags:
    """`sources`: {"S1": nội dung chunk, ...} đã đưa cho model. `known`: tên model/mã người dùng đã nêu trong hội thoại
    nhưng không nằm trong câu hỏi (vd model của lượt trước): không tính là số/mã lạ."""
    facts = facts or []
    question = f"{question} {' '.join(known or [])}"
    found, missing = facts_found(answer, facts)
    abstained = is_abstention(answer)
    body = strip_markup(answer)
    flags = AutoFlags(
        facts_total=len(facts), facts_found=found, facts_missing=missing,
        invalid_citations=invalid_citations(answer, list(sources)),
        no_citation=not abstained and bool(sources) and not cited_source_ids(answer),
        numbers_not_in_context=tokens_unsupported(body, list(sources.values()), ignore=question),
        unsupported_sentences=[asdict(s) for s in citation_support(answer, sources, question)],
        abstained=abstained, expect_abstain=expect_abstain,
    )
    flags.abstain_mismatch = (expect_abstain and not abstained) or (not expect_abstain and abstained and bool(facts))
    return flags
