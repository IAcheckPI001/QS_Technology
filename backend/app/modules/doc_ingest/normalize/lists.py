"""T-08 list cha–con, phiên bản 1 (contract T-08, sửa 2026-11-09; kiểm trên F54).

Docling trả list_item phẳng (không lồng, `enumerated` luôn false, `marker` không đáng tin),
nên cấp được suy từ lề trái `x0`. Lề là tín hiệu chính, glyph đầu dòng chỉ là tín hiệu phụ
trong khoảng thụt 3–18 pt. Khi không chắc: sinh review, không gán cha im lặng.

Không sửa `text` (glyph `o ` vẫn nằm trong text nguyên văn).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.schemas.normalized import ListInfo
from app.modules.doc_ingest.schemas.profile import Profile

_SAME_LEVEL = 3.0   # hai lề cách nhau ≤ 3 pt là cùng cấp


@dataclass
class ListRun:
    info: dict[str, ListInfo] = field(default_factory=dict)    # element_id -> list_info
    flags: dict[str, list[str]] = field(default_factory=dict)
    orphans: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)


@dataclass
class _Level:
    element_id: str
    x: float
    depth: int
    parent: str | None
    page: int
    marker: str | None
    ambiguous: bool = False
    orphan: bool = False


def _glyph(text: str, glyphs: Sequence[str]) -> str | None:
    """Glyph đầu dòng chỉ khi theo sau là khoảng trắng (`o M1920` có, `operation` không)."""
    for g in glyphs:
        if text.startswith(g) and len(text) > len(g) and text[len(g)].isspace():
            return g
    return None


def _flow(items: Sequence[RawItem], skip: frozenset[str]) -> dict[int, list[RawItem]]:
    """Phần tử body theo trang, thứ tự đọc; bỏ furniture, phần tử con của picture/table (gồm
    nhãn T-18), watermark và hình trùng T-19."""
    pages: dict[int, list[RawItem]] = defaultdict(list)
    for item in items:
        if item.is_furniture or item.parent_id is not None or item.element_id in skip or item.bbox is None:
            continue
        pages[item.page].append(item)
    return pages


def decide_lists(items: Sequence[RawItem], profile: Profile, rec: Recorder,
                 skip: frozenset[str] = frozenset()) -> ListRun:
    run = ListRun()
    indent_min = profile.thresholds.list_indent_min
    glyphs = profile.list_glyphs
    pages = _flow(items, skip)
    stack: list[_Level] = []
    prev_page: int | None = None
    prev_ends_with_list = False

    for page in sorted(pages):
        flow = pages[page]
        # Qua trang: list_item đầu trang nối khối list cuối trang liền trước.
        carry = (prev_page == page - 1 and prev_ends_with_list and bool(flow) and flow[0].label == "list_item")
        if not carry:
            stack = []
        page_list_x = [i.bbox.x0 for i in flow if i.label == "list_item"]  # type: ignore[union-attr]
        for item in flow:
            if item.label != "list_item":
                stack = []          # mọi phần tử body khác ngắt khối list
                continue
            x = item.bbox.x0  # type: ignore[union-attr]
            glyph = _glyph(item.text, glyphs)
            marker = glyph or (item.marker or None)
            block_start = not stack
            level, problem = _place(stack, x, glyph, indent_min)
            if (block_start and glyph is not None
                    and any(px <= x - indent_min for px in page_list_x)):
                problem = "orphan"
            parent = level.parent if level is not None else None
            depth = level.depth if level is not None else 0
            run.info[item.element_id] = ListInfo(indent_x=round(x, 2), depth=depth,
                                                 parent_element_id=parent, marker=marker)
            stack.append(_Level(item.element_id, x, depth, parent, page, marker,
                                ambiguous=problem is not None,
                                orphan=problem == "orphan" or (level is not None and level.orphan)))
            if parent is not None:
                parent_page = next((s.page for s in stack if s.element_id == parent), page)
                rec.add_log("T-08", item.element_id, "list_item con: thụt sâu hơn hoặc cùng lề với anh em",
                            target=parent, after={"parent_element_id": parent, "depth": depth})
                if parent_page != page:
                    run.flags.setdefault(item.element_id, []).append("list_cross_page")
            if problem == "orphan":
                run.orphans.append(item.element_id)
                rec.add_review(item.element_id, "list_orphan",
                               f"list_item bắt đầu bằng glyph '{glyph}' ở x={x:.0f} thụt sâu hơn list khác "
                               "cùng trang nhưng đứng đầu khối list (không có cha phía trên)",
                               suggested_action="Chỉ ra list_item cha hoặc xác nhận là cấp 1")
            elif problem == "ambiguous":
                run.ambiguous.append(item.element_id)
                rec.add_review(item.element_id, "list_level_ambiguous",
                               f"chưa rõ cấp list ở x={x:.0f}: lề không khớp cấp nào đang mở, thụt dưới "
                               f"{indent_min:.0f} pt mà không có glyph, hoặc cùng cấp với mục chưa rõ cấp",
                               suggested_action="Xác nhận cấp và list_item cha")
        prev_page = page
        prev_ends_with_list = bool(flow) and flow[-1].label == "list_item"

    _mark_mixed_markers(run)
    return run


def _place(stack: list[_Level], x: float, glyph: str | None,
           indent_min: float) -> tuple[_Level | None, str | None]:
    """Đặt mục ở lề `x` vào ngăn xếp cấp đang mở (sửa `stack` tại chỗ). Trả (cấp của mục
    — với `parent`, `depth` — hoặc None nếu là cấp 1 mới, vấn đề: None | ambiguous)."""
    if not stack:
        return None, None
    popped: _Level | None = None
    while stack and stack[-1].x > x + _SAME_LEVEL:
        popped = stack.pop()
    if not stack:
        # Lùi qua cả cấp gốc của khối: lề không khớp cấp nào. Gốc là mục mồ côi (đã review)
        # thì mục này là cấp 1 bình thường.
        return None, None if popped is not None and popped.orphan else "ambiguous"
    top = stack[-1]
    if abs(top.x - x) <= _SAME_LEVEL:
        stack.pop()             # anh em: thay chỗ của top trong ngăn xếp
        # Anh em của mục mơ hồ/mồ côi cũng chưa rõ cấp: review tiếp, không đoán.
        return (_Level("", x, top.depth, top.parent, top.page, None, orphan=top.orphan),
                "ambiguous" if top.ambiguous else None)
    # top.x < x - _SAME_LEVEL: thụt sâu hơn đỉnh.
    if popped is not None:
        return _Level("", x, 0, None, top.page, None), "ambiguous"
    if x - top.x >= indent_min or glyph is not None:
        return _Level("", x, top.depth + 1, top.element_id, top.page, None), None
    return _Level("", x, 0, None, top.page, None), "ambiguous"


def _mark_mixed_markers(run: ListRun) -> None:
    """Anh em cùng cha dùng marker khác nhau → cờ thông tin `list_marker_mixed`."""
    groups: dict[str, list[str]] = defaultdict(list)
    for element_id, info in run.info.items():
        if info.parent_element_id is not None:
            groups[info.parent_element_id].append(element_id)
    for children in groups.values():
        if len({run.info[c].marker for c in children}) > 1:
            for c in children:
                run.flags.setdefault(c, []).append("list_marker_mixed")
