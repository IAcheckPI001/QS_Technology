"""BL-15 + Bước 2b: CQ-01…CQ-10 bắt được vi phạm, độ phủ, ranh giới theo nhãn, so với CSV tay, tổng hợp duyệt,
cổng; adapter `doc_chunks_v1`."""
from __future__ import annotations

import csv
from pathlib import Path

from app.modules.doc_ingest.build import assertions as A
from app.modules.doc_ingest.build.quality import boundaries, gate, manual_comparison, review_summary
from app.modules.doc_ingest.eval.labels import ChunkLabels
from app.modules.doc_ingest.export.doc_chunks_v1 import export_rows, to_row
from app.modules.doc_ingest.schemas.chunk import ChunkReviewEntry, ChunkReviewFile, ReviewSummary
from app.modules.doc_ingest.schemas.normalized import (
    Cell, Column, LogicalTable, Row, Segment, Box,
)
from tests.doc_ingest.chunk_helpers import Doc, build, leaves, ref


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
    pic = doc.add("screenshot", path=("3 Setup",), label="Params:", image=True)
    return doc, build(doc, tmp_path), pic


def _table() -> LogicalTable:
    seg = Segment(element_id="syn:p005:e001", pdf_page_index=5, bbox=Box(x0=0, y0=0, x1=1, y1=1), num_cols_docling=2)
    cols = [Column(index=0, header_text="Code", x_min=0, x_max=1, header_source="detected"),
            Column(index=1, header_text="Meaning", x_min=1, x_max=2, header_source="detected")]
    cell = lambda col, text: Cell(col=col, text=text, bbox=None, raw_cell_ref=None, docling_col=col,  # noqa: E731
                                  docling_header=False, assigned_by="bbox")
    rows = [Row(row_id="r0", segment=0, is_header=True, cells=[cell(0, "Code"), cell(1, "Meaning")])]
    rows += [Row(row_id=f"r{i}", segment=0, is_header=False, cells=[cell(0, f"#{i}"), cell(1, f"meaning {i}")])
             for i in range(1, 4)]
    return LogicalTable(logical_table_id="syn:t001", segments=[seg], columns=cols, rows=rows)


def test_cq_checks_pass_on_builder_output(tmp_path: Path) -> None:
    _, result, _ = _section(tmp_path)
    assert [c.check_id for c in result.quality.checks if c.passed is False] == []


def test_cq03_cq08_cq09_detect_violations(tmp_path: Path) -> None:
    _, result, _ = _section(tmp_path)
    chunks = result.chunks
    parent = chunks[0]
    child = next(c for c in chunks if c.chunk_role == "child")
    long = child.model_copy(update={"content": "x" * 2600})
    assert A.cq03_length([long], {}, 2500).passed is False
    orphan = child.model_copy(update={"parent_key": "syn_manual_v1:B9999"})
    assert A.cq08_parents([parent, orphan]).passed is False
    altered = child.model_copy(update={"content": child.content + " (sửa)"})
    assert A.cq09_child_in_parent([parent, altered]).passed is False


def test_cq10_and_cq06_detect_split_value_and_figure_without_asset(tmp_path: Path) -> None:
    doc, result, pic = _section(tmp_path)
    by_id = {e.element_id: e for e in doc.elements}
    chunks = leaves(result)
    param = next(c for c in chunks if c.chunk_type == "parameter")
    value_id = param.element_ids[-2] if param.element_ids[-1] == pic else param.element_ids[-1]
    moved = [param.model_copy(update={"element_ids": [e for e in param.element_ids if e != value_id]}),
             param.model_copy(update={"chunk_key": "syn_manual_v1:B0099", "element_ids": [value_id]})]
    assert A.cq10_no_split(moved, by_id).passed is False
    figure = param.model_copy(update={"chunk_type": "figure", "assets": []})
    assert A.cq06_assets([figure], by_id).passed is False


def test_cq01_cq02_on_table_parts() -> None:
    table = _table()
    from app.modules.doc_ingest.build.render import header_line, row_line, separator_line
    head = [header_line(table), separator_line(table)]
    base = dict(chunk_role="standalone", scopes=["operation"], product_models=["F54"], chunk_type="table",
                doc_id="d", doc_type="user_guide", doc_title="t", doc_version="v", lang="en", section_title="s",
                page_start=5, page_end=5, embed_text="e", content_hash="h", element_ids=["syn:p005:e001"],
                logical_table_id="syn:t001")
    from app.modules.doc_ingest.schemas.chunk import DraftChunk
    good = DraftChunk(chunk_key="d:B0000", chunk_index=0, row_ids=["r1", "r2", "r3"],
                      content="\n".join(head + [row_line(table, r) for r in table.rows[1:]]), **base)
    assert A.cq01_table_header([good], {"syn:t001": table}).passed is True
    assert A.cq02_rows_whole([good], {"syn:t001": table}).passed is True
    dup = good.model_copy(update={"chunk_key": "d:B0001", "chunk_index": 1, "row_ids": ["r3"]})
    assert A.cq02_rows_whole([good, dup], {"syn:t001": table}).passed is False
    broken = good.model_copy(update={"content": good.content + "\n| #9 | a | extra |"})
    assert A.cq01_table_header([broken], {"syn:t001": table}).passed is False
    # CQ-11 (I-38): chunk bảng nhiều dòng bị cắt khỏi embed_text là lỗi; phần một dòng thì chỉ ghi chú.
    assert A.cq11_table_embed([good]).passed is True
    cut = good.model_copy(update={"flags": ["embed_truncated"]})
    assert A.cq11_table_embed([cut]).passed is False
    single = cut.model_copy(update={"row_ids": ["r1"]})
    result = A.cq11_table_embed([single])
    assert result.passed is True and "một dòng" in result.note
    # CQ-12 (I-43, D-008): lá vượt ngân sách embed → phần bảng nhiều dòng không đạt; lá khác chỉ ghi chú; cha bỏ qua.
    over = good.model_copy(update={"flags": ["embed_over_budget"], "token_count": 700})
    assert A.cq12_embed_budget([good]).passed is True
    assert A.cq12_embed_budget([over]).passed is False
    block = over.model_copy(update={"logical_table_id": None, "row_ids": [], "chunk_type": "procedure"})
    result = A.cq12_embed_budget([block])
    assert result.passed is True and "d:B0000 (700)" in result.note
    parent = over.model_copy(update={"chunk_role": "parent", "chunk_type": "section", "logical_table_id": None})
    skipped = A.cq12_embed_budget([parent])
    assert skipped.checked == 0 and not skipped.failures


def test_parent_gets_no_embed_flags_but_long_leaf_is_flagged(tmp_path: Path) -> None:
    """D-008 (I-43): chunk cha không được embed/tìm → không gắn `embed_truncated`/`embed_over_budget` dù dài;
    chunk lá vượt ngân sách mang `embed_over_budget`. Ngân sách thu nhỏ (300 − 150) để test chạy được cả khi chỉ
    có ước lượng token (venv ingest)."""
    from app.modules.doc_ingest.build.builder import build_chunks
    from app.modules.doc_ingest.build.loader import RunInput
    from app.modules.doc_ingest.profile import load_profile
    from tests.doc_ingest.chunk_helpers import MANIFEST, report

    base = load_profile("qs_controller")
    profile = base.model_copy(update={"chunking": base.chunking.model_copy(update={"embed_max_tokens": 300})})
    doc = Doc()
    doc.add("heading", "1 Intro", path=("1 Intro",))
    sentence = "The operator checks every terminal of the controller before switching the power on. "
    for i in range(3):
        doc.add("label_heading", f"Note {i}:", label=f"Note {i}:")
        doc.add("text", sentence * 7, label=f"Note {i}:")
    run = RunInput(run_dir=tmp_path, report=report([1]), elements=doc.elements, tables={}, review=[])
    chunks = build_chunks(run, MANIFEST, profile).chunks
    parents = [c for c in chunks if c.chunk_role == "parent"]
    leaves_ = [c for c in chunks if c.chunk_role != "parent"]
    assert parents and all(p.content not in p.embed_text for p in parents)   # cha dài hơn giới hạn, bị cắt
    assert not any({"embed_truncated", "embed_over_budget"} & set(p.flags) for p in parents)
    if any(c.token_count is None for c in leaves_):
        return   # không có tiktoken (venv ingest): không đo token, không gắn cờ ngân sách — kết quả build là tạm
    assert any("embed_over_budget" in c.flags for c in leaves_)
    assert all(("embed_over_budget" in c.flags) == ((c.token_count or 0) > 150) for c in leaves_)


def test_boundaries_precision_recall_and_type(tmp_path: Path) -> None:
    _, result, _ = _section(tmp_path)
    labels = ChunkLabels(doc_id="syn", labeled_by="t", method="t", pages=[{"page": 1, "expected_chunks": [
        {"chunk_type": "overview", "start": "3 Setup", "end": "Short overview of the setup section."},
        {"chunk_type": "procedure", "start": "How to set:", "end": "Press B."},
        {"chunk_type": "parameter", "start": "M1920: Homing", "end": "M1920 = 0 : NC"},
    ]}])
    score = boundaries(result.chunks, labels)
    assert score.recall == 1.0 and score.precision == 1.0 and score.type_accuracy == 1.0
    merged = ChunkLabels(doc_id="syn", labeled_by="t", method="t", pages=[{"page": 1, "expected_chunks": [
        {"chunk_type": "procedure", "start": "3 Setup", "end": "Press B."}]}])
    assert boundaries(result.chunks, merged).recall == 0.0   # builder tách thành 2 chunk → không khớp


def test_manual_comparison_against_csv(tmp_path: Path) -> None:
    _, result, _ = _section(tmp_path)
    path = tmp_path / "manual.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["doc_id", "chunk_index", "chunk_type", "section_title",
                                                    "page_start", "content"])
        writer.writeheader()
        writer.writerow({"doc_id": "syn_manual_v1", "chunk_index": 0, "chunk_type": "procedure", "section_title": "x",
                         "page_start": 1, "content": "How to set: Press A. Press B."})
        writer.writerow({"doc_id": "syn_manual_v1", "chunk_index": 1, "chunk_type": "pinout", "section_title": "y",
                         "page_start": 1, "content": "CN5 pin 1 is the enable signal of the handwheel"})
        writer.writerow({"doc_id": "other", "chunk_index": 0, "chunk_type": "x", "section_title": "z",
                         "page_start": 1, "content": "ignored"})
    comp = manual_comparison(result.chunks, path, "syn_manual_v1")
    assert comp.manual_chunks == 2 and comp.covered == 1
    assert comp.matches[0].containment == 1.0 and comp.matches[1].containment < 0.6


def test_review_summary_and_gate(tmp_path: Path) -> None:
    _, result, _ = _section(tmp_path)
    first, second = result.chunks[0], result.chunks[1]
    review = ChunkReviewFile(doc_id="x", reviews=[
        ChunkReviewEntry(chunk_key=first.chunk_key, content_hash=first.content_hash, verdict="ok"),
        ChunkReviewEntry(chunk_key=second.chunk_key, content_hash="old", verdict="fix")])
    summary = review_summary(result.chunks, review)
    assert summary.ok == 1 and summary.stale == 1 and summary.fix == 0
    assert summary.pending == len(result.chunks) - 2
    q = result.quality
    items, passed, provisional = gate(q.checks, q.coverage, None, summary)
    assert passed is None and provisional is True          # chưa có nhãn ranh giới
    _, passed_fix, _ = gate(q.checks, q.coverage, None, ReviewSummary(fix=1, open_fix=["k"]))
    assert passed_fix is False


def test_export_v1_matches_table_constraints(tmp_path: Path) -> None:
    _, result, _ = _section(tmp_path)
    rows, errors = export_rows(result.chunks, ["F54", "F86"])
    assert errors == []
    row = to_row(leaves(result)[0])
    expected = {"parent_key", "domain", "scopes", "product_models", "control_interface", "spec_attributes",
                "chunk_type", "is_active", "doc_id", "doc_type", "lang", "section_id", "section_path",
                "section_title", "page_start", "page_end", "chunk_index", "assets", "metadata", "content",
                "summary_vi", "keywords", "embed_text", "token_count", "content_hash"}
    assert set(row) == expected
    assert row["metadata"]["chunk_role"] == "child" and row["metadata"]["source"] == "builder"
    param_row = next(r for r in rows if r["chunk_type"] == "parameter")
    assert param_row["metadata"]["param_codes"][0]["label"] == "M1920"
    assert all(set(a) == {"bucket", "path", "page", "printed_page"} for r in rows for a in r["assets"])
    bad = dict(row, scopes=[], product_models=["X99"])
    from app.modules.doc_ingest.export.doc_chunks_v1 import row_errors
    assert len(row_errors(bad, ["F54"])) == 2
