"""Đọc thư mục chạy đã chuẩn hóa (output giai đoạn 1) cho chunk builder. Không parse lại PDF."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.modules.doc_ingest.schemas.normalized import LogicalTable, NormalizedElement, ReviewItem
from app.modules.doc_ingest.schemas.run import RunReport


@dataclass
class RunInput:
    run_dir: Path
    report: RunReport
    elements: list[NormalizedElement]
    tables: dict[str, LogicalTable]
    review: list[ReviewItem]
    ocr_pages: set[int] = field(default_factory=set)
    figure_ocr: dict[str, list[str]] = field(default_factory=dict)   # element_id -> nhãn OCR trên vùng crop


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
                    ocr_pages=ocr, figure_ocr=figure_ocr)
