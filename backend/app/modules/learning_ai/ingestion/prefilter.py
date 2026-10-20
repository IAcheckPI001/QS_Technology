"""Lọc hội thoại chắc chắn vô giá trị trước khi tốn token/GPU. Thận trọng: nghi ngờ thì giữ.

Đánh giá từng message theo token: message chỉ "trivial" khi MỌI token thuộc tập chào hỏi /
cảm ơn / xác nhận / đại từ. Có bất kỳ token khác, chữ số hay mã registry → giữ.
Ví dụ "xin chào, tôi cần giới thiệu về F86" được giữ; "dạ ok cảm ơn anh" là trivial.
Câu chào không bị cắt khỏi message — Segmenter tự xử lý.
"""
from __future__ import annotations

import re
import unicodedata
from enum import Enum

from ..extraction.validators import Role
from ..schemas.registry import RegistrySnapshot
from .source_document import SourceDocument

MIN_SUBSTANTIVE_CHARS = 40

GREETING_TOKENS = frozenset({
    # chào hỏi
    "xin", "chào", "chao", "alo", "hello", "hi", "helo", "hey",
    "buổi", "sáng", "chiều", "tối",
    # cảm ơn / chúc / tạm biệt
    "cảm", "cám", "ơn", "biết", "thanks", "thank", "you", "tks", "thks",
    "chúc", "một", "ngày", "tốt", "lành", "vui", "vẻ", "hẹn", "gặp", "lại", "tạm", "biệt",
    "nhiều", "lắm", "rất",
    # xác nhận / tiểu từ
    "dạ", "vâng", "ạ", "ok", "oke", "okay", "okie", "ừ", "ừm", "uh", "à", "ờ",
    "nha", "nhé", "nhá", "nhe", "rồi", "được", "luôn",
    # đại từ / xưng hô
    "tôi", "em", "anh", "chị", "bạn", "mình", "shop", "ad", "admin", "quý", "khách",
})

_TOKEN = re.compile(r"\w+")


class SkipReason(str, Enum):
    NO_CUSTOMER_MESSAGE = "no_customer_message"
    NO_STAFF_MESSAGE = "no_staff_message"
    GREETING_ONLY = "greeting_only"
    TOO_SHORT = "too_short"


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(unicodedata.normalize("NFC", text).lower())


def _registry_codes(reg: RegistrySnapshot | None) -> frozenset[str]:
    if reg is None:
        return frozenset()
    return frozenset(code.lower() for codes in reg.codes.values() for code in codes)


def is_trivial(text: str, codes: frozenset[str] = frozenset()) -> bool:
    for token in _tokens(text):
        if token in codes or any(ch.isdigit() for ch in token) or token not in GREETING_TOKENS:
            return False
    return True


def prefilter(document: SourceDocument, reg: RegistrySnapshot | None = None) -> SkipReason | None:
    """Trả về lý do bỏ qua cả hội thoại, hoặc None nếu cần xử lý tiếp."""
    roles = {u.role for u in document.units}
    if Role.CUSTOMER not in roles:
        return SkipReason.NO_CUSTOMER_MESSAGE
    if Role.STAFF not in roles:
        return SkipReason.NO_STAFF_MESSAGE

    codes = _registry_codes(reg)
    substantive = [u.text for u in document.units if not is_trivial(u.text, codes)]
    if not substantive:
        return SkipReason.GREETING_ONLY
    if sum(len(t) for t in substantive) < MIN_SUBSTANTIVE_CHARS:
        return SkipReason.TOO_SHORT
    return None
