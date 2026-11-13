"""Profile cấu hình (D-11, contract §9): tri thức miền/ngôn ngữ là dữ liệu, không phải code."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.modules.doc_ingest.schemas.base import StrictModel
from app.modules.doc_ingest.schemas.normalized import ApplicabilityStatus


class LexiconEntry(StrictModel):
    phrase: str
    status: ApplicabilityStatus


class Thresholds(StrictModel):
    continuation_tol: float = 0.15   # × độ rộng cột hẹp nhất (T-03)
    shape_majority: float = 0.6      # tỷ lệ dòng dữ liệu cùng hình dạng token (T-05 b)
    shape_min_rows: int = 3          # số dòng dữ liệu tối thiểu để dùng T-05 b
    row_gap_factor: float = 1.5      # × chiều cao dòng trung vị (T-15)
    max_range_len: int = 64          # dải mã dài hơn → range_too_long (§4)
    text_coverage_min: float = 0.9   # V-01, giá trị tạm (D-12 chưa chốt)
    text_duplicate_max: float = 0.1  # V-01, giá trị tạm (D-12 chưa chốt)
    ocr_min_chars: int = 20          # S0: ít ký tự text layer hơn → cần OCR (tạm, D-12)
    text_bad_char_max: float = 0.1   # S0: tỷ lệ ký tự lỗi cao hơn → text layer hỏng (tạm, D-12)
    furniture_band: float = 0.12     # T-17/T-06: dải trên/dưới, × chiều cao trang (tạm, D-12)
    furniture_min_pages: int = 3     # T-17 lặp / T-06 chuỗi số trang / T-10 bitmap lặp: số trang tối thiểu
    figure_label_gap: float = 12.0   # T-18: nhãn nằm trong bbox picture nở thêm (pt)
    figure_label_max_tokens: int = 4  # T-18: nhãn dài hơn là câu văn, không gắn vào hình
    frame_sentence_words: int = 5    # T-20: con của picture có ≥ số từ này là câu → picture là khung chữ
    frame_text_min_ratio: float = 0.5  # T-20: tỷ lệ tối thiểu con chữ là dòng ≥ 2 từ (sơ đồ có nhiều mảnh nhãn)
    crop_bitmap_min: float = 0.5     # T-14: bitmap phủ ≥ tỷ lệ này của bbox → mở rộng crop
    crop_vector_margin: float = 36.0  # T-14: nét vector vượt bbox quá (pt) → không mở rộng (khung trang)
    crop_padding: float = 12.0       # T-14
    screenshot_bitmap_min: float = 0.8  # T-09
    watermark_cover_min: float = 0.9  # T-10: tỷ lệ diện tích picture nằm trong bitmap lặp
    duplicate_iou_min: float = 0.9   # T-19: hai phần tử hình cùng trang IoU ≥ → cùng một ảnh
    list_indent_min: float = 18.0    # T-08: thụt sâu hơn mục trước ≥ (pt) → con, không cần glyph


class Vocabulary(StrictModel):
    """Snapshot từ vựng registry chatbot (`registry_snapshot.json`, test đồng bộ ở venv chính)."""

    product_models: list[str]
    aliases: dict[str, str] = Field(default_factory=dict)
    control_interface: dict[str, str] = Field(default_factory=dict)
    spec_attributes: dict[str, str] = Field(default_factory=dict)


ChunkTypeTarget = Literal["figure", "overview", "table"]


class ChunkTypeRule(StrictModel):
    """Loại ngữ nghĩa của chunk (contract C2 §6). `title`: regex trên tiêu đề mục + label heading + caption;
    `content`: regex trên nội dung. Có cả hai thì khớp một trong hai là đủ. Luật đầu tiên khớp thắng."""

    chunk_type: Literal["wiring", "pinout", "dimension", "alarm", "spec"]
    applies_to: list[ChunkTypeTarget] = Field(min_length=1)
    title: str | None = None
    content: str | None = None


class ScopeContentRule(StrictModel):
    """I-46: THÊM `scope` cho chunk theo nội dung (không bớt scope gốc của manifest). `title`: regex trên tiêu đề các
    cấp mục từ `Chunking.scope_title_min_level` trở xuống + label heading; `content`: regex trên nội dung đơn vị;
    `chunk_types`: loại chunk. Khai báo nhiều điều kiện thì khớp một trong số đó là đủ."""

    scope: Literal["installation", "operation", "configuration", "maintenance"]
    title: str | None = None
    content: str | None = None
    chunk_types: list[str] = Field(default_factory=list)


class Chunking(StrictModel):
    """Tham số chunk builder (BL-16, contract C2 §5, §6, §8)."""

    child_soft_max: int = 1200       # gộp đơn vị ngắn cùng loại tới ngưỡng này; nhóm parameter tách theo ngưỡng này
    parent_max: int = 2500           # CQ-03: mọi content ≤; khối dài hơn tách ở ranh giới phần tử/bước/dòng
    figure_text_max: int = 600       # khối có hình và chữ ≤ ngưỡng → chunk hình
    table_lead_max: int = 80         # R-04: dòng text kết thúc bằng ":" ngay trước bảng, ≤ ngưỡng → dòng dẫn của bảng
    embed_max_tokens: int = 800
    # Chỗ dành trong `embed_text` cho "Tóm tắt" + "Câu hỏi thường gặp" của Bước 3 khi chia phần bảng (I-38)
    embed_enrich_reserve: int = 150
    max_keywords: int = 40
    step_patterns: list[str] = Field(default_factory=list)            # đầu text của một bước
    # I-39: đầu một phần của khối dài ("Case 1:", "Example 2:"); khối vượt giới hạn chỉ chia ở các điểm này
    block_part_patterns: list[str] = Field(default_factory=list)
    block_lead_max: int = 300        # I-39: phần dẫn chung của khối ≤ ngưỡng → lặp ở đầu mọi phần sau
    procedure_lead_max: int = 160    # I-42: câu dẫn ngắn ngay trước "Step 1" ≤ ngưỡng → thuộc thủ tục đó
    procedure_title_patterns: list[str] = Field(default_factory=list)  # label heading của thủ tục dạng list
    chunk_type_rules: list[ChunkTypeRule] = Field(default_factory=list)
    control_interface_terms: dict[str, list[str]] = Field(default_factory=dict)   # thêm vào nhãn registry
    spec_attribute_terms: dict[str, list[str]] = Field(default_factory=dict)
    figure_label_patterns: list[str] = Field(default_factory=list)    # nhãn trong hình được giữ làm từ khóa
    # I-40b: nhãn OCR crop chỉ vào từ khóa khi có trong từ vựng text layer của tài liệu (điểm OCR không tin được)
    figure_label_require_vocab: bool = True
    # 2026-11-13 (Toma): nhãn hình nguồn OCR (`ocr`, `crop_ocr`) chỉ vào từ khóa của các loại chunk này; loại khác
    # (ảnh tổng quan, ảnh màn hình…) giữ nhãn trong `figure_labels` để không tranh suất với chunk đấu dây thật
    figure_label_keyword_types: list[str] = Field(default_factory=lambda: ["wiring", "pinout", "dimension"])
    # I-46 (2026-11-13): scope theo nội dung, cộng thêm vào scope theo mục của manifest. Tiêu đề cấp < min_level
    # (tên phần lớn, vd. "PART 2: WIRING - CONNECTION - SETTING") không xét: thường gộp nhiều loại việc.
    scope_content_rules: list[ScopeContentRule] = Field(default_factory=list)
    scope_title_min_level: int = 2


class GlossaryTerm(StrictModel):
    """Bảng thuật ngữ cho làm giàu tiếng Việt (Bước 3): cách người dùng QS gọi thuật ngữ tiếng Anh của tài liệu.
    `vi` rỗng = giữ nguyên tiếng Anh (chưa xác nhận cách gọi; LLM không tự dịch)."""

    en: str
    vi: str = ""
    note: str = ""


class Profile(StrictModel):
    name: str
    # Bước 3: bổ sung dần; đổi bảng → phiên bản làm giàu đổi → `cli enrich` chạy lại chunk có bản ghi cũ
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    code_patterns: list[str] = Field(default_factory=list)
    # I-40b: nhãn OCR crop khớp toàn chuỗi một mẫu này được tin dù không có trong từ vựng tài liệu (tên chân, mã
    # tín hiệu, điện áp của miền thiết bị)
    figure_label_trusted_patterns: list[str] = Field(default_factory=list)
    param_prefixes: list[str] = Field(default_factory=list)
    # T-12 trên text: prefix -> regex số chữ số (vd. "M": "\d{4}"); prefix không khai báo → không quét text
    param_text_patterns: dict[str, str] = Field(default_factory=dict)
    applicability_lexicon: list[LexiconEntry] = Field(default_factory=list)
    caption_keywords: list[str] = Field(default_factory=list)        # mọi caption (T-11, T-18)
    table_caption_keywords: list[str] = Field(default_factory=list)  # T-11: caption bảng; còn lại là hình
    section_keywords: list[str] = Field(default_factory=list)
    furniture_patterns: list[str] = Field(default_factory=list)   # regex T-17 (d), khớp toàn chuỗi
    list_glyphs: list[str] = Field(default_factory=list)
    # T-20: tiêu đề khung (khớp toàn chuỗi) không tính là bằng chứng khung chữ, vd. "Description images"
    frame_label_patterns: list[str] = Field(default_factory=list)
    # T-20: dòng model áp dụng của khung (khớp toàn chuỗi, là tập con của `frame_label_patterns`). Nhãn khung
    # Docling không gom vào picture: tiêu đề khung + dòng model liền sau, hoặc dòng model ngay trên hình.
    frame_model_patterns: list[str] = Field(default_factory=list)
    # T-16: tiêu đề mục lục (khớp toàn chuỗi) đứng ngay trước phần tử mục lục
    toc_title_patterns: list[str] = Field(default_factory=list)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    chunking: Chunking = Field(default_factory=Chunking)
    vocabulary: Vocabulary
