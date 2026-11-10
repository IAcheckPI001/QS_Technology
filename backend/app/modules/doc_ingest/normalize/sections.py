"""T-07 section path theo số đánh của heading (contract §5). Không đoán cấp theo cỡ chữ.

Heading đánh số `1.2 Tên` hoặc `<từ khóa> 2` (từ khóa ở profile: PART, CHAPTER…) mở/đóng
cấp theo dãy số: `CHAPTER 2` = (2,), `2.1 …` = (2, 1) nằm dưới nó. Heading không khớp
→ `label_heading` (Note:, Notes:…), không đổi path. Trạng thái mang qua trang.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.schemas.profile import Profile

HEADING_LABELS = frozenset({"section_header", "title"})
_NUMBERED = re.compile(r"^(?P<num>\d+(?:\.\d+)*)\.?\s+(?P<title>\S.*)$")
_GLUED = re.compile(r"^(?P<num>\d+(?:\.\d+)+)(?P<title>[^\W\d_].*)$")   # OCR dính chữ: `2.9.1AXIS`


@dataclass(frozen=True)
class HeadingNumber:
    numbers: tuple[int, ...]
    source: str          # numbered | keyword | glued

    @property
    def strong(self) -> bool:
        """Đủ mạnh để ghi đè nhãn header/footer của Docling (T-17 e): từ khóa, hoặc số nhiều
        đoạn. Số một đoạn (`320 mm`) có thể là nhãn kích thước, không phải heading."""
        return self.source == "keyword" or len(self.numbers) > 1


def parse_heading(text: str, profile: Profile) -> HeadingNumber | None:
    text = " ".join(text.split())
    if profile.section_keywords:
        words = "|".join(re.escape(k) for k in profile.section_keywords)
        # Tiêu đề có thể dính ngay sau `:`/`.` nếu bắt đầu bằng chữ cái (F54 `PART 1:CONTROLLER
        # OVERVIEW`, I-26); `PART 1.2 X` vẫn không khớp.
        match = re.match(rf"^(?:{words})\s+(?P<num>\d+)(?:\s*[.:]?(?:\s+\S.*)?|\s*[.:][^\W\d_].*)$",
                         text, re.IGNORECASE)
        if match:
            return HeadingNumber((int(match["num"]),), "keyword")
    for pattern, source in ((_NUMBERED, "numbered"), (_GLUED, "glued")):
        match = pattern.match(text)
        if match and any(ch.isalpha() for ch in match["title"]):
            return HeadingNumber(tuple(int(n) for n in match["num"].split(".")), source)
    return None


@dataclass
class SectionInfo:
    normalized_type: str | None = None      # heading | label_heading với ứng viên heading
    section_path: list[str] = field(default_factory=list)
    section_path_source: str = "none"
    label_heading: str | None = None
    flags: list[str] = field(default_factory=list)


def assign_sections(items: Sequence[RawItem], demoted: set[str], profile: Profile,
                    rec: Recorder) -> dict[str, SectionInfo]:
    """`demoted`: element_id header/footer được T-17 trả về body làm heading."""
    stack: list[tuple[tuple[int, ...], str]] = []
    label: str | None = None
    out: dict[str, SectionInfo] = {}
    for item in items:
        if item.is_furniture:
            continue
        path = [title for _, title in stack]
        is_candidate = item.parent_id is None and (item.label in HEADING_LABELS or item.element_id in demoted)
        if not is_candidate:
            out[item.element_id] = SectionInfo(section_path=path, section_path_source="inherited" if path else "none",
                                               label_heading=label)
            continue
        text = " ".join(item.text.split())
        heading = parse_heading(text, profile)
        if heading is None:
            label = text
            out[item.element_id] = SectionInfo("label_heading", path, "inherited" if path else "none", label)
            continue
        flags = ["heading_spacing"] if heading.source == "glued" else []
        while stack and not (len(stack[-1][0]) < len(heading.numbers)
                             and heading.numbers[:len(stack[-1][0])] == stack[-1][0]):
            stack.pop()
        if len(heading.numbers) > 1 and (not stack or stack[-1][0] != heading.numbers[:-1]):
            flags.append("section_parent_missing")
        stack.append((heading.numbers, text))
        label = None
        out[item.element_id] = SectionInfo("heading", [title for _, title in stack], "numbering", None, flags)
        rec.add_log("T-07", item.element_id, "numbered heading opens section",
                    after={"numbers": ".".join(map(str, heading.numbers)), "depth": len(stack), "flags": flags})
    return out
