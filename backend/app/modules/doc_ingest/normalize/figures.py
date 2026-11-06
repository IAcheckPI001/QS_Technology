"""Hình (contract §5): T-18 nhãn sát hình, T-09 screenshot, T-10 ứng viên watermark, T-11 gắn
caption, T-14 vùng crop. Luật hình học chung, không theo tài liệu.

Đối tượng trang (`raw/p{n}.objects.json`: bitmap kèm kích thước px, nét vector) đo từ PDF bằng
pypdfium2. Trang không có file này (run cũ, fixture chỉ có Docling JSON): T-09/T-10 không chạy,
T-14 chỉ dùng bbox Docling và nhãn của hình; không đoán.

Chữ trong hình (kể cả nhãn kích thước) chỉ là từ khóa của hình: không vào text thân chunk,
không thành fact. Nội dung có thẩm quyền là ảnh crop.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.modules.doc_ingest.geometry import BBox, overlap_ratio
from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.normalize.sections import parse_heading
from app.modules.doc_ingest.schemas.normalized import Box, CaptionLink, ImageInfo
from app.modules.doc_ingest.schemas.profile import Profile

PageObjects = dict[int, dict[str, list[dict[str, Any]]]]

# Nhãn Docling có thể là nhãn hình bị để ngoài picture (F86: `320 mm` gắn page_header / text).
_LABEL_SOURCES = frozenset({"text", "page_header", "page_footer", "section_header"})
_SENTENCE_END = (".", ":", ";", "?", "!")
_SAME_SIZE = 1.0       # T-10: sai số cỡ hiển thị (pt) để coi hai bitmap là cùng một ảnh lặp
_TIE = 1.0             # T-11: hai ứng viên chênh khoảng cách ≤ (pt) → caption_ambiguous


def _bbox(raw: Mapping[str, Any]) -> BBox:
    return BBox(raw["x0"], raw["y0"], raw["x1"], raw["y1"])


def _box(bbox: BBox) -> Box:
    return Box(x0=round(bbox.x0, 1), y0=round(bbox.y0, 1), x1=round(bbox.x1, 1), y1=round(bbox.y1, 1))


def _union(a: BBox, b: BBox) -> BBox:
    return BBox(min(a.x0, b.x0), min(a.y0, b.y0), max(a.x1, b.x1), max(a.y1, b.y1))


def _size(raw: Mapping[str, Any]) -> tuple[float, float]:
    return raw["x1"] - raw["x0"], raw["y1"] - raw["y0"]


def _same_size(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """Cùng cỡ hiển thị, cho phép xoay 90° (F86: logo 94×148 pt, trang 13–14 là 148×94)."""
    return any(abs(a[0] - w) <= _SAME_SIZE and abs(a[1] - h) <= _SAME_SIZE for w, h in (b, b[::-1]))


def _gap(a: BBox, b: BBox) -> float:
    """Khoảng cách giữa hai bbox (0 khi chạm hoặc chồng nhau)."""
    return max(0.0, max(a.x0, b.x0) - min(a.x1, b.x1), max(a.y0, b.y0) - min(a.y1, b.y1))


def _starts_with(text: str, keywords: Sequence[str]) -> bool:
    folded = text.lstrip().casefold()
    return any(folded.startswith(k.casefold()) for k in keywords)


def label_target(item: RawItem, pictures: Sequence[RawItem], profile: Profile) -> RawItem | None:
    """T-18: nhãn ngắn (kích thước, tên chân) Docling để ngoài picture nhưng nằm sát hoặc đè mép
    hình → picture gần nhất; None nếu không phải nhãn hình. Câu văn, heading đánh số, caption
    không bao giờ bị gắn."""
    text = " ".join(item.text.split())
    t = profile.thresholds
    if (item.bbox is None or item.parent_id is not None or item.label not in _LABEL_SOURCES or not text
            or len(text.split()) > t.figure_label_max_tokens or text.endswith(_SENTENCE_END)
            or _starts_with(text, profile.caption_keywords)):
        return None
    heading = parse_heading(text, profile)
    # `320 mm` khớp mẫu số một đoạn (heading yếu); chỉ heading mạnh hoặc section_header có số
    # mới được giữ là heading.
    if heading is not None and (heading.strong or item.label == "section_header"):
        return None
    b = item.bbox
    cx = (b.x0 + b.x1) / 2
    near = [(_gap(b, p.bbox), p) for p in pictures if p.page == item.page and p.bbox is not None
            and p.bbox.x0 <= cx <= p.bbox.x1]
    near = [(gap, p) for gap, p in near if gap <= t.figure_label_gap]
    return min(near, key=lambda pair: pair[0])[1] if near else None


@dataclass
class FigureRun:
    items: list[RawItem]
    kinds: dict[str, str] = field(default_factory=dict)          # element_id -> screenshot | watermark_candidate
    images: dict[str, ImageInfo] = field(default_factory=dict)
    captions: dict[str, tuple[str, CaptionLink]] = field(default_factory=dict)  # đích -> (caption, link)
    flags: dict[str, list[str]] = field(default_factory=dict)

    @property
    def screenshots(self) -> frozenset[str]:
        return frozenset(k for k, v in self.kinds.items() if v == "screenshot")


@dataclass
class _Repeated:
    px: tuple[int, int]
    size: tuple[float, float]
    boxes: dict[int, list[BBox]] = field(default_factory=dict)   # trang -> vị trí trên trang đó


def _repeated_bitmaps(objects: PageObjects, min_pages: int) -> list[_Repeated]:
    """Bitmap cùng kích thước px và cùng cỡ hiển thị (± `_SAME_SIZE`, cho phép xoay 90°) trên
    ≥ `min_pages` trang; vị trí tùy ý (logo F86 đổi chỗ theo trang). Ảnh dùng lại trong hình thật
    thường đổi cỡ (F86 275×275 px ở 354×144, 386×162 pt…) nên không thành nhóm lặp."""
    groups: list[_Repeated] = []
    for page in sorted(objects):
        for raw in objects[page].get("bitmaps", []):
            px = (raw.get("px_w", 0), raw.get("px_h", 0))
            group = next((g for g in groups if g.px == px and _same_size(g.size, _size(raw))), None)
            if group is None:
                group = _Repeated(px=px, size=_size(raw))
                groups.append(group)
            group.boxes.setdefault(page, []).append(_bbox(raw))
    return [g for g in groups if len(g.boxes) >= min_pages]


def _screenshots(items: Sequence[RawItem], objects: PageObjects, profile: Profile, run: FigureRun,
                 rec: Recorder) -> None:
    for item in items:
        if item.label != "table" or item.parent_id is not None or item.cells or item.bbox is None:
            continue
        if item.page not in objects:
            continue
        cover = overlap_ratio(item.bbox, [_bbox(b) for b in objects[item.page].get("bitmaps", [])])
        if cover >= profile.thresholds.screenshot_bitmap_min:
            run.kinds[item.element_id] = "screenshot"
            rec.add_log("T-09", item.element_id, "docling table with 0 cells covered by an embedded bitmap",
                        before={"normalized_type": "table_segment"},
                        after={"normalized_type": "screenshot", "bitmap_cover": cover})


def _watermarks(items: Sequence[RawItem], objects: PageObjects, profile: Profile, run: FigureRun,
                rec: Recorder) -> None:
    t = profile.thresholds
    repeated = _repeated_bitmaps(objects, t.furniture_min_pages)
    for group in repeated:
        rec.add_log("T-10", f"bitmap:{group.px[0]}x{group.px[1]}",
                    f"bitmap {group.size[0]:.0f}x{group.size[1]:.0f} pt repeated on {len(group.boxes)} pages",
                    after={"pages": sorted(group.boxes)})
    for item in items:
        if item.label != "picture" or item.parent_id is not None or item.bbox is None:
            continue
        reps = [box for group in repeated for box in group.boxes.get(item.page, [])]
        cover = max((overlap_ratio(item.bbox, [box]) for box in reps), default=0.0)
        if cover < t.watermark_cover_min:
            continue
        page_bitmaps = [_bbox(b) for b in objects.get(item.page, {}).get("bitmaps", [])]
        others = [b for b in page_bitmaps if b not in reps]
        real = overlap_ratio(item.bbox, others) if others else 0.0
        if item.has_caption or real >= t.crop_bitmap_min:
            reason = "has a caption" if item.has_caption else "also covered by a non-repeated image"
            rec.add_review(item.element_id, "watermark_conflict",
                           f"picture lies in a repeated bitmap but {reason}; kept as picture",
                           target=item.element_id, suggested_action="confirm whether this is a watermark")
            continue
        run.kinds[item.element_id] = "watermark_candidate"
        run.flags.setdefault(item.element_id, []).append("watermark_candidate")
        rec.add_log("T-10", item.element_id, "picture without caption inside a repeated bitmap",
                    before={"normalized_type": "picture"},
                    after={"normalized_type": "watermark_candidate", "cover": cover})


def _link_captions(items: list[RawItem], profile: Profile, run: FigureRun, rec: Recorder) -> None:
    figure_kw = [k for k in profile.caption_keywords if k not in profile.table_caption_keywords]
    figures = [i for i in items if i.parent_id is None and i.bbox is not None
               and ((i.label == "picture" and run.kinds.get(i.element_id) != "watermark_candidate")
                    or run.kinds.get(i.element_id) == "screenshot")]
    tables = [i for i in items if i.parent_id is None and i.bbox is not None and i.label == "table"
              and i.element_id not in run.kinds]
    for index, item in enumerate(items):
        if item.label != "caption" or item.bbox is None:
            continue
        text = " ".join(item.text.split())
        if _starts_with(text, profile.table_caption_keywords):
            pool = [(_gap(item.bbox, t.bbox), t) for t in tables if t.page == item.page]   # type: ignore[arg-type]
        elif _starts_with(text, figure_kw):
            # Phía trên: đáy hình không thấp hơn đáy caption và hai bên chồng nhau theo chiều ngang
            # (F86: dải hình ở lề phải cùng hàng caption không phải hình của caption).
            pool = [(max(0.0, item.bbox.y0 - f.bbox.y1), f) for f in figures   # type: ignore[union-attr]
                    if f.page == item.page and f.bbox.y1 <= item.bbox.y1        # type: ignore[union-attr]
                    and min(f.bbox.x1, item.bbox.x1) > max(f.bbox.x0, item.bbox.x0)]  # type: ignore[union-attr]
        else:
            if item.parent_id is not None:
                run.captions.setdefault(item.parent_id, (item.element_id, CaptionLink(source="docling")))
            continue
        pool.sort(key=lambda pair: pair[0])
        if not pool or (len(pool) > 1 and pool[1][0] - pool[0][0] <= _TIE):
            count = "no" if not pool else "two"
            rec.add_review(item.element_id, "caption_ambiguous",
                           f"caption {text[:40]!r}: {count} candidate on the page; kept Docling link",
                           target=item.parent_id or item.element_id, suggested_action="link the caption manually")
            if item.parent_id is not None:
                run.captions.setdefault(item.parent_id, (item.element_id, CaptionLink(source="docling")))
            continue
        target = pool[0][1]
        if target.element_id == item.parent_id:
            run.captions.setdefault(target.element_id, (item.element_id, CaptionLink(source="docling")))
            continue
        rec.add_log("T-11", item.element_id, f"caption keyword points to {target.label} {target.element_id}",
                    target=target.element_id, before={"parent": item.parent_id}, after={"parent": target.element_id})
        run.flags.setdefault(item.element_id, []).append("caption_relinked")
        run.captions[target.element_id] = (item.element_id, CaptionLink(source="rule", rule_id="T-11"))
        items[index] = dataclasses.replace(item, parent_id=target.element_id, parent_label=target.label)
    captioned = set(run.captions)
    for index, item in enumerate(items):
        if item.label in ("picture", "table") and item.has_caption != (item.element_id in captioned):
            items[index] = dataclasses.replace(item, has_caption=item.element_id in captioned)


def _crops(items: Sequence[RawItem], objects: PageObjects, profile: Profile, run: FigureRun,
           rec: Recorder) -> None:
    t = profile.thresholds
    children: dict[str, list[BBox]] = defaultdict(list)
    for item in items:
        if item.parent_id is not None and item.label != "caption" and item.bbox is not None:
            children[item.parent_id].append(item.bbox)
    missing: set[int] = set()
    for item in items:
        is_image = (item.label == "picture" and item.parent_id is None) or item.element_id in run.screenshots
        if not is_image or item.bbox is None:
            continue
        bbox, region, sources = item.bbox, item.bbox, ["docling"]
        page = objects.get(item.page)
        if page is None and item.page not in missing:
            missing.add(item.page)
            rec.add_log("T-14", f"p{item.page:03d}", "no_object_info: crop uses Docling bbox and labels only")
        for raw in (page or {}).get("bitmaps", []):
            bm = _bbox(raw)
            if overlap_ratio(bbox, [bm]) >= t.crop_bitmap_min and _union(region, bm) != region:
                region = _union(region, bm)
                sources.append("bitmap")
        for raw in (page or {}).get("paths", []):
            path = _bbox(raw)
            cx, cy = (path.x0 + path.x1) / 2, (path.y0 + path.y1) / 2
            m = t.crop_vector_margin
            if (bbox.x0 <= cx <= bbox.x1 and bbox.y0 <= cy <= bbox.y1
                    and path.x0 >= bbox.x0 - m and path.x1 <= bbox.x1 + m
                    and path.y0 >= bbox.y0 - m and path.y1 <= bbox.y1 + m and _union(region, path) != region):
                region = _union(region, path)
                sources.append("vector")
        for label in children.get(item.element_id, []):
            if _union(region, label) != region:
                region = _union(region, label)
                sources.append("label")
        width = item.page_width or region.x1 + t.crop_padding
        crop = region.padded(t.crop_padding, width, item.page_height or region.y1 + t.crop_padding)
        kinds = list(dict.fromkeys(sources))
        run.images[item.element_id] = ImageInfo(crop_bbox=_box(crop), crop_sources=kinds)   # type: ignore[arg-type]
        if len(kinds) > 1:
            rec.add_log("T-14", item.element_id, f"crop extended by {', '.join(kinds[1:])}",
                        before={"bbox": bbox.as_dict()}, after={"crop_bbox": crop.as_dict()})


def decide_figures(items: Sequence[RawItem], objects: PageObjects | None, profile: Profile,
                   rec: Recorder) -> FigureRun:
    """T-09 → T-10 → T-11 → T-14 (T-18 chạy trong `decide_furniture`, trước luật furniture)."""
    objects = objects or {}
    run = FigureRun(items=list(items))
    _screenshots(run.items, objects, profile, run, rec)
    _watermarks(run.items, objects, profile, run, rec)
    _link_captions(run.items, profile, run, rec)
    _crops(run.items, objects, profile, run, rec)
    return run
