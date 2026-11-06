"""Chạy Docling theo trang và render ảnh trang bằng pypdfium2 cho CLI `run`.

Mỗi trang chạy một lần `convert(page_range=(n, n))` như spike/fixture, nên Docling JSON
cùng dạng với fixture golden và đi thẳng vào `normalize/`.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from app.modules.doc_ingest.parse.make_fixture import sha256_file, strip_images
from app.modules.doc_ingest.parse.pdf_probe import page_objects, page_words

__all__ = ["build_converter", "convert_pages", "extract_objects", "extract_words", "render_crops", "render_pages",
           "sha256_file", "tool_versions"]


def build_converter(base_scale: float, table_mode: str, *, images: bool = True, ocr: bool = False):
    """`ocr=True`: RapidOCR backend torch (có sẵn trong venv ingest; backend mặc định
    onnxruntime chưa cài), OCR toàn trang, tiếng Anh. Cấu hình ghi trong `s0.OCR_ENGINE`."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = ocr
    if ocr:
        options.ocr_options = RapidOcrOptions(lang=["en"], force_full_page_ocr=True, backend="torch")
    options.do_table_structure = True
    options.table_structure_options.mode = (
        TableFormerMode.ACCURATE if table_mode == "accurate" else TableFormerMode.FAST
    )
    options.table_structure_options.do_cell_matching = True
    options.images_scale = base_scale
    options.generate_page_images = images
    options.generate_picture_images = images
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def convert_pages(pdf_path: Path, pages: list[int], table_mode: str,
                  ocr_pages: set[int] | None = None) -> Iterator[tuple[int, dict[str, Any], float]]:
    """(page_no, DoclingDocument dict không ảnh, giây Docling) cho từng trang; trang trong
    `ocr_pages` chạy converter có OCR (tạo lười)."""
    converters: dict[bool, Any] = {}
    for page_no in pages:
        ocr = page_no in (ocr_pages or set())
        if ocr not in converters:
            converters[ocr] = build_converter(1.0, table_mode, images=False, ocr=ocr)
        started = time.perf_counter()
        result = converters[ocr].convert(pdf_path, page_range=(page_no, page_no))
        doc = strip_images(result.document.export_to_dict())
        yield page_no, doc, round(time.perf_counter() - started, 2)


def page_count(pdf_path: Path) -> int:
    return len(pdfium.PdfDocument(str(pdf_path)))


def render_pages(pdf_path: Path, pages: list[int], out_dir: Path, scale: float = 2.0) -> dict[int, str]:
    """Render PNG từng trang; trả {page_no: tên file} (đường dẫn tương đối trong out_dir)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    names: dict[int, str] = {}
    for page_no in pages:
        name = f"p{page_no:03d}.png"
        pdf[page_no - 1].render(scale=scale).to_pil().convert("RGB").save(out_dir / name, optimize=True)
        names[page_no] = name
    return names


def extract_words(pdf_path: Path, pages: list[int]) -> dict[int, list[dict[str, object]]]:
    """Từ text layer từng trang (nguồn độc lập cho V-01)."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    words: dict[int, list[dict[str, object]]] = {}
    for page_no in pages:
        page = pdf[page_no - 1]
        words[page_no] = page_words(page, page.get_size()[1])
    return words


def extract_objects(pdf_path: Path, pages: list[int]) -> dict[int, dict[str, list[dict[str, Any]]]]:
    """Bitmap (kèm px) và nét vector từng trang cho T-09, T-10, T-14."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    return {page_no: page_objects(pdf[page_no - 1], pdf[page_no - 1].get_size()[1]) for page_no in pages}


def render_crops(pdf_path: Path, requests: list[Any], run_dir: Path) -> dict[str, dict[str, Any]]:
    """T-14: render vùng crop. `original` ở `max(3, độ phân giải bitmap trong vùng)` (trần 4),
    `preview` thu từ original về scale ≤ 2 và rộng ≤ 1600 px. Trang xoay bị bỏ qua (crop theo
    tọa độ chưa xoay, chuẩn hóa hướng chưa làm)."""
    from app.modules.doc_ingest.pipeline import image_dir

    pdf = pdfium.PdfDocument(str(pdf_path))
    out: dict[str, dict[str, Any]] = {}
    for req in requests:
        page = pdf[req.page - 1]
        if page.get_rotation():
            continue
        width, height = page.get_size()
        x0, y0, x1, y1 = req.crop
        scale = round(min(4.0, max(3.0, req.native_px_per_pt)), 3)
        image = page.render(scale=scale, crop=(x0, height - y1, width - x1, y0)).to_pil().convert("RGB")
        folder = image_dir(req.element_id)
        (run_dir / folder).mkdir(parents=True, exist_ok=True)
        image.save(run_dir / folder / "original.png", optimize=True)
        factor = min(2.0, 1600 / max(1.0, x1 - x0)) / scale
        preview = image.resize((max(1, round(image.width * factor)), max(1, round(image.height * factor))))
        preview.save(run_dir / folder / "preview.png", optimize=True)
        out[req.element_id] = {"original_path": f"{folder}/original.png", "preview_path": f"{folder}/preview.png",
                               "scale": scale, "px_w": image.width, "px_h": image.height}
    return out


def tool_versions() -> dict[str, str]:
    from importlib.metadata import version

    return {name: version(name) for name in ("docling", "docling-core", "pypdfium2")}
