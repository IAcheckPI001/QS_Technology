"""quality-report: trạng thái duyệt và nguyên nhân chặn của chunk lá, xuyên tài liệu (chỉ đọc). Không cần Docling."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from app.modules.doc_ingest import cli
from app.modules.doc_ingest.build.builder import write_build
from app.modules.doc_ingest.report import quality_summary as qs
from app.modules.doc_ingest.schemas.chunk import ChunkReviewEntry
from app.modules.doc_ingest.schemas.normalized import ReviewItem
from tests.doc_ingest.chunk_helpers import Doc, build, leaves, logical_table, report


def _item(item_id: str, element_id: str, code: str, blocks: str = "chunk", target: str | None = None) -> ReviewItem:
    return ReviewItem(item_id=item_id, element_id=element_id, code=code, blocking=blocks == "chunk", blocks=blocks,  # type: ignore[arg-type]
                      target=target, detail=f"giả lập {code}")


def _doc() -> tuple[Doc, str]:
    doc = Doc()
    doc.add("heading", "1 Intro", path=("1 Intro",))
    doc.add("text", "Overview of the controller and its main features.", path=("1 Intro",))
    doc.add("heading", "2 Wiring", path=("2 Wiring",), page=2)
    text2 = doc.add("text", "Connect the encoder cable to CN10 before power on.", path=("2 Wiring",), page=2)
    doc.add("heading", "3 Setup", path=("3 Setup",), page=3)
    doc.add("text", "Press the home key and wait for the axis to stop.", path=("3 Setup",), page=3)
    return doc, text2


ITEMS = lambda text2: [  # noqa: E731
    _item("rq-1", "syn:p001", "ocr_required", target="syn:p001"),                       # cấp trang → chunk trang 1
    _item("rq-2", text2, "caption_ambiguous", target=text2),                            # cấp phần tử → chunk trang 2
    _item("rq-3", "syn:p002", "applicability_note", blocks="fact", target="syn:p002"),  # chỉ ghi chú, không chặn
]


def _make_run(root: Path, name: str = "syn", run_id: str = "r1", with_items: bool = True) -> Path:
    run_dir = root / name / run_id
    run_dir.mkdir(parents=True)
    doc, text2 = _doc()
    items = ITEMS(text2) if with_items else []
    result = build(doc, run_dir, review=items, ocr={1})
    (run_dir / "run_report.json").write_text(report([1, 2, 3], {1}).model_dump_json(indent=1), encoding="utf-8")
    normalized = run_dir / "normalized"
    normalized.mkdir()
    (normalized / "review_queue.jsonl").write_text("".join(i.model_dump_json() + "\n" for i in items), encoding="utf-8")
    validation = [
        {"check_id": "V-01", "target": "syn:p001", "score": 0.94, "threshold": 0.9, "passed": False,
         "detail": {"duplicate_ratio": 0.111, "duplicate_max": 0.1, "missing_count": 3,
                    "missing_sample": ["alm￾11", "d￾7"]}},
        {"check_id": "V-01", "target": "syn:p002", "score": 0.84, "threshold": 0.9, "passed": False,
         "detail": {"duplicate_ratio": 0.35, "duplicate_max": 0.1, "missing_count": 25, "missing_sample": ["x50"]}},
        {"check_id": "V-01", "target": "syn:p003", "score": 0.99, "threshold": 0.9, "passed": True, "detail": {}},
    ]
    (normalized / "validation.jsonl").write_text("".join(json.dumps(v) + "\n" for v in validation), encoding="utf-8")
    write_build(result)
    return run_dir


def test_blocking_items_match_builder_blockers(tmp_path: Path) -> None:
    doc, text2 = _doc()
    items = ITEMS(text2)
    result = build(doc, tmp_path, review=items, ocr={1})
    chunks = leaves(result)
    assert len(chunks) == 3
    for chunk in chunks:
        codes = {i.code for i in qs.blocking_items(chunk, items) if i.blocks == "chunk"}
        assert codes == set(chunk.review_blockers), chunk.chunk_key
    by_page = {c.page_start: c for c in chunks}
    assert by_page[1].review_blockers == ["ocr_required"]
    assert by_page[2].review_blockers == ["caption_ambiguous"]
    assert by_page[3].review_blockers == []
    # mục `fact` chạm chunk trang 2 nhưng không phải mã chặn
    assert {i.item_id for i in qs.blocking_items(by_page[2], items)} == {"rq-2", "rq-3"}


def test_table_row_scoped_items(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("heading", "5 Parameters", path=("5 Parameters",))
    seg = doc.add("table_segment", path=("5 Parameters",), table="syn:t001")
    table = logical_table(seg, [["#100", "Speed limit"], ["#101", "Accel time"]])
    chunk = next(c for c in leaves(build(doc, tmp_path, tables={table.logical_table_id: table})) if c.logical_table_id)
    # chunk không chứa phần tử nguồn của mục review (element_id ở nơi khác) → chỉ còn đường theo bảng/dòng
    chunk = chunk.model_copy(update={"row_ids": ["r2"], "element_ids": []})
    other = "syn:p009:e099"
    items = [_item("a", other, "orphan_row", target="syn:t001:r1"),
             _item("b", other, "orphan_row", target="syn:t001:r2"),
             _item("c", other, "complex_header", target="syn:t001")]
    # mục nằm trên dòng r1 không chạm chunk chỉ có r2; mục cấp bảng thì có
    assert [i.item_id for i in qs.blocking_items(chunk, items)] == ["b", "c"]
    # còn khi phần tử nguồn (đoạn bảng) nằm trong chunk thì mọi mục của đoạn đó chạm chunk, như `Assembler._reviews`
    with_segment = chunk.model_copy(update={"element_ids": [other]})
    assert [i.item_id for i in qs.blocking_items(with_segment, items)] == ["a", "b", "c"]


def test_status_precedence(tmp_path: Path) -> None:
    doc, text2 = _doc()
    chunks = {c.page_start: c for c in leaves(build(doc, tmp_path, review=ITEMS(text2), ocr={1}))}
    ocr, defect, clean = chunks[1], chunks[2], chunks[3]

    def entry(chunk, verdict, content_hash=None):
        return ChunkReviewEntry(chunk_key=chunk.chunk_key, content_hash=content_hash or chunk.content_hash,
                                verdict=verdict)

    assert qs._status(clean, True, None) == "approved"
    assert qs._status(clean, False, None) == "pending"
    assert qs._status(clean, False, entry(clean, "ok")) == "reviewed_ok"
    assert qs._status(clean, False, entry(clean, "fix")) == "needs_fix"
    assert qs._status(clean, False, entry(clean, "ok", "da-doi")) == "stale"
    assert qs._status(ocr, False, entry(ocr, "pending")) == "blocked_ocr"
    assert qs._status(defect, False, None) == "blocked_defect"
    assert qs._status(ocr.model_copy(update={"review_blockers": ["ocr_required", "orphan_row"]}), False,
                      None) == "blocked_defect"                       # có lỗi thật thì không còn là "chỉ OCR"
    assert qs._status(defect, False, entry(defect, "fix")) == "needs_fix"
    assert qs.cause_of("ocr_required") == "ocr" and qs.cause_of("orphan_row") == "table"
    assert qs.cause_of("text_coverage_gap") == "coverage" and qs.cause_of("caption_ambiguous") == "other"


def test_load_doc_statuses_groups_and_gaps(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    doc = qs.load_doc(run_dir)
    assert doc is not None and doc.doc_id == "syn_manual_v1" and doc.run == "syn/r1"
    assert doc.leaves == 3 and doc.parents == 0
    assert doc.statuses["blocked_ocr"] == 1 and doc.statuses["blocked_defect"] == 1 and doc.statuses["pending"] == 1
    assert sum(doc.statuses.values()) == doc.leaves
    assert doc.cause_groups == {"ocr": 1, "other": 1} and doc.causes["ocr"] == 1 and doc.causes["other"] == 1
    assert doc.codes == {"ocr_required": 1, "caption_ambiguous": 1}
    assert doc.attribution_mismatch == []
    rows = {r.status: r for r in doc.rows}
    assert rows["blocked_ocr"].item_ids == ["rq-1"] and rows["blocked_defect"].item_ids == ["rq-2"]
    assert rows["blocked_ocr"].pages == [1] and rows["pending"].item_ids == []
    # V-01: p001 chỉ trượt vì lặp (độ phủ 94% ≥ 90%) và text layer hỏng; p002 trượt cả hai
    gaps = {g.page: g for g in doc.page_gaps}
    assert set(gaps) == {1, 2}
    assert gaps[1].failed_by == ["duplicate"] and gaps[1].garbled_text_layer
    assert gaps[2].failed_by == ["coverage", "duplicate"] and not gaps[2].garbled_text_layer


def test_approved_comes_from_export_rows(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path, with_items=False)
    path = run_dir / "build" / "doc_chunks_v2.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["review_status"] = "approved"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    doc = qs.load_doc(run_dir)
    assert doc is not None and doc.statuses["approved"] == 1
    assert next(r for r in doc.rows if r.chunk_key == rows[0]["chunk_key"]).status == "approved"


def test_select_runs(tmp_path: Path) -> None:
    old = _make_run(tmp_path, "docA", "r-old", with_items=False)
    new = _make_run(tmp_path, "docA", "r-new", with_items=False)
    os.utime(old / "build" / "chunks.jsonl", (1, 1))
    _make_run(tmp_path, "docB", "r-new", with_items=False)
    (tmp_path / "_summary" / "x").mkdir(parents=True)
    (tmp_path / "docC" / "empty-run").mkdir(parents=True)                  # run chưa build: bị bỏ qua
    assert qs.select_runs(tmp_path) == [new, tmp_path / "docB" / "r-new"]
    assert qs.select_runs(tmp_path, run_id="r-old") == [old]
    assert qs.select_runs(tmp_path, docs=["docB"]) == [tmp_path / "docB" / "r-new"]
    assert qs.select_runs(tmp_path, docs=[]) == []


def test_outputs_markdown_json_csv(tmp_path: Path) -> None:
    _make_run(tmp_path)
    summary = qs.summarize(qs.select_runs(tmp_path), tmp_path, "r1")
    paths = qs.write_outputs(summary, tmp_path / "_summary" / "t")
    md = paths["md"].read_text(encoding="utf-8")
    for needle in ("## Toàn bộ", "## Theo tài liệu", "## Nhóm nguyên nhân chặn", "OCR chưa kiểm chứng",
                   "`caption_ambiguous`", "## Trang V-01 không đạt", "độ phủ 1, vì lặp vượt ngưỡng 2",
                   "Mọi mã chặn đều truy được về mục review"):
        assert needle in md, needle
    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert data["leaves"] == 3 and sum(data["statuses"].values()) == 3 and "rows" not in data["documents"][0]
    raw = paths["csv"].read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                                  # BOM cho Excel
    rows = list(csv.DictReader(paths["csv"].read_text(encoding="utf-8-sig").splitlines()))
    assert len(rows) == 3 and tuple(rows[0]) == qs.CSV_COLUMNS
    assert {r["status"] for r in rows} == {"blocked_ocr", "blocked_defect", "pending"}
    assert next(r for r in rows if r["status"] == "blocked_ocr")["item_ids"] == "rq-1"


def test_cli_quality_report(tmp_path: Path, capsys) -> None:
    _make_run(tmp_path)
    out = tmp_path / "out"
    assert cli.main(["quality-report", "--runs-dir", str(tmp_path), "--out", str(out)]) == 0
    assert (out / "quality_summary.md").is_file() and (out / "chunks.csv").is_file()
    text = capsys.readouterr().out
    assert "TỔNG" in text and "chặn-OCR" in text
    assert cli.main(["quality-report", "--runs-dir", str(tmp_path), "--docs", "khong-co"]) == 2
    assert cli.main(["quality-report", "--runs-dir", str(tmp_path / "khong-ton-tai")]) == 2
    args = cli._parser().parse_args(["quality-report", "--crm", "--run-id", "crm-1.0-a"])
    assert args.crm and args.run_id == "crm-1.0-a"
