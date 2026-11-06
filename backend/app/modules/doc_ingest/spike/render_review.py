"""Trang HTML để người duyệt so output Docling với trang gốc bằng mắt."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

_STYLE = """
body{font:14px system-ui,sans-serif;margin:16px;color:#222}
table.grid{border-collapse:collapse;margin:4px 0}
table.grid td,table.grid th{border:1px solid #999;padding:2px 6px;vertical-align:top}
.pair{display:flex;gap:16px;align-items:flex-start;border-top:2px solid #ccc;padding:12px 0}
.pair img{max-width:48vw;border:1px solid #ccc}
.meta{color:#555;font-size:12px}
.gallery img{max-height:360px;border:1px solid #ccc;margin:4px}
"""


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<style>{_STYLE}</style></head><body>{body}</body></html>")


def write_tables_html(path: Path, page_no: int, tables: list[dict[str, Any]]) -> None:
    parts = [f"<h1>Trang {page_no}: {len(tables)} bảng</h1>",
             "<p>Trái: crop vùng bảng trên trang. Phải: HTML Docling dựng + lưới thô. "
             "Chấm: đủ cột? header lọt vào dữ liệu? ô merge? dải mã nằm trọn một ô?</p>"]
    for table in tables:
        grid_rows = "".join(
            "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
            for row in table["grid"]
        )
        parts.append(
            "<div class='pair'>"
            f"<div><img src='{html.escape(table['crop'])}'></div>"
            f"<div><div class='meta'>item {table['order']} · {table['num_rows']}×{table['num_cols']} · "
            f"header rows {table['column_header_rows']} · merged {len(table['merged_cells'])} · "
            f"caption: {html.escape(table['captions'] or '-')}</div>"
            f"{table['html']}<details><summary>grid thô</summary>"
            f"<table class='grid'>{grid_rows}</table></details></div></div>"
        )
    path.write_text(_page(f"tables p{page_no}", "".join(parts)), encoding="utf-8")


def write_index(path: Path, summary: dict[str, Any]) -> None:
    parts = [f"<h1>Parsing spike: {html.escape(summary['doc'])}</h1>",
             f"<pre class='meta'>{html.escape(str(summary['config']))}</pre>"]
    for page in summary["pages"]:
        n = page["pdf_page_index"]
        stem = f"p{n:03d}"
        parts.append(
            f"<h2>pdf_page_index {n} · page_label {html.escape(str(page['page_label']))}</h2>"
            f"<div class='meta'>{html.escape(str(page['label_counts']))} · "
            f"docling {page['docling_seconds']}s · footer {html.escape(str(page['footer_texts']))}</div>"
            f"<p><a href='{stem}_tables.html'>bảng</a> · <a href='{stem}_items.json'>items</a></p>"
            f"<div class='pair'><img src='{stem}_overlay.png'></div>"
        )
        for pic in page["pictures"]:
            order = pic["order"]
            parts.append(
                f"<div class='meta'>picture {order}: bitmap_overlap {pic['bitmap_overlap']}, "
                f"vector_paths {pic['vector_paths_inside']}, caption {html.escape(pic['captions'] or '-')}</div>"
                f"<div class='gallery'><img src='{stem}_pictures/e{order}_pad_s4.png' title='pad s4'>"
                f"<img src='{stem}_pictures/e{order}_tight_s2.png' title='tight s2'></div>"
            )
    path.write_text(_page(f"spike {summary['doc']}", "".join(parts)), encoding="utf-8")
