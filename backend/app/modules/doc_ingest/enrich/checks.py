"""Kiểm tự động đầu ra làm giàu (Bước 3). Không gọi LLM, không phụ thuộc SDK."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.modules.doc_ingest.schemas.chunk import DraftChunk, EnrichmentOutput

SUMMARY_MAX = 220
FAQ_MIN, FAQ_MAX, FAQ_CHARS = 2, 3, 90
KEYWORDS_MAX, KEYWORD_CHARS = 6, 40

# Mã kỹ thuật: `#12010`, `X41`, `CN3`, `M1942`, `PUL1+`, `G54`… (chữ in hoa 1–4 ký tự + số, hoặc # + số).
_CODE = re.compile(r"(?<![\w#])(#\d{2,}|[A-Z]{1,4}\d+[A-Z0-9]*[+-]?)(?![\w])")


def chunk_context(chunk: DraftChunk) -> str:
    """Những gì LLM được thấy về chunk: `content` + model + section path (mã trong đây không tính là bịa)."""
    return "\n".join([chunk.content, " ".join(chunk.product_models), " › ".join(chunk.section_path)])


def missing_codes(text: str, context: str) -> list[str]:
    """Mã kỹ thuật xuất hiện trong `text` (tóm tắt/câu hỏi) mà không có trong `context` (LLM bịa hoặc sửa mã)."""
    return sorted({code for code in _CODE.findall(text) if code not in context})


_PREAMBLE = re.compile(r"(?i)^\s*(đoạn|tài liệu|phần|mục)\s+này\b")
# Câu hỏi về tài liệu/hình thay vì về nội dung (thí điểm v1/v2: "Hình ảnh… tìm ở đâu?", "Có hình vẽ nào…?").
# "Sơ đồ đấu dây … gồm gì?" vẫn hợp lệ: chỉ bắt "sơ đồ nào".
_META_FAQ = re.compile(r"(?i)\b(hình ảnh|hình vẽ|tài liệu|sơ đồ nào|mục nào|trang nào|phần nào|chương nào|"
                       r"phần này|mục này)\b")


def is_meta_question(question: str) -> bool:
    return bool(_META_FAQ.search(question))


def clean_output(out: EnrichmentOutput, models: Sequence[str] = ()) -> EnrichmentOutput:
    """Dọn deterministic trước khi kiểm: bỏ từ khóa tiếng Việt chứa mã kỹ thuật (mã đã có trong từ khóa deterministic;
    tên model `models` không tính là mã), bỏ trùng, cắt khoảng trắng; bỏ câu hỏi về tài liệu/hình khi vẫn còn
    ≥ `FAQ_MIN` câu (v3)."""
    allowed = set(models)
    keywords, seen = [], set()
    for k in (" ".join(k.split()) for k in out.keywords_vi):
        codes = [c for c in _CODE.findall(k) if c not in allowed]
        if k and not codes and k.casefold() not in seen:
            seen.add(k.casefold())
            keywords.append(k)
    faq = [" ".join(q.split()) for q in out.faq_vi]
    content_faq = [q for q in faq if not is_meta_question(q)]
    if len(content_faq) >= FAQ_MIN:
        faq = content_faq
    return out.model_copy(update={"summary_vi": " ".join(out.summary_vi.split()), "faq_vi": faq,
                                  "keywords_vi": keywords})


def missing_kept_terms(out: EnrichmentOutput, content: str, keep_terms: list[str]) -> list[str]:
    """Thuật ngữ bảng thuật ngữ ghi "giữ tiếng Anh" có trong `content` nhưng không xuất hiện nguyên văn trong tóm tắt,
    câu hỏi hay từ khóa VI (thí điểm v2: "backlash" thành "bù trục")."""
    text = " ".join([out.summary_vi, *out.faq_vi, *out.keywords_vi]).casefold()
    return [t for t in keep_terms if t.casefold() in content.casefold() and t.casefold() not in text]


def check_output(out: EnrichmentOutput, context: str, keep_terms: list[str] | None = None) -> list[str]:
    """Lỗi của một kết quả làm giàu; rỗng = hợp lệ. `enrich_code_mismatch` không chặn ghi (để người duyệt xem)."""
    problems: list[str] = []
    if not out.summary_vi.strip():
        problems.append("summary_empty")
    elif len(out.summary_vi) > SUMMARY_MAX:
        problems.append("summary_too_long")
    if _PREAMBLE.match(out.summary_vi):
        problems.append("summary_preamble")
    if not FAQ_MIN <= len(out.faq_vi) <= FAQ_MAX:
        problems.append("faq_count")
    if any(len(q) > FAQ_CHARS or not q.strip().endswith("?") for q in out.faq_vi):
        problems.append("faq_format")
    if len(out.keywords_vi) > KEYWORDS_MAX or any(not k.strip() or len(k) > KEYWORD_CHARS for k in out.keywords_vi):
        problems.append("keywords_format")
    if missing_codes(" ".join([out.summary_vi, *out.faq_vi]), context):
        problems.append("enrich_code_mismatch")
    if any(is_meta_question(q) for q in out.faq_vi):
        problems.append("faq_meta")
    if keep_terms and missing_kept_terms(out, context, keep_terms):
        problems.append("glossary_term_missing")
    return problems


BLOCKING = frozenset({"summary_empty", "faq_count"})   # lỗi không ghi được (thử lại); lỗi khác ghi kèm `checks`
