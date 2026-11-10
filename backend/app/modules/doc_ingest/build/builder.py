"""Điều phối bước `build` (BL-16 + kiểm 2b) trên một thư mục chạy có sẵn; ghi các file nháp, không ghi DB.

Đầu ra (contract C2 §2):
- `build/chunks.jsonl`: `DraftChunk`;
- `build/doc_chunks_v1.jsonl`: cùng chunk qua adapter bảng hiện tại (để xem dạng dòng sẽ nạp);
- `build/chunk_quality.json`: CQ, độ phủ, ranh giới, so với chunk viết tay, tổng hợp duyệt, cổng;
- `build/chunk_review.json`: tạo khi chưa có (mọi chunk `pending`), không bao giờ ghi đè;
- `report/chunks.html`: trang duyệt tay;
- `run_report.json`: thêm `chunks` (tóm tắt).
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.modules.doc_ingest.build.assertions import run_checks
from app.modules.doc_ingest.build.chunker import Chunker, ChunkPlan
from app.modules.doc_ingest.build.fields import Assembler, review_index
from app.modules.doc_ingest.build.loader import RunInput, load_run
from app.modules.doc_ingest.build.quality import boundaries, coverage, gate, manual_comparison, review_summary
from app.modules.doc_ingest.eval.labels import ChunkLabels
from app.modules.doc_ingest.export.doc_chunks_v1 import export_rows
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.chunk import ChunkQuality, ChunkReviewEntry, ChunkReviewFile, DraftChunk
from app.modules.doc_ingest.manifest import find_manifest
from app.modules.doc_ingest.schemas.manifest import DocManifest
from app.modules.doc_ingest.schemas.profile import Profile
from app.modules.doc_ingest.schemas.run import RunReport


@dataclass
class BuildResult:
    run: RunInput
    manifest: DocManifest
    plan: ChunkPlan
    chunks: list[DraftChunk]
    quality: ChunkQuality


def build_chunks(run: RunInput, manifest: DocManifest, profile: Profile, labels: ChunkLabels | None = None,
                 compare_csv: Path | None = None, review: ChunkReviewFile | None = None) -> BuildResult:
    chunker = Chunker(profile, run.elements, run.tables)
    plan = chunker.plan()
    assembler = Assembler(run, manifest, profile)
    chunks = assembler.assemble(plan)
    by_element, by_page = review_index(run)
    blocking = {k: {code for code, blocks in v if blocks == "chunk"} for k, v in by_element.items()}
    blocking_pages = {k: {code for code, blocks in v if blocks == "chunk"} for k, v in by_page.items()}
    checks = run_checks(chunks, run.tables, run.elements, blocking, profile.chunking.parent_max, blocking_pages)
    cov = coverage(chunks, chunker, plan)
    bound = boundaries(chunks, labels) if labels is not None else None
    manual = manual_comparison(chunks, compare_csv, manifest.doc_id) if compare_csv is not None else None
    rev = review_summary(chunks, review)
    _, export_errors = export_rows(chunks, profile.vocabulary.product_models)
    items, passed, provisional = gate(checks, cov, bound, rev)
    lengths = sorted(len(c.content) for c in chunks if c.chunk_role != "parent")
    quality = ChunkQuality(
        doc_id=manifest.doc_id, run_dir=str(run.run_dir), chunks=len(chunks),
        by_role=dict(sorted(Counter(c.chunk_role for c in chunks).items())),
        by_type=dict(sorted(Counter(c.chunk_type for c in chunks).items())),
        content_chars={"min": lengths[0], "median": int(statistics.median(lengths)), "max": lengths[-1]}
        if lengths else {},
        token_count_method=assembler.token_method,  # type: ignore[arg-type]
        flags=dict(sorted(Counter(f for c in chunks for f in c.flags).items())),
        blocked_chunks=dict(sorted(Counter(b for c in chunks if c.chunk_role != "parent"
                                           for b in c.review_blockers).items())),
        checks=checks, coverage=cov, boundaries=bound, manual=manual, review=rev, export_errors=export_errors,
        gate=items, gate_passed=passed, provisional=provisional,
    )
    return BuildResult(run, manifest, plan, chunks, quality)


def _load_review(path: Path) -> ChunkReviewFile | None:
    return ChunkReviewFile.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None


def chunk_summary(quality: ChunkQuality) -> dict[str, int]:
    out = {"chunks": quality.chunks, **{f"role_{k}": v for k, v in quality.by_role.items()},
           **{f"type_{k}": v for k, v in quality.by_type.items()},
           "checks_failed": sum(1 for c in quality.checks if c.passed is False)}
    if quality.coverage is not None:
        out["coverage_missing"] = len(quality.coverage.missing)
        out["coverage_duplicated"] = len(quality.coverage.duplicated)
    return out


def write_build(result: BuildResult) -> Path:
    from app.modules.doc_ingest.report.chunks_report import render_chunks

    run_dir = result.run.run_dir
    out = run_dir / "build"
    out.mkdir(parents=True, exist_ok=True)
    (out / "chunks.jsonl").write_text("".join(c.model_dump_json() + "\n" for c in result.chunks), encoding="utf-8")
    rows, _ = export_rows(result.chunks, [])
    (out / "doc_chunks_v1.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (out / "chunk_quality.json").write_text(result.quality.model_dump_json(indent=1) + "\n", encoding="utf-8")
    review_path = out / "chunk_review.json"
    if not review_path.is_file():
        template = ChunkReviewFile(doc_id=result.manifest.doc_id, reviews=[
            ChunkReviewEntry(chunk_key=c.chunk_key, content_hash=c.content_hash) for c in result.chunks])
        review_path.write_text(template.model_dump_json(indent=1) + "\n", encoding="utf-8")
    report_path = run_dir / "report" / "chunks.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_chunks(result), encoding="utf-8")
    report_file = run_dir / "run_report.json"
    report = RunReport.model_validate_json(report_file.read_text(encoding="utf-8"))
    report = report.model_copy(update={"chunks": chunk_summary(result.quality)})
    report_file.write_text(report.model_dump_json(indent=1) + "\n", encoding="utf-8")
    return report_path


def build_run_dir(run_dir: Path, manifest: DocManifest | None = None, labels_path: Path | None = None,
                  compare_csv: Path | None = None) -> BuildResult:
    run = load_run(run_dir)
    manifest = manifest or find_manifest(run.report.doc_id)
    if manifest is None:
        raise ValueError(f"không có manifest cho doc_id '{run.report.doc_id}' (manifests/*.yaml, run_doc_ids)")
    profile = load_profile(run.report.profile_name)
    labels = ChunkLabels.model_validate_json(labels_path.read_text(encoding="utf-8")) if labels_path else None
    review = _load_review(run_dir / "build" / "chunk_review.json")
    return build_chunks(run, manifest, profile, labels, compare_csv, review)
