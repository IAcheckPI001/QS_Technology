"""Deterministic detection of a short reply to a pending clarification.

Only unambiguous short replies are matched here. Anything else (questions,
long sentences, refusals) returns None and is left to AnalysisStage, which
receives the pending clarification and reports `pending_answer`.
"""

import re

from app.modules.chatbot.extraction.validate_registry import _ALIAS, _AMBIG, _norm
from app.modules.chatbot.schemas.system import PendingClarification

MAX_CONFIRM_WORDS = 4

_PUNCT = re.compile(r"[.,!;:…\"'()]+")
_MODEL_LIKE = re.compile(r"^[a-z]+[\s\-_]?\d+[a-z]*$")
_CONFIRM_TOKENS = frozenset({
    "đúng", "rồi", "vâng", "dạ", "phải", "ok", "oke", "okay", "ừ", "ừm",
    "chính", "xác", "vậy", "yes", "có",
})
_FILLERS = frozenset({
    "là", "bộ", "model", "dòng", "máy", "điều", "khiển", "ạ", "nhé", "nha",
    "nhe", "em", "anh", "chị", "mình", "tôi", "loại", "con", "mã",
})
_ORDINALS = {
    "1": 0, "số 1": 0, "một": 0, "thứ nhất": 0, "cái đầu": 0, "đầu tiên": 0,
    "cái thứ nhất": 0,
    "2": 1, "số 2": 1, "hai": 1, "thứ hai": 1, "cái thứ hai": 1, "cái sau": 1,
    "3": 2, "số 3": 2, "ba": 2, "thứ ba": 2, "cái thứ ba": 2,
}


def match_confirmation(reply: str, pending: PendingClarification) -> str | None:
    """Return the confirmed model (canonical, or the typed mention) or None."""
    if "?" in reply:
        return None
    text = " ".join(_PUNCT.sub(" ", reply.lower()).split())
    if not text:
        return None

    candidates = pending.candidates
    if text in _ORDINALS:
        return _candidate_at(candidates, _ORDINALS[text])

    words = [word for word in text.split() if word not in _FILLERS]
    if words and all(word in _CONFIRM_TOKENS for word in words):
        # Pending không chặn (câu hỏi model ở cuối câu trả lời chung): "ok"
        # thường chỉ là đáp lễ, không phải chọn model.
        if not pending.blocking:
            return None
        return candidates[0] if len(candidates) == 1 else None

    rest = [word for word in words if word not in _CONFIRM_TOKENS]
    if not rest or len(rest) > MAX_CONFIRM_WORDS:
        return None
    phrase = " ".join(rest)
    if phrase in _ORDINALS:
        return _candidate_at(candidates, _ORDINALS[phrase])

    key = _norm(phrase)
    if key in _ALIAS:
        return _ALIAS[key]
    if key in _AMBIG or _MODEL_LIKE.match(phrase):
        return phrase.upper()
    return None


def _candidate_at(candidates: list[str], index: int) -> str | None:
    return candidates[index] if index < len(candidates) else None
