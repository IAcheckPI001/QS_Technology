"""S0: đo từng trang PDF bằng pypdfium2 trước khi parse (BL-24, contract §7).

Chỉ đo; quyết định OCR nằm ở `s0.py` (thuần Python, test được không cần PDF).
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium

from app.modules.doc_ingest.geometry import BBox
from app.modules.doc_ingest.parse.pdf_probe import count_path_objects, image_objects, page_label

_BAD = {"�"}


def measure_pages(pdf_path: Path, pages: list[int]) -> list[dict[str, object]]:
    pdf = pdfium.PdfDocument(str(pdf_path))
    out: list[dict[str, object]] = []
    for page_no in pages:
        page = pdf[page_no - 1]
        width, height = page.get_size()
        text = page.get_textpage().get_text_range()
        visible = [c for c in text if not c.isspace()]
        bad = sum(1 for c in visible if c in _BAD or (ord(c) < 32))
        area = sum((b.x1 - b.x0) * (b.y1 - b.y0) for b in image_objects(page, height))
        out.append({
            "page": page_no,
            "text_chars": len(visible),
            "bad_char_ratio": round(bad / len(visible), 4) if visible else 0.0,
            "rotation": page.get_rotation(),
            "bitmap_area_ratio": round(min(1.0, area / (width * height)), 3),
            "vector_path_count": count_path_objects(page, BBox(0, 0, width, height), height),
            "page_label": page_label(pdf, page_no - 1),
        })
    return out
