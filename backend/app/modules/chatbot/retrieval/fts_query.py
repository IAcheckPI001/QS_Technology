"""Làm sạch câu hỏi trước khi đưa vào nhánh FTS (R-4, website-qa LOG "Eval 14 câu").

FTS của `match_doc_chunks_*` đổi câu thành OR các từ (`simple`, không bỏ từ phổ biến). Từ chức năng và tên model
có trong gần như mọi chunk ("cách", "trên", "bộ điều khiển", "F54"…) nên chunk tổng quan khớp nhiều từ nhất và chiếm
hạng FTS, kéo nó vượt chunk đúng khi trộn RRF. Model đã là bộ lọc (`p_models`) nên bỏ khỏi câu FTS không mất thông
tin. Chỉ dùng cho nhánh FTS; embedding vẫn tính trên câu gốc.

Danh sách là từ chức năng tiếng Việt/Anh chung và cụm chỉ "bộ điều khiển" (mọi tài liệu của QS là bộ điều khiển);
không chứa thuật ngữ riêng của một tài liệu.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Cụm dài trước cụm ngắn. So khớp theo ranh giới từ, không phân biệt hoa thường. Có cả dạng không dấu.
STOP_PHRASES: tuple[str, ...] = (
    "như thế nào", "làm thế nào", "làm sao", "thế nào", "là gì", "là bao nhiêu", "bao nhiêu", "ở đâu",
    "bộ điều khiển", "hướng dẫn", "cho tôi", "giúp tôi", "dùng để", "được không",
    "nhu the nao", "lam the nao", "lam sao", "the nao", "la gi", "bao nhieu", "o dau",
    "bo dieu khien", "huong dan", "cho toi", "giup toi", "dung de",
    "how to", "what is", "controller",
)
# KHÔNG đưa vào: "vào", "ra" (đầu vào/đầu ra = input/output), "không" (triệu chứng lỗi: "không về home"),
# "về" ở dạng không dấu ("ve" trùng nhiều từ khác). Từ có nghĩa kỹ thuật thì giữ.
STOP_WORDS: frozenset[str] = frozenset({
    # tiếng Việt: từ chức năng, đại từ, từ hỏi
    "cách", "các", "những", "của", "trên", "trong", "cho", "với", "và", "hoặc", "là", "thì", "mà", "để", "có",
    "được", "bị", "gì", "nào", "sao", "đâu", "khi", "nếu", "này", "đó", "tôi", "bạn",
    "mình", "em", "anh", "chị", "ạ", "nhé", "vậy", "thế", "về", "theo", "từ", "đến", "một",
    # dạng không dấu thường gặp (người dùng gõ không dấu)
    "cach", "cac", "nhung", "cua", "tren", "trong", "voi", "hoac", "thi", "duoc", "khi", "neu", "nay", "toi", "ban",
    # tiếng Anh
    "the", "a", "an", "of", "on", "in", "for", "to", "and", "or", "is", "are", "how", "what", "which", "with",
})
_SPACE = re.compile(r"\s+")


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)


_PHRASES = [_phrase_pattern(p) for p in STOP_PHRASES]


def clean_fts_query(text: str, models: Iterable[str] = ()) -> str:
    """Bỏ tên model (đã lọc bằng `p_models`), cụm và từ phổ biến. Câu sạch rỗng → trả câu gốc."""
    out = text
    for model in sorted({m for m in models if m}, key=len, reverse=True):
        out = _phrase_pattern(model).sub(" ", out)
    for pattern in _PHRASES:
        out = pattern.sub(" ", out)
    words = [w for w in re.split(r"[\s,.;:!?()\"']+", out) if w and w.lower() not in STOP_WORDS]
    cleaned = _SPACE.sub(" ", " ".join(words)).strip()
    return cleaned or text
