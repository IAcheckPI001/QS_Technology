"""Dựng `content` nguyên văn (contract C2 §6.1): một dòng mỗi phần tử, list lồng theo T-08, bảng dạng markdown.

Không thêm câu tự viết vào content; ngoại lệ duy nhất là dòng tiêu đề lặp lại của phần thủ tục/bảng bị tách
(`(phần i/n …)`), đã ghi trong contract.
"""

from __future__ import annotations

import re

from app.modules.doc_ingest.schemas.normalized import LogicalTable, NormalizedElement, Row

INDENT = "    "
_PIPE = re.compile(r"(?<!\\)\|")


def element_line(element: NormalizedElement) -> str | None:
    """Dòng content của một phần tử; picture/screenshot/bảng không có dòng (ảnh vào assets, bảng render riêng)."""
    if element.normalized_type in ("picture", "screenshot", "table_segment"):
        return None
    text = (element.text or "").strip()
    if not text:
        return None
    if element.normalized_type == "list_item" and element.list_info is not None:
        info = element.list_info
        indent = INDENT * info.depth
        has_glyph = info.marker is not None and text.startswith(info.marker + " ")
        return f"{indent}{text}" if has_glyph else f"{indent}- {text}"
    return text


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def header_line(table: LogicalTable) -> str | None:
    """Dòng header theo `columns` của bảng logic; mọi cột không có header → None."""
    names = [c.header_text for c in table.columns]
    if all(not n for n in names):
        return None
    return "| " + " | ".join(_cell(n or "") for n in names) + " |"


def separator_line(table: LogicalTable) -> str:
    return "|" + "|".join("---" for _ in table.columns) + "|"


def row_line(table: LogicalTable, row: Row) -> str:
    texts = [""] * len(table.columns)
    for cell in row.cells:
        if 0 <= cell.col < len(texts):
            texts[cell.col] = f"{texts[cell.col]} {cell.text}".strip() if texts[cell.col] else cell.text
    return "| " + " | ".join(_cell(t) for t in texts) + " |"


def data_rows(table: LogicalTable) -> list[Row]:
    """Dòng dữ liệu: bỏ dòng header (gồm header lặp ở segment sau) vì header lấy từ `columns`."""
    return [r for r in table.rows if not r.is_header and not r.repeated_header]


def parse_markdown_row(line: str) -> list[str]:
    """Tách một dòng bảng markdown theo `|` không escape (dùng cho CQ-01)."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [part.strip() for part in _PIPE.split(body)]
