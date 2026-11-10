"""CLI tool ingest offline.

`run`: PDF (hoặc Docling JSON đã lưu) → chuẩn hóa → thư mục chạy theo contract §1 +
`report/index.html` để xem kết quả từng bước.

Chạy (từ thư mục backend):
    ..\\.venv-ingest\\Scripts\\python.exe -m app.modules.doc_ingest.cli run \\
        --pdf "<file.pdf>" --pages 11,167-171 --doc-id f54 --profile qs_controller
    # chạy lại chuẩn hóa trên Docling JSON đã lưu (không cần Docling, chạy được ở venv chính):
    .\\venv\\Scripts\\python.exe -m app.modules.doc_ingest.cli run \\
        --raw-dir tests\\doc_ingest\\fixtures\\docling\\f54 --doc-id f54

`eval`: chấm một thư mục chạy theo bộ nhãn tay mẫu → `report/eval.json`, `report/eval.html`:
    .\\venv\\Scripts\\python.exe -m app.modules.doc_ingest.cli eval \\
        --run-dir ..\\data\\ingest_runs\\f54\\<run_id> --labels tests\\doc_ingest\\fixtures\\eval\\f54.labels.json

`build`: chunk builder + kiểm chất lượng (BL-16, Bước 2b) trên thư mục chạy có sẵn → `build/*.jsonl`,
`build/chunk_quality.json`, `report/chunks.html` (không ghi DB). `run` gọi `build` ở cuối khi có manifest:
    .\\venv\\Scripts\\python.exe -m app.modules.doc_ingest.cli build --run-dir ..\\data\\ingest_runs\\f54\\<run_id> \\
        --labels tests\\doc_ingest\\fixtures\\eval\\f54.chunks.json

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
from app.modules.doc_ingest.schemas.run import DocumentProfile, RunReport, RunSource

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
    run.add_argument("--no-build", action="store_true", help="không chạy bước build chunk ở cuối")
    ev = sub.add_parser("eval", help="chấm điểm thư mục chạy theo nhãn mẫu")
    ev.add_argument("--run-dir", type=Path, required=True)
    ev.add_argument("--labels", type=Path, required=True, help="file {doc_id}.labels.json")
    bd = sub.add_parser("build", help="chunk builder + kiểm chất lượng trên thư mục chạy có sẵn (không ghi DB)")
    bd.add_argument("--run-dir", type=Path, required=True)
    bd.add_argument("--manifest", type=Path, help="manifests/*.yaml; mặc định: tìm theo doc_id của lần chạy")
    bd.add_argument("--labels", type=Path, help="file {doc_id}.chunks.json: nhãn ranh giới chunk")
    bd.add_argument("--compare-csv", type=Path, help="CSV chunk viết tay để so sánh (vd. doc_chunks_f86.csv)")
    fo = sub.add_parser("figure-ocr", help="OCR nhãn trong hình trên trang có text layer → build/figure_ocr.jsonl "
                                           "(.venv-ingest; chạy tiếp được; chạy lại build để dùng)")
    fo.add_argument("--run-dir", type=Path, required=True)
    fo.add_argument("--limit", type=int, help="chỉ OCR tối đa N hình trong lần chạy này")
    return parser


def cmd_figure_ocr(args: argparse.Namespace) -> None:
    from app.modules.doc_ingest.build.loader import load_run
    from app.modules.doc_ingest.parse.figure_ocr import run_figure_ocr

    run = load_run(args.run_dir)
    count = 0
    for element_id, labels, seconds in run_figure_ocr(args.run_dir, run.elements, run.ocr_pages, args.limit):
        count += 1
        print(f"  {element_id}: {labels} nhãn, {seconds:.1f}s", flush=True)
    print(f"OCR hình: {count} hình mới → {args.run_dir / 'build' / 'figure_ocr.jsonl'}")


def cmd_build(args: argparse.Namespace) -> Path:
    from app.modules.doc_ingest.build.builder import build_run_dir, write_build
    from app.modules.doc_ingest.manifest import load_manifest

    manifest = load_manifest(args.manifest) if args.manifest else None
    result = build_run_dir(args.run_dir, manifest, args.labels, args.compare_csv)
    path = write_build(result)
    q = result.quality
    failed = [c.check_id for c in q.checks if c.passed is False]
    verdict = {True: "ĐẠT", False: "KHÔNG ĐẠT", None: "chưa đủ dữ liệu"}[q.gate_passed]
    print(f"Chunk: {q.chunks} ({', '.join(f'{k} {v}' for k, v in q.by_role.items())}); "
          f"CQ không đạt: {', '.join(failed) or 'không'}; cổng 2b: {verdict}{' (tạm)' if q.provisional else ''}")
    return path


def cmd_eval(args: argparse.Namespace) -> Path:
    from app.modules.doc_ingest.eval.render import render_eval
    from app.modules.doc_ingest.eval.score import load_labels, score_run

    report = score_run(args.run_dir, load_labels(args.labels))
    out = args.run_dir / "report"
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval.json").write_text(report.model_dump_json(indent=1) + "\n", encoding="utf-8")
    (out / "eval.html").write_text(render_eval(report), encoding="utf-8")
    verdict = {True: "ĐẠT", False: "KHÔNG ĐẠT", None: "không đủ dữ liệu"}[report.gate_passed]
    print(f"Cổng đánh giá: {verdict}{' (tạm: nhãn chưa xác nhận)' if report.provisional else ''}")
    return out / "eval.html"


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
    if not args.no_build:
        report = _build_after_run(run_dir, report)
    report_path = run_dir / "report" / "index.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(result, report, images), encoding="utf-8")
    return report_path


def _build_after_run(run_dir: Path, report: RunReport) -> RunReport:
    """`run` gọi bước build ở cuối khi tìm được manifest; không có manifest thì bỏ qua và báo."""
    from app.modules.doc_ingest.build.builder import build_run_dir, chunk_summary, write_build
    from app.modules.doc_ingest.manifest import find_manifest

    if find_manifest(report.doc_id) is None:
        print(f"  build bỏ qua: không có manifest cho doc_id '{report.doc_id}'", flush=True)
        return report
    result = build_run_dir(run_dir)
    write_build(result)
    print(f"  build: {result.quality.chunks} chunk → report/chunks.html", flush=True)
    return report.model_copy(update={"chunks": chunk_summary(result.quality)})


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
    elif args.command == "eval":
        print(f"Báo cáo: {cmd_eval(args)}")
    elif args.command == "build":
        print(f"Báo cáo: {cmd_build(args)}")
    elif args.command == "figure-ocr":
        cmd_figure_ocr(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
