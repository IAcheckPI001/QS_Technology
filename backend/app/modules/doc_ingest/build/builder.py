"""Điều phối bước `build` (BL-16 + kiểm 2b) trên một thư mục chạy có sẵn; ghi các file nháp, không ghi DB.

Đầu ra (contract C2 §2):
- `build/chunks.jsonl`: `DraftChunk`;
- `build/doc_chunks_v1.jsonl`: cùng chunk qua adapter bảng cũ `doc_chunks`;
- `build/doc_chunks_v2.jsonl`: dòng bảng `doc_chunks_v2` (D-009) — đầu vào của loader `chunking_loader`;
- `build/chunk_quality.json`: CQ, độ phủ, ranh giới, so với chunk viết tay, tổng hợp duyệt, cổng;
- `build/chunk_review.json`: tạo khi chưa có (mọi chunk `pending`, hoặc chép verdict của lần build trước theo
  `content_hash` + `section_path` khi có `CarrySource`), không bao giờ ghi đè;
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
from app.modules.doc_ingest.export.doc_chunks_v2 import ApprovalContext
from app.modules.doc_ingest.export.doc_chunks_v2 import export_rows as export_rows_v2
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.chunk import (
    ChunkQuality, ChunkReviewEntry, ChunkReviewFile, DraftChunk, EnrichmentSummary,
)
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
    assembler = Assembler(run, manifest, profile)
    chunker = Chunker(profile, run.elements, run.tables, assembler.counter, assembler.head_tokens,
                      manifest.exclude_pages, manifest.exclude_sections)
    plan = chunker.plan()
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
    # Không có tiktoken: token chỉ là ước lượng, `embed_truncated` và CQ-11 không đáng tin → kết quả là tạm.
    provisional = provisional or assembler.token_method == "unavailable"
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
        enrichment=enrichment_summary(chunks, review, run),
    )
    return BuildResult(run, manifest, plan, chunks, quality)


def enrichment_summary(chunks: list[DraftChunk], review: ChunkReviewFile | None = None,
                       run: RunInput | None = None) -> EnrichmentSummary:
    """Cổng 2c. Tự động (CQ-13): mọi chunk lá đã làm giàu, 0 mã kỹ thuật lạ trong tóm tắt/câu hỏi, 0 lá có làm giàu
    mà `content` vẫn bị cắt khỏi `embed_text`. Mẫu duyệt tay: 0 lỗi nặng, ≥ 90% `ok`, không còn mẫu chờ
    (`enrich/review.py`). Chưa làm giàu chunk nào → `None`."""
    from app.modules.doc_ingest.enrich.review import gate_2c, leaf_versions, sample_counts

    records = run.enrichment if run is not None else {}
    leaves = [c for c in chunks if c.chunk_role != "parent"]
    enriched = [c for c in leaves if c.enrichment_status != "none"]
    mismatch = [c.chunk_key for c in enriched if "enrich_code_mismatch" in c.flags]
    trimmed = [c.chunk_key for c in enriched if "enrich_trimmed" in c.flags]
    truncated = [c.chunk_key for c in enriched if "embed_truncated" in c.flags]
    auto = None if not enriched else (len(enriched) == len(leaves) and not mismatch and not truncated)
    counts = sample_counts(chunks, review, records)
    return EnrichmentSummary(
        leaves=len(leaves), enriched=len(enriched), code_mismatch=mismatch, trimmed=trimmed, truncated=truncated,
        versions=leaf_versions(chunks, records), auto_passed=auto, sample=counts.sample, sample_ok=counts.ok,
        sample_fix=counts.fix, sample_pending=counts.pending, severe=counts.severe,
        approved_version=run.approval.version if run is not None and run.approval is not None else None,
        passed=gate_2c(auto, counts))


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


@dataclass(frozen=True)
class CarrySource:
    """Bản duyệt của một lần build trước: `chunk_review.json` + `chunks.jsonl` cùng lần build đó."""

    review: ChunkReviewFile
    chunks: list[DraftChunk]


def load_carry(review_path: Path, chunks_path: Path) -> CarrySource:
    review = ChunkReviewFile.model_validate_json(review_path.read_text(encoding="utf-8"))
    chunks = [DraftChunk.model_validate_json(line) for line in chunks_path.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    return CarrySource(review=review, chunks=chunks)


def carry_review(chunks: list[DraftChunk], doc_id: str, carry: CarrySource | None) -> tuple[ChunkReviewFile, int]:
    """Template duyệt cho bộ chunk mới. `chunk_key` đánh số theo thứ tự nên dịch khi số chunk đổi; verdict cũ
    được chép theo (`content_hash`, `section_path`), không theo key. Chunk mới hoặc đã đổi nội dung → `pending`.
    Trả về (file, số mục chép được)."""
    pool: dict[tuple[str, tuple[str, ...]], list[ChunkReviewEntry]] = {}
    if carry is not None:
        old = {c.chunk_key: c for c in carry.chunks}
        for entry in carry.review.reviews:
            chunk = old.get(entry.chunk_key)
            if entry.verdict == "pending" or chunk is None or chunk.content_hash != entry.content_hash:
                continue   # chưa duyệt, hoặc verdict đã stale ở lần build cũ
            pool.setdefault((chunk.content_hash, tuple(chunk.section_path)), []).append(entry)
    reviews, carried = [], 0
    for c in chunks:
        queue = pool.get((c.content_hash, tuple(c.section_path)))
        if queue:
            prev = queue.pop(0)
            reviews.append(ChunkReviewEntry(chunk_key=c.chunk_key, content_hash=c.content_hash,
                                            verdict=prev.verdict, note=prev.note, reviewer=prev.reviewer,
                                            enrichment_verdict=prev.enrichment_verdict,
                                            enrichment_note=prev.enrichment_note,
                                            enrichment_version=prev.enrichment_version,
                                            enrichment_severe=prev.enrichment_severe))
            carried += 1
        else:
            reviews.append(ChunkReviewEntry(chunk_key=c.chunk_key, content_hash=c.content_hash))
    return ChunkReviewFile(doc_id=doc_id, reviews=reviews), carried


def write_build(result: BuildResult, carry: CarrySource | None = None) -> Path:
    """`carry`: chép verdict của lần build trước khi tạo `chunk_review.json` mới; file đã có thì không ghi đè."""
    from app.modules.doc_ingest.report.chunks_report import render_chunks

    run_dir = result.run.run_dir
    out = run_dir / "build"
    out.mkdir(parents=True, exist_ok=True)
    (out / "chunks.jsonl").write_text("".join(c.model_dump_json() + "\n" for c in result.chunks), encoding="utf-8")
    rows, _ = export_rows(result.chunks, [])
    (out / "doc_chunks_v1.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    review_path = out / "chunk_review.json"
    if not review_path.is_file():
        template, carried = carry_review(result.chunks, result.manifest.doc_id, carry)
        review_path.write_text(template.model_dump_json(indent=1) + "\n", encoding="utf-8")
        if carry is not None:
            print(f"  chép verdict: {carried}/{len(result.chunks)} chunk; còn lại pending", flush=True)
            # Tổng hợp duyệt trong chunk_quality phải tính trên file vừa tạo.
            result.quality.review = review_summary(result.chunks, template)
            items, passed, provisional = gate(result.quality.checks, result.quality.coverage,
                                              result.quality.boundaries, result.quality.review)
            result.quality.gate, result.quality.gate_passed, result.quality.provisional = items, passed, provisional
            result.quality.enrichment = enrichment_summary(result.chunks, template, result.run)
    elif carry is not None:
        print(f"  --carry-review bỏ qua: {review_path} đã có (không ghi đè)", flush=True)
    write_rows_v2(result, _load_review(review_path))
    (out / "chunk_quality.json").write_text(result.quality.model_dump_json(indent=1) + "\n", encoding="utf-8")
    report_path = run_dir / "report" / "chunks.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_chunks(result), encoding="utf-8")
    report_file = run_dir / "run_report.json"
    report = RunReport.model_validate_json(report_file.read_text(encoding="utf-8"))
    report = report.model_copy(update={"chunks": chunk_summary(result.quality)})
    report_file.write_text(report.model_dump_json(indent=1) + "\n", encoding="utf-8")
    return report_path


def source_run(run_dir: Path) -> str:
    """Định danh run để truy ngược từ dòng DB: hai cấp cuối của thư mục chạy (vd. `f54/eval-l`)."""
    return "/".join(run_dir.resolve().parts[-2:])


def write_rows_v2(result: BuildResult, review: ChunkReviewFile | None) -> Path:
    """`build/doc_chunks_v2.jsonl` (D-009). Cần cổng đã tính trên file duyệt cuối cùng (gọi sau khi tạo/đọc
    `chunk_review.json`); ghi lỗi và số dòng theo `review_status` vào `result.quality`."""
    ctx = ApprovalContext.from_build(result.quality, review)
    rows, errors = export_rows_v2(result.chunks, ctx, source_run(result.run.run_dir))
    path = result.run.run_dir / "build" / "doc_chunks_v2.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    result.quality.export_errors_v2 = errors
    result.quality.review_status_v2 = dict(sorted(Counter(r["review_status"] for r in rows).items()))
    return path


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
