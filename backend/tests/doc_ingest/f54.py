"""Helper chạy chuẩn hóa bảng trên fixture golden F54 và fixture SYN."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.modules.doc_ingest.normalize.docling_reader import read_items
from app.modules.doc_ingest.normalize.tables import TableRun, build_logical_tables
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.normalized import LogicalTable, Row
from app.modules.doc_ingest.schemas.profile import Profile

F54_DIR = Path(__file__).resolve().parent / "fixtures" / "docling" / "f54"


@lru_cache(maxsize=1)
def _f54_json() -> tuple[str, ...]:
    return tuple(p.read_text(encoding="utf-8") for p in sorted(F54_DIR.glob("*.docling.json")))


def f54_docs(pages: set[int] | None = None) -> list[dict[str, Any]]:
    docs = [json.loads(text) for text in _f54_json()]
    if pages is None:
        return docs
    return [d for d in docs if int(next(iter(d["pages"]))) in pages]


def run_docs(docs: list[dict[str, Any]], profile: str | Profile = "default", doc_id: str = "f54") -> TableRun:
    resolved = load_profile(profile) if isinstance(profile, str) else profile
    return build_logical_tables(read_items(docs, doc_id), doc_id, resolved)


def run_f54(profile: str | Profile = "default") -> TableRun:
    return run_docs(f54_docs(), profile)


def table_on(run: TableRun, page: int, segment: int = 0) -> LogicalTable:
    return next(t for t in run.tables if t.segments[segment].pdf_page_index == page)


def row_by_key(table: LogicalTable, key: str) -> Row:
    return next(r for r in table.rows if r.cells[0].text == key)


def texts(row: Row) -> list[str]:
    return [c.text for c in row.cells]
