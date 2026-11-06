"""CLI tool ingest offline.

`run`: PDF (hoặc Docling JSON đã lưu) → chuẩn hóa → thư mục chạy theo contract §1 +
`report/index.html` để xem kết quả từng bước.

Chạy (từ thư mục backend):
    ..\\.venv-ingest\\Scripts\\python.exe -m app.modules.doc_ingest.cli run \\
        --pdf "<file.pdf>" --pages 11,167-171 --doc-id f54 --profile qs_controller
    # chạy lại chuẩn hóa trên Docling JSON đã lưu (không cần Docling, chạy được ở venv chính):
    .\\venv\\Scripts\\python.exe -m app.modules.doc_ingest.cli run \\
        --raw-dir tests\\doc_ingest\\fixtures\\docling\\f54 --doc-id f54

Docling chỉ được import (qua `parse/docling_runner`) khi cần parse hoặc render PDF.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from app.modules.doc_ingest.geometry import parse_pages
from app.modules.doc_ingest.pipeline import (
    apply_rendered, crop_requests, load_objects, load_raw_dir, load_s0, load_words, run_normalization, write_run,
)
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.report.html_report import render_report
from app.modules.doc_ingest.s0 import build_profile, ocr_pages
from app.modules.doc_ingest.schemas.run import DocumentProfile, RunSource

DEFAULT_OUT = Path(__file__).resolve().parents[4] / "data" / "ingest_runs"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="doc_ingest", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="parse + chuẩn hóa + báo cáo HTML")
    run.add_argument("--pdf", type=Path, help="PDF nguồn (parse bằng Docling; kèm --raw-dir thì chỉ để render ảnh)")
    run.add_argument("--raw-dir", type=Path, help="thư mục p{n}.docling.json đã lưu (fixture hoặc raw/ của lần chạy cũ)")
    run.add_argument("--pages", help="vd. 11,167-171 (pdf_page_index, từ 1); bỏ trống = mọi trang")
    run.add_argument("--doc-id", required=True, help="nhãn ngắn của tài liệu, vd. f54")
    run.add_argument("--profile", default="default", help="tên profile trong profiles/ hoặc đường dẫn .yaml")
    run.add_argument("--table-mode", choices=["accurate", "fast"], default="accurate")
    run.add_argument("--ocr", choices=["auto", "off", "force"], default="auto",
                     help="auto: OCR trang S0 báo không có/hỏng text layer; off: không OCR; force: OCR mọi trang")
    run.add_argument("--out", type=Path, default=DEFAULT_OUT)
    run.add_argument("--run-id", help="mặc định: thời điểm chạy YYYYmmdd-HHMMSS")
    return parser


def cmd_run(args: argparse.Namespace) -> Path:
    if args.pdf is None and args.raw_dir is None:
        raise SystemExit("cần --pdf hoặc --raw-dir")
    pages = parse_pages(args.pages) if args.pages else None
    profile = load_profile(args.profile)
    timings: dict[str, float] = {}
    versions: dict[str, str] = {}
    source = RunSource()
    s0: DocumentProfile | None = None

    if args.pdf is not None:
        from app.modules.doc_ingest.parse import docling_runner as runner

        total = runner.page_count(args.pdf)
        source = RunSource(pdf_name=args.pdf.name, pdf_sha256=runner.sha256_file(args.pdf), total_pages=total)
        versions = runner.tool_versions()
        if pages is None:
            pages = list(range(1, total + 1))
        if any(p < 1 or p > total for p in pages):
            raise SystemExit(f"trang ngoài phạm vi 1..{total}")
        from app.modules.doc_ingest.parse.profile_probe import measure_pages

        started = time.perf_counter()
        # Chạy từ raw đã parse: không parse lại nên không OCR được; S0 chỉ để gắn cờ.
        mode = "off" if args.raw_dir is not None else args.ocr
        s0 = build_profile(measure_pages(args.pdf, pages), profile.thresholds, mode)
        timings["s0"] = round(time.perf_counter() - started, 2)

    if args.raw_dir is not None:
        docs = load_raw_dir(args.raw_dir, pages)
        source = source.model_copy(update={"raw_dir": str(args.raw_dir)})
        saved = load_s0(args.raw_dir)
        if saved is not None:
            s0 = saved
    else:
        docs = []
        started = time.perf_counter()
        ocr = ocr_pages(s0) if s0 is not None else set()
        page_no = 0
        try:
            for page_no, doc, seconds in runner.convert_pages(args.pdf, pages or [], args.table_mode, ocr):
                tag = " (OCR)" if page_no in ocr else ""
                print(f"  docling trang {page_no}{tag}: {seconds:.1f}s", flush=True)
                docs.append(doc)
        except Exception as exc:  # Docling/OCR lỗi: dừng rõ ràng, không chạy tiếp thiếu OCR
            raise SystemExit(f"Docling lỗi sau trang {page_no} (OCR các trang {sorted(ocr)}): {exc}") from exc
        timings["parse"] = round(time.perf_counter() - started, 2)
    if not docs:
        raise SystemExit("không có trang nào để chạy")

    doc_pages = sorted(min(int(no) for no in d["pages"]) for d in docs)
    if s0 is not None:
        s0 = s0.model_copy(update={"pages": [p for p in s0.pages if p.page in doc_pages]})
    if args.pdf is not None:
        words = runner.extract_words(args.pdf, doc_pages)
        objects = runner.extract_objects(args.pdf, doc_pages)
    else:
        words = load_words(args.raw_dir, doc_pages)
        objects = load_objects(args.raw_dir, doc_pages)
        if not words:
            print("  V-01 không chạy: thư mục raw không có p{n}.words.json", flush=True)
        if not objects:
            print("  T-09/T-10 không chạy, T-14 chỉ dùng bbox Docling: raw không có p{n}.objects.json", flush=True)

    created_at = datetime.now()
    run_id = args.run_id or created_at.strftime("%Y%m%d-%H%M%S")
    run_dir = args.out / args.doc_id / run_id
    started = time.perf_counter()
    result = run_normalization(docs, args.doc_id, profile, words, s0, objects)
    timings["normalize"] = round(time.perf_counter() - started, 3)

    images: dict[int, str] = {}
    if args.pdf is not None:
        names = runner.render_pages(args.pdf, result.pages, run_dir / "pages")
        images = {page: f"../pages/{name}" for page, name in names.items()}
        started = time.perf_counter()
        apply_rendered(result, runner.render_crops(args.pdf, crop_requests(result), run_dir))
        timings["render_crops"] = round(time.perf_counter() - started, 2)

    report = write_run(run_dir, result, doc_id=args.doc_id, run_id=run_id, created_at=created_at,
                       source=source, timings=timings, versions=versions)
    report_path = run_dir / "report" / "index.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(result, report, images), encoding="utf-8")
    return report_path


def _utf8_console() -> None:
    """Console Windows bị pipe mặc định cp1252, không in được tiếng Việt."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def main(argv: Sequence[str] | None = None) -> int:
    _utf8_console()
    args = _parser().parse_args(argv)
    if args.command == "run":
        path = cmd_run(args)
        print(f"Báo cáo: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
