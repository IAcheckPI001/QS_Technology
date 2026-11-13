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
    # build sang run mới mà giữ verdict đã duyệt (chép theo content_hash + section_path):
    #   ... build --run-dir <run mới> --carry-review <run cũ>\\build\\chunk_review.json \\
    #       --carry-chunks <run cũ>\\build\\chunks.jsonl

`enrich`: Bước 3, làm giàu tiếng Việt cho chunk lá bằng LLM (venv chính) → `build/enrichment.jsonl`; chạy lại
`build` để đưa vào `embed_text`:
    .\\venv\\Scripts\\python.exe -m app.modules.doc_ingest.cli enrich --run-dir <run> --sample 20 --dry-run

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
    bd.add_argument("--carry-review", type=Path,
                    help="chunk_review.json của lần build trước: chép verdict theo content_hash + section_path "
                         "khi tạo chunk_review.json mới (cần --carry-chunks)")
    bd.add_argument("--carry-chunks", type=Path, help="chunks.jsonl cùng lần build với --carry-review")
    fo = sub.add_parser("figure-ocr", help="OCR nhãn trong hình trên trang có text layer → build/figure_ocr.jsonl "
                                           "(.venv-ingest; chạy tiếp được; chạy lại build để dùng)")
    fo.add_argument("--run-dir", type=Path, required=True)
    fo.add_argument("--limit", type=int, help="chỉ OCR tối đa N hình trong lần chạy này")
    en = sub.add_parser("enrich", help="Bước 3: làm giàu tiếng Việt cho chunk lá bằng LLM → build/enrichment.jsonl "
                                       "(venv chính; cần cổng 2b đạt; chạy lại build để dùng)")
    en.add_argument("--run-dir", type=Path, required=True)
    en.add_argument("--limit", type=int, help="tối đa N chunk trong lần chạy này (theo thứ tự đọc)")
    en.add_argument("--sample", type=int, help="thí điểm: N chunk chọn phân tầng theo loại chunk")
    en.add_argument("--dry-run", action="store_true", help="không gọi API: chỉ in số chunk và ước tính chi phí")
    en.add_argument("--only-enriched", action="store_true",
                    help="chỉ làm lại chunk đã có bản ghi phiên bản cũ (so sánh prompt/thuật ngữ mới)")
    en.add_argument("--model", help="mặc định: env OPENAI_MODEL (hoặc backend/.env), không có thì gpt-4o-mini")
    en.add_argument("--input-price", type=float, help="USD / 1M token vào (mặc định: giá gpt-4o-mini)")
    en.add_argument("--output-price", type=float, help="USD / 1M token ra (mặc định: giá gpt-4o-mini)")
    es = sub.add_parser("enrich-sample", help="cổng 2c: chọn mẫu chunk lá đã làm giàu để duyệt tay "
                                              "(đánh dấu enrichment_verdict=pending trong chunk_review.json)")
    es.add_argument("--run-dir", type=Path, required=True)
    es.add_argument("--size", type=int, default=30)
    es.add_argument("--include-pilot", action="store_true", help="không bỏ chunk thí điểm (đã làm giàu nhiều phiên bản)")
    ea = sub.add_parser("enrich-approve", help="cổng 2c đạt → ghi build/enrichment_approval.json (chạy lại build)")
    ea.add_argument("--run-dir", type=Path, required=True)
    ea.add_argument("--reviewer", required=True)
    return parser


def cmd_enrich_sample(args: argparse.Namespace) -> None:
    import json

    from app.modules.doc_ingest.build.loader import ENRICHMENT_FILE, enrichment_key, load_enrichment
    from app.modules.doc_ingest.enrich import review as rv
    from app.modules.doc_ingest.enrich.runner import load_chunks
    from app.modules.doc_ingest.schemas.chunk import ChunkReviewFile

    records = load_enrichment(args.run_dir)
    if not records:
        raise SystemExit("chưa có build/enrichment.jsonl: chạy enrich trước")
    versions: dict[tuple[str, tuple[str, ...]], set[str]] = {}
    for line in (args.run_dir / "build" / ENRICHMENT_FILE).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            key = enrichment_key(row["content_hash"], row.get("section_path", []))
            versions.setdefault(key, set()).add(row["prompt_version"])
    pilot = frozenset() if args.include_pilot else frozenset(h for h, v in versions.items() if len(v) > 1)
    chunks = load_chunks(args.run_dir)
    sample = rv.select_sample(chunks, records, args.size, pilot)
    path = args.run_dir / "build" / "chunk_review.json"
    review = ChunkReviewFile.model_validate_json(path.read_text(encoding="utf-8"))
    marked = rv.mark_sample(review, sample, records)
    path.write_text(review.model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(f"Mẫu 2c: {len(sample)} chunk ({marked} mới đánh dấu pending; bỏ {len(pilot)} nội dung thí điểm)")
    for c in sample:
        checks = records[enrichment_key(c.content_hash, c.section_path)].checks
        print(f"  {c.chunk_key} [{c.chunk_type}] {(c.section_path or [c.section_title])[-1][:60]}"
              f"{' — kiểm: ' + ', '.join(checks) if checks else ''}")
    print("Ghi verdict vào chunk_review.json (enrichment_verdict ok/fix, enrichment_note, enrichment_severe) rồi build.")


def cmd_enrich_approve(args: argparse.Namespace) -> None:
    from datetime import datetime

    from app.modules.doc_ingest.build.loader import APPROVAL_FILE
    from app.modules.doc_ingest.schemas.chunk import ChunkQuality, EnrichmentApproval

    quality = ChunkQuality.model_validate_json(
        (args.run_dir / "build" / "chunk_quality.json").read_text(encoding="utf-8"))
    e = quality.enrichment
    if e.passed is not True:
        raise SystemExit(f"cổng 2c chưa đạt (tự động: {e.auto_passed}; mẫu {e.sample_ok}/{e.sample} ok, "
                         f"{len(e.severe)} lỗi nặng, {e.sample_pending} chờ): chạy build sau khi ghi verdict")
    if len(e.versions) != 1:
        raise SystemExit(f"chunk lá đang ở nhiều phiên bản làm giàu {e.versions}: chạy enrich cho đồng nhất trước")
    version = next(iter(e.versions))
    approval = EnrichmentApproval(version=version, approved_at=datetime.now().isoformat(timespec="seconds"),
                                  reviewer=args.reviewer, sample=e.sample, sample_ok=e.sample_ok)
    (args.run_dir / "build" / APPROVAL_FILE).write_text(approval.model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(f"Duyệt làm giàu phiên bản {version} ({e.sample_ok}/{e.sample} mẫu ok). Chạy lại build → approved.")


def cmd_enrich(args: argparse.Namespace) -> None:
    from app.modules.doc_ingest.build.chunker import estimate_tokens
    from app.modules.doc_ingest.build.fields import token_counter
    from app.modules.doc_ingest.enrich import env, runner

    try:
        runner.require_gate(args.run_dir)
    except runner.GateNotPassed as exc:
        raise SystemExit(f"enrich dừng: {exc}") from exc
    model = args.model or env.openai_model()
    if model != env.DEFAULT_MODEL and (args.input_price is None or args.output_price is None):
        raise SystemExit(f"model {model}: truyền --input-price và --output-price (chỉ có sẵn giá {env.DEFAULT_MODEL})")
    price_in = args.input_price if args.input_price is not None else env.GPT4O_MINI_INPUT_USD
    price_out = args.output_price if args.output_price is not None else env.GPT4O_MINI_OUTPUT_USD
    from app.modules.doc_ingest.enrich.prompt import prompt_version, system_prompt
    from app.modules.doc_ingest.schemas.run import RunReport

    report = RunReport.model_validate_json((args.run_dir / "run_report.json").read_text(encoding="utf-8"))
    glossary = load_profile(report.profile_name).glossary
    version, system = prompt_version(glossary), system_prompt(glossary)
    chunks = runner.pending_leaves(runner.load_chunks(args.run_dir), args.run_dir, version, args.only_enriched)
    if args.sample:
        chunks = runner.stratified(chunks, args.sample)
    if args.limit:
        chunks = chunks[: args.limit]
    counter, method = token_counter()
    est_in, est_out = runner.estimate(chunks, counter or estimate_tokens, system)
    types = ", ".join(f"{t} {n}" for t, n in sorted(
        {t: sum(1 for c in chunks if c.chunk_type == t) for t in {c.chunk_type for c in chunks}}.items()))
    print(f"Chunk lá cần làm giàu: {len(chunks)} ({types or '—'}); model {model}; prompt {version} "
          f"({len(glossary)} thuật ngữ)")
    print(f"Ước tính: {est_in:,} token vào + {est_out:,} token ra ≈ "
          f"{runner.cost_usd(est_in, est_out, price_in, price_out):.4f} USD"
          f"{'' if method == 'tiktoken' else ' (token ước lượng ký tự/4)'}")
    if args.dry_run or not chunks:
        return
    from app.modules.doc_ingest.enrich.client import OpenAIEnricher

    enricher = OpenAIEnricher(model, env.openai_api_key(), system)
    stats = runner.RunStats()
    keep_terms = [t.en for t in glossary if not t.vi]
    for chunk, record, error, stats in runner.run_enrichment(args.run_dir, chunks, enricher, version=version,
                                                             keep_terms=keep_terms):
        status = "lỗi: " + error if error else ("ok" + (f" (kiểm: {', '.join(record.checks)})"
                                                         if record and record.checks else ""))
        print(f"  {chunk.chunk_key} [{chunk.chunk_type}]: {status}", flush=True)
    cost = runner.cost_usd(stats.input_tokens, stats.output_tokens, price_in, price_out)
    print(f"Xong: {stats.done} ghi, {len(stats.failed)} lỗi; thật: {stats.input_tokens:,} vào + "
          f"{stats.output_tokens:,} ra ≈ {cost:.4f} USD → {args.run_dir / 'build' / 'enrichment.jsonl'}")
    print("Chạy lại build để đưa làm giàu vào embed_text.")


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
    from app.modules.doc_ingest.build.builder import build_run_dir, load_carry, write_build
    from app.modules.doc_ingest.manifest import load_manifest

    if (args.carry_review is None) != (args.carry_chunks is None):
        raise SystemExit("--carry-review và --carry-chunks phải đi cùng nhau")
    carry = load_carry(args.carry_review, args.carry_chunks) if args.carry_review else None
    manifest = load_manifest(args.manifest) if args.manifest else None
    result = build_run_dir(args.run_dir, manifest, args.labels, args.compare_csv)
    path = write_build(result, carry)
    q = result.quality
    failed = [c.check_id for c in q.checks if c.passed is False]
    verdict = {True: "ĐẠT", False: "KHÔNG ĐẠT", None: "chưa đủ dữ liệu"}[q.gate_passed]
    if q.token_count_method == "unavailable":
        print("  CẢNH BÁO: venv này không có tiktoken; token chỉ là ước lượng (ký tự/4), `token_count` để trống, "
              "`embed_truncated` và CQ-11 không đáng tin. Build lại bằng venv chính trước khi duyệt.", flush=True)
    print(f"Chunk: {q.chunks} ({', '.join(f'{k} {v}' for k, v in q.by_role.items())}); "
          f"CQ không đạt: {', '.join(failed) or 'không'}; cổng 2b: {verdict}{' (tạm)' if q.provisional else ''}")
    e = q.enrichment
    if e.enriched:
        state = {True: "ĐẠT", False: "KHÔNG ĐẠT", None: "chưa đủ"}
        print(f"Làm giàu (2c): tự động (CQ-13) {state[e.auto_passed]}: {e.enriched}/{e.leaves} chunk lá, mã lạ "
              f"{len(e.code_mismatch)}, bớt câu hỏi/từ khóa {len(e.trimmed)}, content bị cắt {len(e.truncated)}; "
              f"mẫu {e.sample_ok}/{e.sample} ok, {len(e.sample_fix)} fix ({len(e.severe)} nặng), {e.sample_pending} "
              f"chờ; cổng 2c {state[e.passed]}"
              f"{f'; đã duyệt phiên bản {e.approved_version}' if e.approved_version else ''}")
    status = ", ".join(f"{k} {v}" for k, v in q.review_status_v2.items())
    print(f"doc_chunks_v2: {status or '0 dòng'}; lỗi ràng buộc {len(q.export_errors_v2)}"
          f"{': ' + '; '.join(q.export_errors_v2[:3]) if q.export_errors_v2 else ''}")
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
    elif args.command == "enrich":
        cmd_enrich(args)
    elif args.command == "enrich-sample":
        cmd_enrich_sample(args)
    elif args.command == "enrich-approve":
        cmd_enrich_approve(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
