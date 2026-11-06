"""T-13: ứng viên ghi chú áp dụng theo lexicon của profile (D-04).

Lớp chuẩn hóa chỉ đánh ứng viên; câu điều kiện không có trong lexicon được bắt ở bước
trích fact (LLM, evidence nguyên văn). Model/interface khớp theo từ vựng registry; điều
kiện không khớp registry (vd. "touch controller") giữ nguyên văn trong `condition_text`
và để người duyệt quyết định.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.doc_ingest.schemas.normalized import ApplicabilityCandidate
from app.modules.doc_ingest.schemas.profile import Profile, Vocabulary

_CONDITION_END = re.compile(r"[)\];]|\.(?:\s|$)|$")
_MAX_NGRAM = 3


@dataclass(frozen=True)
class ApplicabilityMatch:
    candidate: ApplicabilityCandidate
    unmatched: bool          # điều kiện không khớp model/interface nào của registry


def _norm(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", text).casefold()


def _model_index(vocab: Vocabulary) -> dict[str, str]:
    index = {_norm(model): model for model in vocab.product_models}
    index.update({_norm(alias): model for alias, model in vocab.aliases.items()})
    return index


def _interface_index(vocab: Vocabulary) -> dict[str, str]:
    index: dict[str, str] = {}
    for key, label in vocab.control_interface.items():
        index[_norm(key)] = key
        for part in label.split("/"):
            if part.strip():
                index[_norm(part)] = key
    return index


def _resolve(condition: str, index: dict[str, str]) -> list[str]:
    """Khớp n-gram (dài trước) của điều kiện với từ vựng; trả mã canonical theo thứ tự gặp."""
    words = re.findall(r"[\w.+]+", condition)
    found: list[str] = []
    i = 0
    while i < len(words):
        for size in range(min(_MAX_NGRAM, len(words) - i), 0, -1):
            canonical = index.get(_norm("".join(words[i:i + size])))
            if canonical is not None:
                if canonical not in found:
                    found.append(canonical)
                i += size
                break
        else:
            i += 1
    return found


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    body = r"\s+".join(re.escape(part) for part in phrase.split())
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def detect_applicability(text: str, profile: Profile) -> list[ApplicabilityMatch]:
    entries = sorted(profile.applicability_lexicon, key=lambda e: len(e.phrase), reverse=True)
    taken: list[tuple[int, int]] = []
    hits: list[tuple[int, int, str]] = []   # (start, phrase_end, status)
    for entry in entries:
        for m in _phrase_pattern(entry.phrase).finditer(text):
            if any(m.start() < end and start < m.end() for start, end in taken):
                continue
            taken.append((m.start(), m.end()))
            hits.append((m.start(), m.end(), entry.status))
    models_index = _model_index(profile.vocabulary)
    interfaces_index = _interface_index(profile.vocabulary)
    results: list[ApplicabilityMatch] = []
    for start, phrase_end, status in sorted(hits):
        end = _CONDITION_END.search(text, phrase_end).start()
        condition = text[phrase_end:end].strip(" ,:")
        models = _resolve(condition, models_index)
        interfaces = _resolve(condition, interfaces_index)
        unmatched = not models and not interfaces
        if status == "available_only" and unmatched:
            status = "conditional"
        note = text[start:end].strip()
        results.append(ApplicabilityMatch(
            ApplicabilityCandidate(status=status, note=note, models=models, interfaces=interfaces,
                          condition_text=condition),
            unmatched,
        ))
    return results
