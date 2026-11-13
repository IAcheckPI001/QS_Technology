"""Đọc thư mục chạy đã chuẩn hóa (output giai đoạn 1) cho chunk builder. Không parse lại PDF."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.modules.doc_ingest.schemas.chunk import EnrichmentApproval, EnrichmentRecord
from app.modules.doc_ingest.schemas.normalized import LogicalTable, NormalizedElement, ReviewItem
from app.modules.doc_ingest.schemas.run import RunReport

ENRICHMENT_FILE = "enrichment.jsonl"
APPROVAL_FILE = "enrichment_approval.json"


@dataclass
class RunInput:
    run_dir: Path
    report: RunReport
    elements: list[NormalizedElement]
    tables: dict[str, LogicalTable]
    review: list[ReviewItem]
    ocr_pages: set[int] = field(default_factory=set)
    figure_ocr: dict[str, list[str]] = field(default_factory=dict)   # element_id -> nhãn OCR trên vùng crop
    # (content_hash, section_path) -> làm giàu Bước 3
    enrichment: dict[tuple[str, tuple[str, ...]], EnrichmentRecord] = field(default_factory=dict)
    approval: EnrichmentApproval | None = None                               # phiên bản làm giàu đã qua cổng 2c


def load_approval(run_dir: Path) -> EnrichmentApproval | None:
    path = run_dir / "build" / APPROVAL_FILE
    return EnrichmentApproval.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None


EnrichKey = tuple[str, tuple[str, ...]]


def enrichment_key(content_hash: str, section_path: Sequence[str]) -> EnrichKey:
    """Khóa làm giàu: cùng nội dung ở mục khác nhau làm giàu riêng (nghĩa phụ thuộc mục)."""
    return content_hash, tuple(section_path)


def load_enrichment(run_dir: Path) -> dict[EnrichKey, EnrichmentRecord]:
    """`build/enrichment.jsonl` (append-only): bản ghi sau cùng của mỗi (`content_hash`, `section_path`) thắng."""
    out: dict[EnrichKey, EnrichmentRecord] = {}
    for row in _jsonl(run_dir / "build" / ENRICHMENT_FILE):
        record = EnrichmentRecord.model_validate(row)
        out[enrichment_key(record.content_hash, record.section_path)] = record
    return out


def _jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_run(run_dir: Path) -> RunInput:
    report = RunReport.model_validate_json((run_dir / "run_report.json").read_text(encoding="utf-8"))
    normalized = run_dir / "normalized"
    elements = [NormalizedElement.model_validate(row) for row in _jsonl(normalized / "elements.jsonl")]
    elements.sort(key=lambda e: e.reading_order)
    tables = {t.logical_table_id: t for t in (LogicalTable.model_validate(row)
                                              for row in _jsonl(normalized / "tables.jsonl"))}
    review = [ReviewItem.model_validate(row) for row in _jsonl(normalized / "review_queue.jsonl")]
    ocr = {p.page for p in report.s0.pages if p.ocr_applied} if report.s0 is not None else set()
    figure_ocr: dict[str, list[str]] = {}
    for row in _jsonl(run_dir / "build" / "figure_ocr.jsonl"):
        figure_ocr[str(row["element_id"])] = [str(t) for t in row.get("labels", [])]   # type: ignore[union-attr]
    return RunInput(run_dir=run_dir, report=report, elements=elements, tables=tables, review=review,
                    ocr_pages=ocr, figure_ocr=figure_ocr, enrichment=load_enrichment(run_dir),
                    approval=load_approval(run_dir))
