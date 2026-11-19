"""Vị trí của chunk trong PDF (trang + vùng) và nguồn CRM trong metadata xuất `doc_chunks_v2` (2026-11-19)."""
from __future__ import annotations

import json
from pathlib import Path

from app.modules.doc_ingest.build.builder import build_chunks
from app.modules.doc_ingest.build.loader import RunInput, load_page_sizes
from app.modules.doc_ingest.export.doc_chunks_v2 import ApprovalContext, to_row
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.manifest import CrmSource
from app.modules.doc_ingest.schemas.normalized import Box
from tests.doc_ingest.chunk_helpers import MANIFEST, Doc, build, leaves, logical_table, report

FINAL = ApprovalContext(gate_2b_final=True)


def _two_page_doc() -> Doc:
    doc = Doc()
    doc.add("heading", "2 Wiring", path=("2 Wiring",))
    doc.add("text", "Connect the encoder cable to CN10 before power on.", path=("2 Wiring",))
    doc.add("text", "Then connect the servo drive to CN11 and check the shield.", path=("2 Wiring",), page=2)
    doc.elements[1] = doc.elements[1].model_copy(update={"bbox": Box(x0=50, y0=100, x1=300, y1=140)})
    doc.elements[2] = doc.elements[2].model_copy(update={"bbox": Box(x0=40, y0=20, x1=280, y1=60)})
    return doc


def test_locations_union_per_page_with_page_size(tmp_path: Path) -> None:
    doc = _two_page_doc()
    run = RunInput(run_dir=tmp_path, report=report([1, 2]), elements=doc.elements, tables={}, review=[],
                   page_sizes={1: (595.0, 842.0), 2: (595.0, 842.0)})
    chunk = leaves(build_chunks(run, MANIFEST, load_profile("qs_controller")))[0]
    by_page = {loc.page: loc for loc in chunk.locations}
    assert set(by_page) == {1, 2} == {chunk.page_start, chunk.page_end}
    # trang 1: hợp heading (0,0,10,10) với đoạn văn (50,100,300,140)
    assert by_page[1].bbox == Box(x0=0, y0=0, x1=300, y1=140)
    assert by_page[2].bbox == Box(x0=40, y0=20, x1=280, y1=60)
    assert by_page[1].printed_page == "1" and by_page[1].page_width == 595.0 and by_page[1].page_height == 842.0


def test_table_rows_use_cell_boxes(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("heading", "5 Parameters", path=("5 Parameters",))
    seg = doc.add("table_segment", path=("5 Parameters",), table="syn:t001")
    table = logical_table(seg, [["#100", "Speed limit"], ["#101", "Accel time"]])
    rows = [r.model_copy(update={"cells": [c.model_copy(update={"bbox": Box(x0=10 * i, y0=200 + 10 * n,
                                                                             x1=10 * i + 9, y1=209 + 10 * n)})
                                           for i, c in enumerate(r.cells)]})
            for n, r in enumerate(table.rows)]
    table = table.model_copy(update={"rows": rows})
    result = build(doc, tmp_path, tables={table.logical_table_id: table})
    table_chunks = [c for c in leaves(result) if c.logical_table_id]
    assert table_chunks and all(c.locations for c in table_chunks)
    assert all(loc.page == 1 for c in table_chunks for loc in c.locations)


def test_export_metadata_locations_and_crm(tmp_path: Path) -> None:
    chunk = leaves(build(_two_page_doc(), tmp_path))[0]
    row = to_row(chunk, FINAL)
    assert [loc["page"] for loc in row["metadata"]["locations"]] == [1, 2]
    assert "crm" not in row["metadata"]                       # manifest cũ: không có nguồn CRM
    source = CrmSource(crm_id="70824a03", version="1.0", file_id="f1", sha256="a" * 64, synced_at="2026-11-19")
    manifest = MANIFEST.model_copy(update={"source": source})
    doc = _two_page_doc()
    run = RunInput(run_dir=tmp_path, report=report([1, 2]), elements=doc.elements, tables={}, review=[])
    crm_chunk = leaves(build_chunks(run, manifest, load_profile("qs_controller")))[0]
    meta = to_row(crm_chunk, FINAL)["metadata"]
    assert meta["crm"] == {"system": "crm", "crm_id": "70824a03", "version": "1.0", "file_id": "f1",
                           "sha256": "a" * 64, "synced_at": "2026-11-19"}
    assert "page_width" not in meta["locations"][0]           # không có kích thước trang → bỏ khóa


def test_load_page_sizes_from_docling_raw(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "p3.docling.json").write_text(json.dumps({"pages": {"3": {"size": {"width": 612, "height": 792}}}}),
                                         encoding="utf-8")
    (raw / "p4.docling.json").write_text("{broken", encoding="utf-8")
    assert load_page_sizes(tmp_path) == {3: (612.0, 792.0)}
