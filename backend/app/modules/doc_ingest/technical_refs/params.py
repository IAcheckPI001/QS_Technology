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
