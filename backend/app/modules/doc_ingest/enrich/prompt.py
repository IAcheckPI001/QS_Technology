"""Prompt làm giàu tiếng Việt (Bước 3).

Phiên bản ghi vào mỗi bản ghi (`EnrichmentRecord.prompt_version`) = `PROMPT_VERSION` + dấu của bảng thuật ngữ
(`profile.glossary`): đổi nội dung prompt → tăng `PROMPT_VERSION`; bổ sung/sửa thuật ngữ → dấu đổi. Cả hai trường hợp
`cli enrich` coi bản ghi cũ là chưa cập nhật và làm lại (bản ghi cũ vẫn dùng được cho tới khi có bản mới).

v1 (2026-11-13, thí điểm 20 chunk). v2 (2026-11-13, sau duyệt thí điểm): tóm tắt không mở bằng "Đoạn này…"; không
hỏi về tài liệu/hình; từ khóa tiếng Việt không lặp mã kỹ thuật hay tiếng Anh; dùng bảng thuật ngữ. v3 (2026-11-13):
ví dụ câu hỏi cho đoạn chỉ có hình; thuật ngữ "giữ tiếng Anh" bắt buộc có nguyên văn trong tóm tắt (thí điểm v2:
"backlash" → "bù trục"); kèm kiểm `faq_meta`, `glossary_term_missing` và bỏ câu hỏi về tài liệu/hình khi còn đủ câu.
v4 (2026-11-13): bỏ ví dụ câu hỏi cụ thể của v3 (LLM chép ví dụ "kích thước F54" vào chunk ảnh mặt trước/sau); cấm
"trong tài liệu", "trong phần này", "được trình bày"; từ khóa VI được giữ tên model.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from app.modules.doc_ingest.enrich.checks import FAQ_CHARS, FAQ_MAX, FAQ_MIN, KEYWORDS_MAX, SUMMARY_MAX
from app.modules.doc_ingest.schemas.chunk import DraftChunk
from app.modules.doc_ingest.schemas.profile import GlossaryTerm

PROMPT_VERSION = "v4"

_BASE = f"""Bạn viết lớp tìm kiếm tiếng Việt cho tài liệu kỹ thuật bộ điều khiển CNC của QS Technology.
Người dùng (kỹ thuật viên, khách hàng) hỏi bằng tiếng Việt; đoạn tài liệu thường bằng tiếng Anh. Đọc MỘT đoạn tài liệu
và trả JSON đúng ba khóa:

- "summary_vi": 1–2 câu (tối đa {SUMMARY_MAX} ký tự) nói thẳng đoạn hướng dẫn/mô tả gì. KHÔNG mở đầu bằng "Đoạn này",
  "Tài liệu này", "Phần này"; bắt đầu ngay bằng nội dung (vd. "Hướng dẫn đấu dây …", "Bảng tham số …").
- "faq_vi": {FAQ_MIN}–{FAQ_MAX} câu hỏi người dùng thật sẽ gõ khi gặp vấn đề, mỗi câu tối đa {FAQ_CHARS} ký tự, kết thúc
  bằng "?", trả lời được HOÀN TOÀN bằng nội dung đoạn. KHÔNG hỏi về tài liệu, mục, trang, hình ảnh hay hình vẽ (sai:
  "Mục nào nói về…", "Hình ảnh… tìm ở đâu?", "Có hình vẽ nào…?", "Có sơ đồ nào…?"); hỏi về việc cần làm, giá trị,
  cách đấu, ý nghĩa, thông số. Đoạn chỉ có hình/bản vẽ: hỏi về điều mà CHÍNH hình đó cho biết theo tiêu đề/caption,
  không hỏi điều thuộc mục khác. Không viết "trong tài liệu", "trong phần này", "được trình bày" ở tóm tắt và câu hỏi.
- "keywords_vi": tối đa {KEYWORDS_MAX} cụm từ tiếng Việt người dùng hay gõ cho chủ đề này. KHÔNG chứa mã kỹ thuật
  (#12010, M1920, X41, CN3…), KHÔNG chứa từ tiếng Anh hay tên model; mã và tên tiếng Anh đã có sẵn trong từ khóa khác.

Quy tắc bắt buộc:
1. Chỉ dùng thông tin có trong đoạn. Không thêm số, giá trị, bước, model hay mã không có trong đoạn.
2. Giữ NGUYÊN VĂN mã kỹ thuật, tên nút, tên màn hình (#12010, X41, CN3, M1942, PUL1+, G54, GO TO LINE…).
3. Viết tiếng Việt có dấu, tự nhiên, ngắn gọn.
4. Đoạn là một phần của bảng tham số: tóm tắt nói phần bảng tham số gì; câu hỏi hỏi về mã/giá trị có trong phần đó.
5. Chỉ trả JSON."""


def _glossary_lines(glossary: Sequence[GlossaryTerm]) -> list[str]:
    return [f"- {t.en} → {t.vi}" if t.vi else f"- {t.en} → giữ nguyên tiếng Anh \"{t.en}\" (không dịch)"
            for t in glossary]


def system_prompt(glossary: Sequence[GlossaryTerm] = ()) -> str:
    if not glossary:
        return _BASE
    return (_BASE + "\n\nBảng thuật ngữ (cách người dùng QS gọi; khi đoạn có thuật ngữ này, tóm tắt/câu hỏi/từ khóa dùng"
            " đúng cách gọi bên phải). Thuật ngữ ghi \"giữ nguyên tiếng Anh\": KHÔNG dịch, KHÔNG thay bằng từ khác, và"
            " BẮT BUỘC viết nguyên văn thuật ngữ đó trong tóm tắt khi đoạn có nó (vd. \"Bảng tham số backlash…\";"
            " sai: \"bù trục\"); riêng quy tắc từ khóa không chứa tiếng Anh không áp dụng cho các thuật ngữ này:\n"
            + "\n".join(_glossary_lines(glossary)))


def prompt_version(glossary: Sequence[GlossaryTerm] = ()) -> str:
    """`v2` khi không có bảng thuật ngữ; có bảng → `v2+g<8 hex>` (dấu đổi khi bảng đổi)."""
    if not glossary:
        return PROMPT_VERSION
    data = json.dumps([t.model_dump() for t in glossary], ensure_ascii=False, sort_keys=True)
    return f"{PROMPT_VERSION}+g{hashlib.sha256(data.encode('utf-8')).hexdigest()[:8]}"


# Giữ tương thích cho chỗ cần prompt không bảng thuật ngữ (ước tính, test).
SYSTEM_PROMPT = system_prompt()


def user_message(chunk: DraftChunk) -> str:
    path = " › ".join(chunk.section_path) or chunk.section_title
    return (f"Tài liệu: {chunk.doc_title} (model: {', '.join(chunk.product_models)})\n"
            f"Mục: {path}\n"
            f"Loại đoạn: {chunk.chunk_type}\n"
            f"--- ĐOẠN TÀI LIỆU ---\n{chunk.content}")
