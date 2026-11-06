"""Sinh fixture golden (BL-02) từ output spike: Docling JSON bỏ ảnh + bounds bitmap nhúng.

Test đọc fixture không cần Docling hay PDF. Mỗi trang xuất:

    p{n}.docling.json    DoclingDocument của spike, bỏ `pages[].image` và `pictures[].image`
    p{n}.objects.json    bitmap nhúng (bounds + px) và nét vector lấy từ PDF (T-09, T-10, T-14)
    p{n}.words.json      từ của text layer kèm bbox (V-01/V-02, BL-02b)
    README.md            sha256 PDF, version tool, lệnh sinh lại

Chạy (venv ingest, từ thư mục backend):
    ..\\.venv-ingest\\Scripts\\python.exe -m app.modules.doc_ingest.parse.make_fixture \\
        --pdf "<pdf>" --spike-dir ..\\docs\\ai\\doc_ingest_spike\\output\\f54 \\
        --out tests\\doc_ingest\\fixtures\\docling\\f54
    # chỉ bổ sung words.json / objects.json cho fixture đã có (không sinh lại Docling JSON):
    ..\\.venv-ingest\\Scripts\\python.exe -m app.modules.doc_ingest.parse.make_fixture \\
        --pdf "<pdf>" --words-only --out tests\\doc_ingest\\fixtures\\docling\\f54
    ..\\.venv-ingest\\Scripts\\python.exe -m app.modules.doc_ingest.parse.make_fixture \\
        --pdf "<pdf>" --objects-only --out tests\\doc_ingest\\fixtures\\docling\\f54
"""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from app.modules.doc_ingest.parse.pdf_probe import page_objects, page_words


def strip_images(doc: dict[str, Any]) -> dict[str, Any]:
    """Bỏ ảnh nhúng (chiếm gần hết dung lượng); cấu trúc DoclingDocument giữ nguyên."""
    for page in doc.get("pages", {}).values():
        page["image"] = None
    for picture in doc.get("pictures", []):
        picture["image"] = None
    return doc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def make_page(spike_json: Path, pdf: pdfium.PdfDocument, out: Path) -> int:
    doc = strip_images(json.loads(spike_json.read_text(encoding="utf-8")))
    (page_key, page_meta), = doc["pages"].items()
    page_no = int(page_key)
    height = page_meta["size"]["height"]

    write_json(out / f"p{page_no:03d}.docling.json", doc)
    write_objects(pdf, page_no, page_meta["size"], out)
    write_words(pdf, page_no, height, out)
    return page_no


def write_objects(pdf: pdfium.PdfDocument, page_no: int, size: dict[str, float], out: Path) -> None:
    """Cùng format `raw/p{n}.objects.json` của lần chạy CLI (`pipeline.write_run`)."""
    write_json(out / f"p{page_no:03d}.objects.json",
               {"pdf_page_index": page_no, "size_pt": size, **page_objects(pdf[page_no - 1], size["height"])})


def write_words(pdf: pdfium.PdfDocument, page_no: int, height: float, out: Path) -> None:
    write_json(out / f"p{page_no:03d}.words.json",
               {"pdf_page_index": page_no, "words": page_words(pdf[page_no - 1], height)})


def write_readme(path: Path, pdf_path: Path, pages: list[int]) -> None:
    lines = [
        f"# Fixture golden Docling: {path.parent.name}",
        "",
        "Sinh tự động bởi `app.modules.doc_ingest.parse.make_fixture`; không sửa tay.",
        "Docling JSON lấy từ output spike (cấu hình ghi trong `docs/ai/reports/parsing_spike.md`),",
        "đã bỏ `pages[].image` và `pictures[].image`. `p{n}.words.json`: từ text layer + bbox (pypdfium2).",
        "`p{n}.objects.json`: bitmap nhúng (bounds + px) và nét vector (pypdfium2; đối tượng trong Form XObject",
        "lấy bounds của form).",
        "",
        "| Mục | Giá trị |",
        "|---|---|",
        f"| PDF | `{pdf_path.name}` |",
        f"| sha256 PDF | `{sha256_file(pdf_path)}` |",
        f"| Trang (pdf_page_index) | {', '.join(str(page) for page in pages)} |",
        f"| docling | {version('docling')} |",
        f"| docling-core | {version('docling-core')} |",
        f"| pypdfium2 | {version('pypdfium2')} |",
        "",
        "Sinh lại (venv ingest, từ thư mục `backend`; chạy spike trước để có `--spike-dir`):",
        "",
        "```powershell",
        "..\\.venv-ingest\\Scripts\\python.exe -m app.modules.doc_ingest.parse.make_fixture `",
        f"    --pdf \"<{pdf_path.name}>\" --spike-dir <spike output>\\{path.parent.name} `",
        f"    --out tests\\doc_ingest\\fixtures\\docling\\{path.parent.name}",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--spike-dir", type=Path, help="thư mục output spike của một tài liệu")
    parser.add_argument("--words-only", action="store_true",
                        help="chỉ sinh p{n}.words.json cho các trang đã có trong --out")
    parser.add_argument("--objects-only", action="store_true",
                        help="chỉ sinh p{n}.objects.json cho các trang đã có trong --out")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(args.pdf))
    if args.words_only or args.objects_only:
        pages = []
        for path in sorted(args.out.glob("p*.docling.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            (page_key, page_meta), = doc["pages"].items()
            if args.words_only:
                write_words(pdf, int(page_key), page_meta["size"]["height"], args.out)
            if args.objects_only:
                write_objects(pdf, int(page_key), page_meta["size"], args.out)
            pages.append(int(page_key))
        write_readme(args.out / "README.md", args.pdf, pages)
        print(f"done: words/objects cho {len(pages)} trang -> {args.out}")
        return
    if args.spike_dir is None:
        parser.error("cần --spike-dir (hoặc --words-only / --objects-only)")
    spike_jsons = sorted(
        path for path in args.spike_dir.glob("p*.json")
        if path.stem[1:].isdigit()
    )
    pages = [make_page(path, pdf, args.out) for path in spike_jsons]
    write_readme(args.out / "README.md", args.pdf, pages)
    print(f"done: {len(pages)} trang -> {args.out}")


if __name__ == "__main__":
    main()
