"""Adapter `doc_chunks_v2` (D-009): chuẩn hóa mã, `codes` của chunk, `review_status`, ràng buộc dòng và bộ dòng,
file `build/doc_chunks_v2.jsonl`."""
from __future__ import annotations

import json
from pathlib import Path

from app.modules.doc_ingest.build.builder import source_run, write_rows_v2
from app.modules.doc_ingest.export.doc_chunks_v2 import (
    MAX_RANGE_CODES, ApprovalContext, chunk_codes, export_rows, normalize_code, review_status, set_errors, to_row,
)
from app.modules.doc_ingest.schemas.chunk import ChunkReviewEntry, ChunkReviewFile, FigureLabel
from app.modules.doc_ingest.technical_refs.params import ParamRef
from tests.doc_ingest.chunk_helpers import Doc, build, leaves, ref

FINAL = ApprovalContext(gate_2b_final=True)


def _section(tmp_path: Path):
    doc = Doc()
    doc.add("heading", "3 Setup", path=("3 Setup",))
    doc.add("text", "Short overview of the setup section.", path=("3 Setup",))
    doc.add("label_heading", "How to set:", path=("3 Setup",), label="How to set:")
    doc.add("list_item", "Press A.", path=("3 Setup",), label="How to set:", depth=0)
    doc.add("list_item", "Press B.", path=("3 Setup",), label="How to set:", depth=0)
    d = doc.add("list_item", "M1920: Homing", path=("3 Setup",), label="Params:", depth=0,
                refs=[ref("M1920", "definition")])
    doc.add("list_item", "o M1920 = 0 : NC", path=("3 Setup",), label="Params:", depth=1, parent=d, marker="o",
            refs=[ref("M1920", "value_option")])
    doc.add("screenshot", path=("3 Setup",), label="Params:", image=True)
    return build(doc, tmp_path)


def test_normalize_code() -> None:
    assert normalize_code("#0008") == "#8"
    assert normalize_code("#12010") == "#12010"
    assert normalize_code("m1920") == "M1920"
    assert normalize_code("X 41") == "X41"
    assert normalize_code("AX1.ENA") == "AX1.ENA"
    assert normalize_code("PUL1+") == "PUL1+"
    assert normalize_code("IN0") == "IN0"
    for not_code in ("24V", "GND", "NPN", "0 V", "Figure 3", "#", "ABCDE1"):
        assert normalize_code(not_code) is None, not_code


def test_chunk_codes_expand_ranges_and_skip_models(tmp_path: Path) -> None:
    chunk = leaves(_section(tmp_path))[0]
    long_range = list(range(MAX_RANGE_CODES + 10))
    chunk = chunk.model_copy(update={
        "product_models": ["F54"],
        "param_refs": [ParamRef(prefix="#", kind="range", codes=[12090, 12091, 12092, 12093], range_start=12090,
                                range_end=12093, label="#12090 - #12093"),
                       ParamRef(prefix="#", kind="range", codes=long_range, range_start=0,
                                range_end=long_range[-1], label="#0000 - #0073"),
                       ParamRef(prefix="M", kind="single", codes=[1920], label="M1920")],
        "io_codes": ["CN3", "X41"],
        "figure_labels": [FigureLabel(text="F54", element_id="e", source="crop_ocr"),
                          FigureLabel(text="X51", element_id="e", source="crop_ocr"),
                          FigureLabel(text="Y99", element_id="e", source="crop_ocr", verified=False),
                          FigureLabel(text="24V", element_id="e", source="crop_ocr"),
                          FigureLabel(text="X41", element_id="e", source="crop_ocr")]})
    codes = chunk_codes(chunk)
    assert codes[:4] == ["#12090", "#12091", "#12092", "#12093"]
    assert "#0" in codes and f"#{long_range[-1]}" in codes and "#1" not in codes   # dải dài: chỉ hai đầu
    assert {"M1920", "CN3", "X41", "X51"} <= set(codes)
    assert "F54" not in codes and "Y99" not in codes and "24V" not in codes   # model, nhãn chưa xác minh, không phải mã
    assert codes.count("X41") == 1


def test_review_status_rules(tmp_path: Path) -> None:
    result = _section(tmp_path)
    parent = next(c for c in result.chunks if c.chunk_role == "parent")
    leaf = leaves(result)[0].model_copy(update={"enrichment_status": "approved"})
    ok = ApprovalContext(gate_2b_final=True, ok_hashes={parent.chunk_key: parent.content_hash,
                                                         leaf.chunk_key: leaf.content_hash})
    assert review_status(parent, ok) == "approved"            # cha: chỉ cần cổng 2b + verdict ok
    assert review_status(leaf, ok) == "approved"
    provisional = ApprovalContext(gate_2b_final=False, ok_hashes=ok.ok_hashes)
    assert review_status(leaf, provisional) == "draft"       # cổng 2b tạm (nhãn chưa xác nhận) không tính
    assert review_status(leaf.model_copy(update={"enrichment_status": "draft"}), ok) == "draft"
    assert review_status(leaf.model_copy(update={"content_hash": "khác"}), ok) == "draft"   # verdict đã stale
    assert review_status(leaf.model_copy(update={"review_blockers": ["ocr_required"]}), ok) == "draft"
    assert review_status(leaf, FINAL) == "draft"              # chưa có verdict ok


def test_approval_context_from_build(tmp_path: Path) -> None:
    result = _section(tmp_path)
    chunk = result.chunks[0]
    review = ChunkReviewFile(doc_id="d", reviews=[
        ChunkReviewEntry(chunk_key=chunk.chunk_key, content_hash=chunk.content_hash, verdict="ok"),
        ChunkReviewEntry(chunk_key="d:B0099", content_hash="h", verdict="fix")])
    quality = result.quality.model_copy(update={"gate_passed": True, "provisional": True})
    ctx = ApprovalContext.from_build(quality, review)
    assert ctx.gate_2b_final is False and ctx.ok_hashes == {chunk.chunk_key: chunk.content_hash}
    final = ApprovalContext.from_build(quality.model_copy(update={"provisional": False}), review)
    assert final.gate_2b_final is True


def test_export_v2_rows_match_table(tmp_path: Path) -> None:
    result = _section(tmp_path)
    rows, errors = export_rows(result.chunks, FINAL, "syn/eval-a")
    assert errors == []
    expected = {"parent_key", "doc_id", "doc_version", "doc_title", "doc_type", "lang", "chunk_key", "chunk_index",
                "chunk_role", "chunk_type", "domain", "scopes", "product_models", "applies_to_models",
                "control_interface", "spec_attributes", "section_id", "section_path", "section_title",
                "page_start", "page_end", "printed_page_start", "printed_page_end", "content", "summary_vi",
                "keywords", "codes", "embed_text", "token_count", "content_hash", "assets", "metadata", "source",
                "review_status", "is_active", "source_run"}
    assert set(rows[0]) == expected
    child = next(r for r in rows if r["chunk_role"] == "child")
    assert child["parent_key"] and child["source"] == "builder" and child["source_run"] == "syn/eval-a"
    assert child["printed_page_start"] == 1 and child["review_status"] == "draft"
    param = next(r for r in rows if r["chunk_type"] == "parameter")
    assert "M1920" in param["codes"]
    assert to_row(result.chunks[0].model_copy(update={"printed_page_start": "iv"}), FINAL)["printed_page_start"] \
        is None


def test_export_v2_set_errors(tmp_path: Path) -> None:
    rows, _ = export_rows(_section(tmp_path).chunks, FINAL)
    child = next(r for r in rows if r["chunk_role"] == "child")
    orphan = dict(child, chunk_key="x:B9", chunk_index=99, parent_key="x:B0404")
    dup = dict(child)
    errors = set_errors(rows + [orphan, dup])
    assert any("không phải chunk cha" in e for e in errors)
    assert any(e.startswith("chunk_key trùng") for e in errors)
    from app.modules.doc_ingest.export.doc_chunks_v2 import row_errors
    assert any("chunk con không có parent_key" in e for e in row_errors(dict(child, parent_key=None)))


def test_write_rows_v2_file_and_quality(tmp_path: Path) -> None:
    (tmp_path / "build").mkdir()
    result = _section(tmp_path)
    path = write_rows_v2(result, None)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == len(result.chunks)
    assert result.quality.review_status_v2 == {"draft": len(rows)}
    assert result.quality.export_errors_v2 == []
    assert source_run(tmp_path) == "/".join(tmp_path.resolve().parts[-2:])
