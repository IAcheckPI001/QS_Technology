"""T-17 xác nhận furniture (kèm T-18 nhãn sát hình) và T-06 số trang in (contract §5). Luật
chung, không theo tài liệu.

T-17 chạy trước mọi bước dùng `is_furniture` (phân loại nhãn, bảng, V-01). Nhãn
`page_header`/`page_footer` của Docling chỉ là gợi ý: furniture thật lặp lại trên nhiều
trang ở dải trên/dưới; heading đánh số xuất hiện một lần ở đầu trang thì trả về body.
Không xóa gì: phần tử furniture vẫn có trong `elements.jsonl` kèm lý do.
"""

from __future__ import annotations

import dataclasses
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.normalize.figures import label_target, text_margin
from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.normalize.sections import parse_heading
from app.modules.doc_ingest.schemas.normalized import PrintedPage
from app.modules.doc_ingest.schemas.profile import Profile
from app.modules.doc_ingest.schemas.run import DocumentProfile, FurnitureKey

# Nhãn được đếm lặp ở dải trên/dưới. Không gồm section_header/title: heading lặp ở đầu
# trang dễ là nội dung thật ("Notes:"), không tự đẩy thành furniture.
_REPEAT_LABELS = frozenset({"page_header", "page_footer", "text"})
_LETTER_DIGIT = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")
_PUNCT = " .,:;|/\\-–—_()[]"


def _spaced(text: str) -> str:
    """Chữ thường, tách chữ cái/chữ số dính nhau (`PAGE3` → `page 3`), gộp khoảng trắng."""
    return " ".join(_LETTER_DIGIT.sub(" ", text.casefold()).split())


def furniture_key(text: str) -> str:
    return re.sub(r"\d+", "#", _spaced(text))


def band_of(item: RawItem, profile: Profile) -> str | None:
    if item.bbox is None or item.page_height <= 0:
        return None
    band = profile.thresholds.furniture_band * item.page_height
    if item.bbox.y1 <= band:
        return "top"
    if item.bbox.y0 >= item.page_height - band:
        return "bottom"
    return None


@dataclass
class FurnitureRun:
    items: list[RawItem]
    flags: dict[str, list[str]] = field(default_factory=dict)
    demoted: set[str] = field(default_factory=set)
    keys: list[FurnitureKey] = field(default_factory=list)


def _composed(key: str, repeated: Sequence[str]) -> bool:
    rest, hit = key, False
    for other in sorted(repeated, key=len, reverse=True):
        if other in rest:
            rest, hit = rest.replace(other, " "), True
    return hit and not rest.strip(_PUNCT)


def decide_furniture(items: Sequence[RawItem], profile: Profile, rec: Recorder,
                     frames: frozenset[str] = frozenset()) -> FurnitureRun:
    """`frames`: picture là khung chữ (T-20) — không phải hình nên T-18 không gắn nhãn vào đó."""
    min_pages = profile.thresholds.furniture_min_pages
    patterns = [re.compile(p) for p in profile.furniture_patterns]
    bands = {i.element_id: band_of(i, profile) for i in items}
    pages: dict[tuple[str, str], set[int]] = defaultdict(set)
    examples: dict[tuple[str, str], str] = {}
    for item in items:
        band = bands[item.element_id]
        if item.parent_id is None and band and item.label in _REPEAT_LABELS and item.text.strip():
            slot = (band, furniture_key(item.text))
            pages[slot].add(item.page)
            examples.setdefault(slot, " ".join(item.text.split()))
    repeated = {slot for slot, seen in pages.items() if len(seen) >= min_pages}
    pictures = [i for i in items if i.label == "picture" and i.parent_id is None and i.element_id not in frames]
    margin = text_margin(items)
    run = FurnitureRun(items=[])
    run.keys = [FurnitureKey(band=b, key=k, pages=sorted(pages[(b, k)]), example=examples[(b, k)])
                for b, k in sorted(repeated)]
    for key in run.keys:
        rec.add_log("T-17", f"{key.band}:{key.key}", f"repeated on {len(key.pages)} pages in {key.band} band",
                    after={"pages": key.pages, "example": key.example})

    for item in items:
        band, text = bands[item.element_id], " ".join(item.text.split())
        layer, flag = item.content_layer, None
        if item.parent_label == "picture" and item.label != "caption":
            layer, flag = "body", "figure_text"
        elif item.parent_id is None and band and item.label in _REPEAT_LABELS and text:
            slot = (band, furniture_key(text))
            if slot in repeated:
                layer, flag = "furniture", "furniture_repeated"
            elif _composed(slot[1], [k for b, k in repeated if b == band]):
                layer, flag = "furniture", "furniture_composed"
            elif any(p.fullmatch(text) for p in patterns):
                layer, flag = "furniture", "furniture_pattern"
        if flag is None and (target := label_target(item, pictures, profile, margin)) is not None:
            # T-18: furniture thật (lặp/pattern) đã thắng ở trên; còn lại nhãn sát hình → chữ của hình.
            layer, flag = "body", "figure_text_attached"
            rec.add_log("T-18", item.element_id, f"short label next to {target.element_id}; figure text",
                        target=target.element_id, before={"parent": None, "content_layer": item.content_layer},
                        after={"parent": target.element_id, "content_layer": "body"})
            item = dataclasses.replace(item, parent_id=target.element_id, parent_label="picture",
                                       content_layer="body")
        if flag is None and item.is_furniture and item.parent_id is None:
            heading = parse_heading(text, profile)
            if heading is not None and heading.strong:
                layer, flag = "body", "furniture_demoted"
                run.demoted.add(item.element_id)
                rec.add_review(item.element_id, "furniture_reclassified",
                               f"{item.label} {text!r} appears once and is a numbered heading; returned to body",
                               target=item.element_id, suggested_action="confirm this is a section heading")
            else:
                flag = "furniture_unconfirmed"
                rec.add_review(item.element_id, "furniture_unconfirmed",
                               f"{item.label} {text!r} does not repeat across pages; kept as furniture (Docling)",
                               target=item.element_id, suggested_action="confirm it can be dropped from content")
        if flag is not None:
            run.flags[item.element_id] = [flag]
        if layer != item.content_layer:
            rec.add_log("T-17", item.element_id, flag or "", before={"content_layer": item.content_layer},
                        after={"content_layer": layer})
            if flag in ("furniture_repeated", "furniture_composed", "furniture_pattern"):
                run.flags[item.element_id].append("furniture_promoted")
            item = dataclasses.replace(item, content_layer=layer)
        run.items.append(item)
    return run


def _number_slots(item: RawItem, band: str) -> list[tuple[tuple[str, str, str], int]]:
    """(dải, token trước, token sau) quanh mỗi số nguyên; vị trí x không dùng vì OCR có thể
    gộp hai dòng footer (`QS TECHNOLOGY CO.,LTD PAGE 4`)."""
    tokens = _spaced(item.text).split()
    shape = ["#" if t.isdigit() else t for t in tokens]
    return [((band, shape[i - 1] if i else "", shape[i + 1] if i + 1 < len(shape) else ""), int(t))
            for i, t in enumerate(tokens) if t.isdigit()]


def printed_pages(items: Sequence[RawItem], pages: Sequence[int], doc_id: str, profile: Profile,
                  rec: Recorder, s0: DocumentProfile | None = None) -> dict[int, PrintedPage]:
    """(1) /PageLabels từ S0; (2) chuỗi số trong furniture: cùng một mẫu (dải + chữ quanh số),
    giá trị − trang PDF bằng nhau trên ≥ `furniture_min_pages` trang. Gom theo offset thay vì
    đòi trang liền nhau, để một số in sai giữa chừng không làm mất cả đoạn; trang có số không
    khớp offset được chấp nhận → `printed_page_conflict`. Không nội suy trang thiếu số."""
    min_pages = profile.thresholds.furniture_min_pages
    found: dict[tuple[str, str, str], dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    for item in items:
        band = band_of(item, profile)
        if item.is_furniture and item.parent_id is None and band:
            for slot, value in _number_slots(item, band):
                found[slot][item.page].add(value)
    accepted: dict[int, set[int]] = defaultdict(set)
    printed_on: dict[int, set[int]] = defaultdict(set)   # trang -> số in ra theo mẫu có chuỗi
    for per_page in found.values():
        entries = [(page, next(iter(v))) for page, v in sorted(per_page.items()) if len(v) == 1]
        by_offset: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for page, value in entries:
            by_offset[value - page].append((page, value))
        good = [group for group in by_offset.values() if len(group) >= min_pages]
        if not good:
            continue
        for page, value in entries:
            printed_on[page].add(value)
        for group in good:
            for page, value in group:
                accepted[page].add(value)
    labels = {p.page: p.page_label for p in s0.pages} if s0 is not None else {}
    out: dict[int, PrintedPage] = {}
    for page in pages:
        if labels.get(page):
            out[page] = PrintedPage(value=labels[page], source="page_labels")
            continue
        values = accepted.get(page, set())
        if len(values) == 1 and printed_on[page] == values:
            out[page] = PrintedPage(value=str(next(iter(values))), source="furniture_sequence")
            continue
        out[page] = PrintedPage()
        if printed_on.get(page):
            target = f"{doc_id}:p{page:03d}"
            rec.add_review(target, "printed_page_conflict",
                           f"printed numbers {sorted(printed_on[page])} do not fit the page-number sequence",
                           target=target, suggested_action="check the printed page number on this page")
    return out
