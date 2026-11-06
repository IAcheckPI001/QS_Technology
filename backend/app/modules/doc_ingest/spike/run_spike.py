"""P-1 Parsing Spike: chạy Docling trên các trang đại diện và xuất dữ liệu để người duyệt chấm.

Docling chạy MỘT lần (layout + TableFormer) ở `--base-scale`; crop picture ở các scale
cao hơn được render lại bằng pypdfium2 theo bbox, đây cũng chính là đường fallback
`page_render_crop` của S1. Mỗi trang xuất:

    p{n}.json            DoclingDocument (ảnh để placeholder)
    p{n}_items.json      danh sách item: label, bbox (pt, top-left), text, table, picture
    p{n}_overlay.png     trang render + bbox + nhãn + reading order
    p{n}_tables.html     mỗi bảng: crop vùng bảng đặt cạnh HTML Docling dựng
    p{n}_pictures/       crop picture: docling ở base scale + render lại ở từng scale
    summary.json         số liệu toàn bộ lượt chạy (thời gian, page label, cảnh báo)

Chạy (venv ingest, từ thư mục backend):
    ..\\.venv-ingest\\Scripts\\python.exe -m app.modules.doc_ingest.spike.run_spike \\
        --pdf "<pdf>" --doc f54 --pages 9,11,14,18,40,167-171 --out <dir>
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

from app.modules.doc_ingest.geometry import BBox, overlap_ratio, parse_pages
from app.modules.doc_ingest.parse.docling_runner import build_converter
from app.modules.doc_ingest.parse.pdf_probe import count_path_objects, image_objects, page_label
from app.modules.doc_ingest.spike.render_review import write_index, write_tables_html

LABEL_COLORS = {
    "section_header": "#d62728",
    "title": "#d62728",
    "text": "#1f77b4",
    "list_item": "#17becf",
    "table": "#2ca02c",
    "picture": "#ff7f0e",
    "caption": "#9467bd",
    "page_header": "#7f7f7f",
    "page_footer": "#7f7f7f",
    "footnote": "#8c564b",
    "formula": "#e377c2",
}
CROP_PADDING_PT = 12.0


def item_bbox(item: Any, page_height: float) -> BBox | None:
    if not item.prov:
        return None
    box = item.prov[0].bbox.to_top_left_origin(page_height=page_height)
    return BBox(box.l, box.t, box.r, box.b)


def table_payload(item: Any, doc: Any) -> dict[str, Any]:
    data = item.data
    grid = [[cell.text for cell in row] for row in data.grid]
    header_rows = sorted({
        cell.start_row_offset_idx for cell in data.table_cells if cell.column_header
    })
    spans = [
        {"row": cell.start_row_offset_idx, "col": cell.start_col_offset_idx,
         "row_span": cell.row_span, "col_span": cell.col_span, "text": cell.text}
        for cell in data.table_cells if cell.row_span > 1 or cell.col_span > 1
    ]
    return {
        "num_rows": data.num_rows,
        "num_cols": data.num_cols,
        "column_header_rows": header_rows,
        "merged_cells": spans,
        "grid": grid,
        "html": item.export_to_html(doc=doc),
    }


def save_crop(image: Image.Image, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    return {"path": path.name, "width": image.width, "height": image.height,
            "bytes": path.stat().st_size}


def run_page(converter, pdf_path: Path, pdf: pdfium.PdfDocument, page_no: int,
             out: Path, scales: list[float], base_scale: float) -> dict[str, Any]:
    from docling_core.types.doc import ContentLayer, ImageRefMode, PictureItem, TableItem, TextItem

    started = time.perf_counter()
    result = converter.convert(pdf_path, page_range=(page_no, page_no))
    elapsed_docling = time.perf_counter() - started
    doc = result.document

    doc.save_as_json(out / f"p{page_no:03d}.json", image_mode=ImageRefMode.PLACEHOLDER)

    page_meta = doc.pages[page_no]
    width, height = page_meta.size.width, page_meta.size.height
    page_image = page_meta.image.pil_image.convert("RGB")
    raw_page = pdf[page_no - 1]
    bitmaps = image_objects(raw_page, height)

    items: list[dict[str, Any]] = []
    tables_for_html: list[dict[str, Any]] = []
    overlay = page_image.copy()
    draw = ImageDraw.Draw(overlay)
    picture_dir = out / f"p{page_no:03d}_pictures"
    renders: dict[float, Image.Image] = {}

    # Header/footer nằm ở lớp FURNITURE; mặc định iterate_items chỉ trả BODY nên mất
    # "Page | 11" (nguồn duy nhất của printed_page khi PDF không có /PageLabels).
    layers = {ContentLayer.BODY, ContentLayer.FURNITURE}
    for order, (item, level) in enumerate(
        doc.iterate_items(with_groups=False, included_content_layers=layers)
    ):
        label = str(item.label.value if hasattr(item.label, "value") else item.label)
        bbox = item_bbox(item, height)
        record: dict[str, Any] = {
            "order": order, "level": level, "label": label, "self_ref": item.self_ref,
            "content_layer": str(getattr(item.content_layer, "value", item.content_layer)),
            "bbox": bbox.as_dict() if bbox else None,
        }
        if isinstance(item, TextItem):
            record["text"] = item.text
        if bbox is not None:
            color = LABEL_COLORS.get(label, "#000000")
            draw.rectangle(bbox.scaled(base_scale), outline=color, width=3)
            draw.text((bbox.x0 * base_scale + 3, bbox.y0 * base_scale + 2),
                      f"{order}:{label}", fill=color)

        if isinstance(item, TableItem):
            record["table"] = table_payload(item, doc)
            record["captions"] = item.caption_text(doc)
            crop_name = f"p{page_no:03d}_table{order}.png"
            if bbox is not None:
                save_crop(page_image.crop(bbox.padded(4, width, height).scaled(base_scale)),
                          out / crop_name)
            tables_for_html.append({"order": order, "crop": crop_name, **record["table"],
                                    "captions": record["captions"]})

        if isinstance(item, PictureItem) and bbox is not None:
            pic: dict[str, Any] = {
                "captions": item.caption_text(doc),
                "bitmap_overlap": overlap_ratio(bbox, bitmaps),
                "vector_paths_inside": count_path_objects(raw_page, bbox, height),
                "crops": [],
            }
            docling_image = item.get_image(doc)
            if docling_image is not None:
                pic["crops"].append({"source": "docling", "scale": base_scale,
                                     **save_crop(docling_image, picture_dir / f"e{order}_docling_s{base_scale:g}.png")})
            for scale in scales:
                t0 = time.perf_counter()
                if scale not in renders:
                    renders[scale] = raw_page.render(scale=scale).to_pil().convert("RGB")
                render = renders[scale]
                for tag, box in (("tight", bbox), ("pad", bbox.padded(CROP_PADDING_PT, width, height))):
                    crop = render.crop(box.scaled(scale))
                    pic["crops"].append({
                        "source": f"pdfium_{tag}", "scale": scale,
                        "ms": int((time.perf_counter() - t0) * 1000),
                        **save_crop(crop, picture_dir / f"e{order}_{tag}_s{scale:g}.png"),
                    })
            record["picture"] = pic
        items.append(record)

    overlay.save(out / f"p{page_no:03d}_overlay.png", optimize=True)
    write_tables_html(out / f"p{page_no:03d}_tables.html", page_no, tables_for_html)
    (out / f"p{page_no:03d}_items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    labels: dict[str, int] = {}
    for record in items:
        labels[record["label"]] = labels.get(record["label"], 0) + 1
    return {
        "pdf_page_index": page_no,
        "page_label": page_label(pdf, page_no - 1),
        "footer_texts": [r.get("text") for r in items if r["label"] in {"page_footer", "page_header"}],
        "size_pt": {"width": width, "height": height},
        "docling_seconds": round(elapsed_docling, 2),
        "label_counts": labels,
        "bitmap_objects_on_page": len(bitmaps),
        "tables": [{"order": t["order"], "rows": t["num_rows"], "cols": t["num_cols"],
                    "column_header_rows": t["column_header_rows"],
                    "merged_cells": len(t["merged_cells"])} for t in tables_for_html],
        "pictures": [{"order": r["order"], "bbox": r["bbox"],
                      "bitmap_overlap": r["picture"]["bitmap_overlap"],
                      "vector_paths_inside": r["picture"]["vector_paths_inside"],
                      "captions": r["picture"]["captions"]}
                     for r in items if "picture" in r],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--doc", required=True, help="nhãn ngắn, vd. f54")
    parser.add_argument("--pages", required=True, help="vd. 9,11,14,18,40,167-171 (pdf_page_index, từ 1)")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--base-scale", type=float, default=2.0)
    parser.add_argument("--scales", default="2,3,4")
    parser.add_argument("--table-mode", choices=["accurate", "fast"], default="accurate")
    args = parser.parse_args()

    import docling  # noqa: F401  (chỉ để lấy version)
    from importlib.metadata import version

    out = args.out / args.doc
    out.mkdir(parents=True, exist_ok=True)
    scales = [float(value) for value in args.scales.split(",")]
    pdf = pdfium.PdfDocument(str(args.pdf))

    t0 = time.perf_counter()
    converter = build_converter(args.base_scale, args.table_mode)
    pages = []
    for page_no in parse_pages(args.pages):
        print(f"page {page_no} ...", flush=True)
        pages.append(run_page(converter, args.pdf, pdf, page_no, out, scales, args.base_scale))

    summary = {
        "doc": args.doc,
        "pdf": args.pdf.name,
        "pdf_page_count": len(pdf),
        "page_labels_present": any(page_label(pdf, i) for i in range(len(pdf))),
        "config": {
            "docling": version("docling"), "docling_core": version("docling-core"),
            "pypdfium2": version("pypdfium2"), "do_ocr": False,
            "table_mode": args.table_mode, "base_scale": args.base_scale, "crop_scales": scales,
        },
        "total_seconds": round(time.perf_counter() - t0, 1),
        "pages": pages,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    write_index(out / "index.html", summary)
    print(f"done: {out}")


if __name__ == "__main__":
    main()
