"""T-12: parse mã parameter thành ParamRef (D-01, contract §4).

Ngữ pháp (đơn / dải / danh sách) là chung; tập prefix (`#`, `M`, ...) lấy từ profile, nên
profile `default` (không có prefix) không parse mã nào.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.modules.doc_ingest.schemas.base import StrictModel


class ParamRef(StrictModel):
    prefix: str
    kind: Literal["single", "range", "list"]
    codes: list[int]           # tường minh, tăng dần, không trùng; nguồn duy nhất để khớp
    range_start: int | None = None
    range_end: int | None = None
    label: str                 # nguyên văn


@dataclass(frozen=True)
class ParamParse:
    ref: ParamRef | None
    error: str | None = None   # lý do unparseable
    flags: tuple[str, ...] = field(default=())


def _prefix_group(prefixes: Sequence[str]) -> str:
    return "|".join(re.escape(p) for p in sorted(prefixes, key=len, reverse=True))


def parse_param_ref(text: str, prefixes: Sequence[str], max_range_len: int) -> ParamParse:
    label = text.strip()
    if not prefixes or not label:
        return ParamParse(None, "no_prefix")
    pfx = _prefix_group(prefixes)

    single = re.fullmatch(rf"({pfx})(\d+)", label)
    if single:
        code = int(single.group(2))
        return ParamParse(ParamRef(prefix=single.group(1), kind="single", codes=[code], label=label))

    rng = re.fullmatch(rf"({pfx})(\d+)\s*[-–—]\s*({pfx})(\d+)", label)
    if rng:
        p1, a, p2, b = rng.group(1), int(rng.group(2)), rng.group(3), int(rng.group(4))
        if p1 != p2:
            return ParamParse(None, "mixed_prefix")
        if b <= a:
            return ParamParse(None, "range_not_increasing")
        flags = ("range_too_long",) if b - a + 1 > max_range_len else ()
        ref = ParamRef(prefix=p1, kind="range", codes=list(range(a, b + 1)),
                       range_start=a, range_end=b, label=label)
        return ParamParse(ref, None, flags)

    if re.fullmatch(rf"(?:{pfx})\d+(?:[\s,]+(?:{pfx})\d+)+", label):
        tokens = re.findall(rf"({pfx})(\d+)", label)
        if len({p for p, _ in tokens}) > 1:
            return ParamParse(None, "mixed_prefix")
        codes = sorted({int(n) for _, n in tokens})
        return ParamParse(ParamRef(prefix=tokens[0][0], kind="list", codes=codes, label=label))

    return ParamParse(None, "unrecognized_pattern")


def matches(ref: ParamRef, prefix: str, code: int) -> bool:
    """Khớp một mã: cùng namespace prefix và `codes @> [code]`."""
    return ref.prefix == prefix and code in ref.codes


def overlapping(refs: Sequence[tuple[str, ParamRef]]) -> list[tuple[str, str]]:
    """Các cặp (key, key) cùng prefix có codes giao nhau (`param_code_overlap`)."""
    pairs: list[tuple[str, str]] = []
    for i, (key_a, a) in enumerate(refs):
        codes_a = set(a.codes)
        for key_b, b in refs[i + 1:]:
            if a.prefix == b.prefix and codes_a.intersection(b.codes):
                pairs.append((key_a, key_b))
    return pairs


# ---------------------------------------------------------------------- T-12 trên text

TextRole = Literal["definition", "value_option", "mention"]


class TextParamRef(ParamRef):
    """Mã parameter tìm thấy trong text của một phần tử (T-12 trên text, sửa 2026-11-09).

    `text[start:end] == label`; `role`: `definition` (mã đứng đầu phần tử, sau là `:`),
    `value_option` (sau mã là `=`), `mention` (nhắc trong câu)."""

    start: int
    end: int
    role: TextRole


@dataclass(frozen=True)
class TextScan:
    refs: list[TextParamRef] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)      # (label, lý do) → param_unparseable
    too_long: list[str] = field(default_factory=list)                # label → range_too_long
    near_miss: list[str] = field(default_factory=list)               # prefix đúng, số chữ số không khớp


_LIST_SEP = re.compile(r"[\s,]+")
_RANGE_SEP = re.compile(r"\s*[-–—]\s*")
_LEAD = re.compile(r"\s*(?:\S\s+)?")          # đầu phần tử: rỗng hoặc một glyph đầu dòng + khoảng trắng
_DEF_TAIL = re.compile(r"\s*:")
_VALUE_TAIL = re.compile(r"\s*=")


def _role(text: str, start: int, end: int) -> TextRole:
    if _VALUE_TAIL.match(text, end):
        return "value_option"
    if _LEAD.fullmatch(text[:start]) and _DEF_TAIL.match(text, end):
        return "definition"
    return "mention"


def find_param_refs(text: str, prefixes: Sequence[str], digit_patterns: dict[str, str],
                    max_range_len: int) -> TextScan:
    """Quét mã parameter trong text. Chỉ prefix có trong `digit_patterns` (profile
    `param_text_patterns`) mới được quét; profile không khai báo → không quét gì.

    Token `PREFIX + chữ số` đứng riêng (không dính chữ/số phía trước hoặc sau). Token cùng
    prefix nối bằng `,`/khoảng trắng hoặc gạch ngang được gộp rồi parse bằng ngữ pháp
    contract §4 (`parse_param_ref`); khác prefix → tách thành nhiều ref (văn xuôi)."""
    scan = TextScan()
    active = [p for p in prefixes if p in digit_patterns]
    if not text or not active:
        return scan
    pfx = _prefix_group(prefixes)
    tokens: list[tuple[int, int, str]] = []          # (start, end, prefix)
    for m in re.finditer(rf"(?<![\w#])({pfx})(\d+)", text):
        prefix, digits = m.group(1), m.group(2)
        glued = m.end() < len(text) and (text[m.end()].isalnum() or text[m.end()] == "_")
        if prefix in digit_patterns and not glued and re.fullmatch(digit_patterns[prefix], digits):
            tokens.append((m.start(), m.end(), prefix))
        else:
            scan.near_miss.append(m.group(0) + (text[m.end()] if glued else ""))
    groups: list[list[tuple[int, int, str]]] = []
    for token in tokens:
        if groups:
            last = groups[-1][-1]
            gap = text[last[1]:token[0]]
            if last[2] == token[2] and (_LIST_SEP.fullmatch(gap) or _RANGE_SEP.fullmatch(gap)):
                groups[-1].append(token)
                continue
        groups.append([token])
    for group in groups:
        start, end = group[0][0], group[-1][1]
        label = text[start:end]
        parsed = parse_param_ref(label, prefixes, max_range_len)
        if parsed.ref is None:
            scan.errors.append((label, parsed.error or "unrecognized_pattern"))
            continue
        if "range_too_long" in parsed.flags:
            scan.too_long.append(label)
        scan.refs.append(TextParamRef(**parsed.ref.model_dump(), start=start, end=end,
                                      role=_role(text, start, end)))
    return scan
