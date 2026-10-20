"""Tầng A (và D): phát hiện PII có cấu trúc và giá bằng regex. Hàm thuần, deterministic.

Nguyên tắc chống nhầm với số liệu kỹ thuật:
  - Số định danh (CCCD/CMND/MST/STK) chỉ bắt khi có từ khoá đứng trước, để không xoá giá trị
    tham số, số xung encoder, mã lô.
  - Giá: đơn vị tiền rõ nghĩa (đ, đồng, vnđ, usd, $) luôn bắt; đơn vị số lượng
    (ngàn, nghìn, triệu, tỷ, củ) bắt trừ khi theo sau là danh từ kỹ thuật ("10 nghìn xung");
    đơn vị mơ hồ (k, tr) cần từ khoá giá hoặc không có danh từ kỹ thuật theo sau
    ("5k ohm" không bắt); tiếng lóng (lít, xị) chỉ bắt khi có từ khoá giá.
  - Tên người, công ty, địa chỉ KHÔNG dùng regex — để tầng Ollama.
"""
from __future__ import annotations

import re

from .schemas import FindingCategory, FindingType, PiiSpan

_I = re.IGNORECASE
PRICE_KEYWORD_WINDOW = 30

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w-])(?:\+84|0)[\s.]?[35789](?:[\s.]?\d){8}(?![\w-])")
_IPV4 = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")
_KEYWORD_IDS: tuple[tuple[re.Pattern[str], FindingType], ...] = (
    (re.compile(r"(?:cccd|cmnd|cmt|căn\s*cước)[^\d\n]{0,20}(\d(?:[\s.]?\d){8,11})(?!\d)", _I),
     FindingType.NATIONAL_ID),
    (re.compile(r"(?:mst|mã\s*số\s*thuế)[^\d\n]{0,20}(\d{10}(?:-\d{3})?)(?!\d)", _I), FindingType.TAX_CODE),
    (re.compile(r"(?:stk|số\s*tk|tài\s*khoản)[^\d\n]{0,20}(\d(?:[\s.]?\d){7,18})(?!\d)", _I),
     FindingType.BANK_ACCOUNT),
)

_NUM_WORD = r"(?:một|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|trăm|linh|lẻ)"
_AMOUNT = re.compile(
    r"(?<![\w.,])(?P<num>\d+(?:[.,]\d+)*|(?:" + _NUM_WORD + r"\s+)*" + _NUM_WORD + r")"
    r"\s*(?P<unit>vnđ|vnd|đồng|đ|ngàn|nghìn|ngìn|triệu|tỷ|tỉ|củ|usd|tr|k|lít|xị)"
    r"(?P<tail>(?:\s*đồng)?(?:\s*\d+)?(?:\s*rưỡi)?)(?!\w)",
    _I,
)
_DOLLAR = re.compile(r"\$\s*\d+(?:[.,]\d+)*")
_PERCENT = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?\s*%")

_STRONG_UNITS = frozenset({"vnđ", "vnd", "đồng", "đ", "usd"})
_COUNT_UNITS = frozenset({"ngàn", "nghìn", "ngìn", "triệu", "tỷ", "tỉ", "củ"})
_AMBIGUOUS_UNITS = frozenset({"tr", "k"})
_SLANG_UNITS = frozenset({"lít", "xị"})

_PRICE_KEYWORD = re.compile(
    r"giá|phí|tiền|thanh\s*toán|chuyển\s*khoản|chiết\s*khấu|giảm|cọc|khuyến\s*mãi|ưu\s*đãi|tổng\s*cộng", _I)
_DISCOUNT_KEYWORD = re.compile(r"chiết\s*khấu|giảm|khuyến\s*mãi|ưu\s*đãi|discount", _I)
_TECH_NOUN_AFTER = re.compile(
    r"\s*(?:xung|vòng|ppr|rpm|hz|ohm|Ω|kw|w|v|a|ma|giờ|h|lần|bước|mét|m|mm|cm|byte|bit|bps|baud|"
    r"ms|giây|phút|độ|sản\s*phẩm|cái|chiếc|bộ|con)(?!\w)", _I)


def _has_keyword_before(text: str, start: int, pattern: re.Pattern[str]) -> bool:
    return pattern.search(text, max(0, start - PRICE_KEYWORD_WINDOW), start) is not None


def _is_price(text: str, m: re.Match[str]) -> bool:
    unit = m.group("unit").lower()
    if unit in _STRONG_UNITS:
        return True
    keyword = _has_keyword_before(text, m.start(), _PRICE_KEYWORD)
    if unit in _SLANG_UNITS:
        return keyword
    if keyword:
        return True
    tech_after = _TECH_NOUN_AFTER.match(text, m.end()) is not None
    return not tech_after if unit in _COUNT_UNITS | _AMBIGUOUS_UNITS else False


def _price_spans(text: str) -> list[PiiSpan]:
    spans = [PiiSpan(m.start(), m.end(), FindingCategory.PRICING, FindingType.PRICE_AMOUNT)
             for m in _AMOUNT.finditer(text) if _is_price(text, m)]
    spans += [PiiSpan(m.start(), m.end(), FindingCategory.PRICING, FindingType.PRICE_AMOUNT)
              for m in _DOLLAR.finditer(text)]
    spans += [PiiSpan(m.start(), m.end(), FindingCategory.PRICING, FindingType.DISCOUNT)
              for m in _PERCENT.finditer(text) if _has_keyword_before(text, m.start(), _DISCOUNT_KEYWORD)]
    return spans


def find_regex_spans(text: str) -> list[PiiSpan]:
    """Mọi span nhạy cảm tìm được bằng regex, đã gộp chồng lấn, theo thứ tự xuất hiện."""
    pii = FindingCategory.PII
    # Từ khoá rõ nghĩa hơn định dạng: "mst 0312345678" là MST dù trông như SĐT (merge giữ span đầu tiên).
    spans = [PiiSpan(m.start(1), m.end(1), pii, kind)
             for pattern, kind in _KEYWORD_IDS for m in pattern.finditer(text)]
    spans += [PiiSpan(m.start(), m.end(), pii, FindingType.EMAIL) for m in _EMAIL.finditer(text)]
    spans += [PiiSpan(m.start(), m.end(), pii, FindingType.PHONE) for m in _PHONE.finditer(text)]
    spans += [PiiSpan(m.start(), m.end(), pii, FindingType.IP_ADDRESS) for m in _IPV4.finditer(text)]
    spans += _price_spans(text)
    return merge_spans(spans)


def merge_spans(spans: list[PiiSpan]) -> list[PiiSpan]:
    """Giữ span bắt đầu sớm nhất (dài nhất khi trùng điểm đầu); bỏ span chồng lấn sau đó."""
    out: list[PiiSpan] = []
    for s in sorted(spans, key=lambda s: (s.start, -(s.end - s.start))):
        if out and s.start < out[-1].end:
            continue
        out.append(s)
    return out
