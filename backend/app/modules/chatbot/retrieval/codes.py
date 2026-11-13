"""Trích mã kỹ thuật từ câu hỏi để khớp cột `doc_chunks_v2.codes` (D-009, S-02).

Cùng luật chuẩn hóa với adapter `doc_ingest/export/doc_chunks_v2.normalize_code` (không import được: ranh giới
import của tool offline) — đổi một bên thì đổi bên kia: `#`+số hoặc 1–4 chữ + số, có thể `.HẬU_TỐ` và `+`/`-`;
chữ hoa, bỏ số 0 đầu (`#0008` → `#8`). Tên model (F54, F86…) không phải mã.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_CODE = re.compile(r"^(#|[A-Z]{1,4})(\d{1,6})((?:\.[A-Z0-9]+)?[+-]?)$")
# Ứng viên trong câu: "#12010", "M1920", "X41", "CN3", "AX1.ENA", "PUL1+" (ranh giới không phải chữ/số).
_TOKEN = re.compile(r"(?<![\w#])(#\s?\d{1,6}|[A-Za-z]{1,4}\d{1,6}(?:\.[A-Za-z0-9]+)?[+-]?)(?![\w])")


def normalize_code(text: str) -> str | None:
    match = _CODE.match("".join(text.split()).upper())
    if match is None:
        return None
    prefix, digits, suffix = match.groups()
    return f"{prefix}{int(digits)}{suffix}"


def extract_codes(text: str, exclude: Iterable[str] = ()) -> list[str]:
    """Mã trong câu hỏi theo thứ tự xuất hiện, đã chuẩn hóa, bỏ trùng; bỏ các giá trị trong `exclude` (vd. model)."""
    skip = {e.upper() for e in exclude}
    out: list[str] = []
    for raw in _TOKEN.findall(text):
        code = normalize_code(raw)
        if code is not None and code not in skip and code not in out:
            out.append(code)
    return out
