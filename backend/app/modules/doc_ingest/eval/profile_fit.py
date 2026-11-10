"""B1 — độ khớp profile với tài liệu (2026-11-09).

Chạy trên kết quả chuẩn hóa của mọi lần chạy. Chỉ sinh **tín hiệu cảnh báo** cho người
nạp tài liệu (chọn/tạo profile, kiểm OCR), không đổi profile và không sinh review.

Tín hiệu:
- `default_profile_with_codes`: profile không quét mã trong text nhưng tài liệu có nhiều token dạng mã.
- `unknown_code_shapes`: có dạng mã lặp nhiều mà profile không khai báo (vd. hãng khác dùng `P01-02`).
- `near_miss_high`: nhiều token đúng prefix nhưng sai số chữ số (profile có thể đặt sai mẫu).
- `ocr_majority`: hơn nửa số trang phải OCR (V-01 không đo được trên trang OCR).
- `picture_swallows_text`: picture chiếm ≥ 50% trang mà bên trong có ≥ 2 câu văn (≥ 8 từ): nội dung thân
  có thể bị xếp thành `figure_text` và mất khỏi chunk (F10T, I-28). Nhãn sơ đồ ngắn không tính.
- `ocr_lang_mismatch`: chữ tiếng Việt xuất hiện trên trang OCR nhưng OCR không chạy ngôn ngữ `vi`
  (mất dấu — F10T, I-29).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from app.modules.doc_ingest.schemas.run import ProfileFit, ShapeCount, TokenCount

if TYPE_CHECKING:
    from app.modules.doc_ingest.pipeline import RunResult

_BODY_TYPES = frozenset({"text", "list_item", "heading", "label_heading", "caption", "warning"})
_CODE_TOKEN = re.compile(r"(?<![\w#])(?:#|[A-Z]{1,3})[.\-]?\d{2,5}(?:[.\-]\d{1,3})?(?![\w])")
_VI_CHARS = re.compile(r"[ăâđêôơưĂÂĐÊÔƠƯẠ-ỹ]")
_BIG_PICTURE = 0.5          # tỷ lệ diện tích trang
_SENTENCE_WORDS = 8         # chữ trong hình dài ≥ 8 từ là câu văn (nhãn sơ đồ thường 1–3 từ)
_SENTENCES_MIN = 2
_DEFAULT_CODES_MIN = 20
_SHAPE_MIN = 10
_NEAR_MISS_RATIO = 0.2
_VI_MIN = 20


def code_shape(token: str) -> str:
    """Dạng mã: chuỗi chữ số → `9`, giữ chữ cái và ký hiệu (`#4140` → `#9`, `P01-02` → `P9-9`)."""
    return re.sub(r"\d+", "9", token)


def _texts(result: RunResult) -> list[str]:
    body = [e.text for e in result.normalized or []
            if e.content_layer == "body" and e.normalized_type in _BODY_TYPES and e.text]
    cells = [c.text for t in result.tables.tables for r in t.rows for c in r.cells if c.text]
    return body + cells


def _known(token: str, result: RunResult) -> bool:
    profile = result.profile
    if any(re.search(p, token) for p in profile.code_patterns):
        return True
    models = {m.casefold() for m in profile.vocabulary.product_models} | {a.casefold() for a in profile.vocabulary.aliases}
    return token.casefold() in models


def profile_fit(result: RunResult) -> ProfileFit:
    profile = result.profile
    elements = result.normalized or []
    s0_pages = result.s0.pages if result.s0 is not None else []
    pages_ocr = sum(1 for p in s0_pages if p.ocr)
    langs = sorted({str(lang) for p in s0_pages if p.ocr
                    for lang in (p.docling_config.get("lang") or [])})  # type: ignore[union-attr]

    refs = [r for e in elements for r in e.param_refs]
    param_tokens = Counter(r.prefix for r in refs)
    near = result.refs.near_miss if result.refs is not None else Counter()
    ref_labels = {r.label for r in refs}

    shapes: dict[str, Counter[str]] = defaultdict(Counter)
    texts = _texts(result)
    for text in texts:
        for m in _CODE_TOKEN.finditer(text):
            token = m.group(0)
            if token in ref_labels or token in near or _known(token, result):
                continue
            if any(token.startswith(p) and token[len(p):].isdigit() for p in profile.param_text_patterns):
                continue   # đã đếm ở param_tokens (token nằm trong danh sách/dải)
            shapes[code_shape(token)][token] += 1
    unknown = sorted(((shape, sum(c.values()), [t for t, _ in c.most_common(3)]) for shape, c in shapes.items()),
                     key=lambda x: (-x[1], x[0]))[:15]

    body_chars = sum(len(e.text or "") for e in elements
                     if e.content_layer == "body" and e.normalized_type in _BODY_TYPES)
    figure_chars = sum(len(e.text or "") for e in elements if e.normalized_type == "figure_text")
    sentences = Counter(e.parent_element_id for e in elements
                        if e.normalized_type == "figure_text" and len((e.text or "").split()) >= _SENTENCE_WORDS)
    big_pages: set[int] = set()
    page_area = {i.page: (i.page_width or 0) * (i.page_height or 0) for i in result.items}
    for e in elements:
        if e.normalized_type not in ("picture", "screenshot") or e.bbox is None:
            continue
        area = (e.bbox.x1 - e.bbox.x0) * (e.bbox.y1 - e.bbox.y0)
        full = page_area.get(e.pdf_page_index) or 0
        if full and area / full >= _BIG_PICTURE and sentences[e.element_id] >= _SENTENCES_MIN:
            big_pages.add(e.pdf_page_index)
    ocr_set = {p.page for p in s0_pages if p.ocr}
    vi_chars = sum(len(_VI_CHARS.findall(e.text or "")) for e in elements
                   if e.pdf_page_index in ocr_set and e.content_layer == "body")

    signals = []
    unknown_total = sum(n for _, n, _ in unknown)
    if not profile.param_text_patterns and unknown_total >= _DEFAULT_CODES_MIN:
        signals.append("default_profile_with_codes")
    if any(n >= _SHAPE_MIN for _, n, _ in unknown):
        signals.append("unknown_code_shapes")
    near_total = sum(near.values())
    if near_total >= 5 and near_total > _NEAR_MISS_RATIO * (near_total + sum(param_tokens.values())):
        signals.append("near_miss_high")
    if s0_pages and pages_ocr / len(s0_pages) > 0.5:
        signals.append("ocr_majority")
    if big_pages:
        signals.append("picture_swallows_text")
    if pages_ocr and vi_chars >= _VI_MIN and "vi" not in langs:
        signals.append("ocr_lang_mismatch")

    return ProfileFit(
        pages_total=len(result.pages), pages_ocr=pages_ocr, ocr_langs=langs,
        param_tokens=dict(sorted(param_tokens.items())),
        near_miss=[TokenCount(token=t, count=n) for t, n in near.most_common(20)],
        unknown_shapes=[ShapeCount(shape=s, count=n, examples=ex) for s, n, ex in unknown],
        body_chars=body_chars, figure_text_chars=figure_chars,
        page_pictures_with_text=sorted(big_pages), vietnamese_chars=vi_chars, signals=signals,
    )
