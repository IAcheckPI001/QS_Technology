"""Đọc thông tin trang trực tiếp từ PDF bằng pypdfium2 (page label, bitmap, path vector)."""

from __future__ import annotations

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.modules.doc_ingest.geometry import BBox


def page_label(pdf: pdfium.PdfDocument, index0: int) -> str | None:
    """Nhãn trang in từ /PageLabels (FPDF_GetPageLabel); None khi PDF không khai báo."""
    raw_doc = pdf.raw
    length = pdfium_c.FPDF_GetPageLabel(raw_doc, index0, None, 0)
    if length <= 2:
        return None
    buffer = (pdfium_c.c_ubyte * length)()
    pdfium_c.FPDF_GetPageLabel(raw_doc, index0, buffer, length)
    return bytes(buffer).decode("utf-16-le").rstrip("\x00") or None


def page_words(page: pdfium.PdfPage, height: float) -> list[dict[str, object]]:
    """Từ của text layer (ký tự liền nhau không phải khoảng trắng) kèm bbox gốc trên-trái.

    Nguồn độc lập với Docling cho kiểm V-01/V-02.
    """
    textpage = page.get_textpage()
    words: list[dict[str, object]] = []
    chars: list[str] = []
    box: list[float] = []

    def flush() -> None:
        if chars:
            words.append({"text": "".join(chars),
                          "bbox": BBox(box[0], height - box[3], box[2], height - box[1]).as_dict()})
            chars.clear()

    for index in range(textpage.count_chars()):
        char = textpage.get_text_range(index, 1)
        if not char or char.isspace():
            flush()
            continue
        left, bottom, right, top = textpage.get_charbox(index)
        if not chars:
            box = [left, bottom, right, top]
        else:
            box = [min(box[0], left), min(box[1], bottom), max(box[2], right), max(box[3], top)]
        chars.append(char)
    flush()
    return words


def _topleft(obj: pdfium.PdfObject, height: float) -> BBox:
    left, bottom, right, top = obj.get_bounds()
    return BBox(left, height - top, right, height - bottom)


def page_objects(page: pdfium.PdfPage, height: float) -> dict[str, list[dict[str, float]]]:
    """Ảnh bitmap (kèm kích thước px) và nét vector trên trang (top-left origin), cho T-09,
    T-10, T-14. Đối tượng lồng trong Form XObject được pdfium trả bounds theo hệ tọa độ của
    form, không phải của trang (F54 trang 18: ảnh chụp màn hình bị báo ở góc 0,720) → dùng
    bounds của form cấp trang chứa nó."""
    bitmaps: list[dict[str, float]] = []
    paths: list[dict[str, float]] = []
    form: tuple[BBox, list[tuple[int, int]], list[bool]] | None = None

    def flush() -> None:
        if form is None:
            return
        box, px, has_path = form
        if px:
            bitmaps.append({**box.as_dict(), "px_w": px[0][0], "px_h": px[0][1]})
        elif has_path[0]:
            paths.append(box.as_dict())

    for obj in page.get_objects(max_depth=15):
        if obj.level == 0:
            flush()
            form = None
            if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE:
                px_w, px_h = obj.get_px_size()
                bitmaps.append({**_topleft(obj, height).as_dict(), "px_w": px_w, "px_h": px_h})
            elif obj.type == pdfium_c.FPDF_PAGEOBJ_PATH:
                paths.append(_topleft(obj, height).as_dict())
            elif obj.type == pdfium_c.FPDF_PAGEOBJ_FORM:
                form = (_topleft(obj, height), [], [False])
        elif form is not None:
            if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE and not form[1]:
                form[1].append(obj.get_px_size())
            elif obj.type == pdfium_c.FPDF_PAGEOBJ_PATH:
                form[2][0] = True
    flush()
    return {"bitmaps": bitmaps, "paths": paths}


def image_objects(page: pdfium.PdfPage, height: float) -> list[BBox]:
    """Vị trí các ảnh bitmap nhúng trên trang (top-left origin)."""
    return [BBox(b["x0"], b["y0"], b["x1"], b["y1"]) for b in page_objects(page, height)["bitmaps"]]


def count_path_objects(page: pdfium.PdfPage, bbox: BBox, height: float) -> int:
    count = 0
    for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_PATH], max_depth=3):
        left, bottom, right, top = obj.get_bounds()
        cx, cy = (left + right) / 2, height - (bottom + top) / 2
        if bbox.x0 <= cx <= bbox.x1 and bbox.y0 <= cy <= bbox.y1:
            count += 1
    return count
