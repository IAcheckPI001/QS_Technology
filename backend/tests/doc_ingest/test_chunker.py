"""BL-16 chunk builder (contract C2 §5, §6, §8): luật chia đơn vị, cha–con, trường lọc, trên dữ liệu tổng hợp
và fixture F54 (qua `cli run`, bước build chạy ở cuối)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.doc_ingest import cli
from app.modules.doc_ingest.manifest import MANIFESTS_DIR, find_manifest, load_manifest
from app.modules.doc_ingest.schemas.normalized import ReviewItem
from tests.doc_ingest.chunk_helpers import Doc, build, leaves, ref
from tests.doc_ingest.f54 import F54_DIR

LONG = "This sentence describes one step of the procedure in plain words for the operator. " * 4


def test_manifests_load_and_resolve_run_doc_ids() -> None:
    manifests = {p.stem: load_manifest(p) for p in MANIFESTS_DIR.glob("*.yaml")}
    assert set(manifests) == {"f54", "f86_installation", "f86_operation"}
    assert all(isinstance(m.doc_version, str) for m in manifests.values())
    assert find_manifest("f86_italliation").doc_id == "f86_installation_2024-04-25"
    assert find_manifest("f54").doc_id == "f54_operation_v02"
    assert find_manifest("unknown") is None


def test_parameter_block_keeps_values_with_definition_and_adds_configuration(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("heading", "1 Intro")
    doc.add("label_heading", "Parameter status description:", label="Parameter status description:")
    for code in (1920, 1921):
        d = doc.add("list_item", f"M{code}: Homing sensor status for axis", label="Parameter status description:",
                    depth=0, refs=[ref(f"M{code}", "definition")])
        for v in (0, 1):
            doc.add("list_item", f"o M{code} = {v} : option {v}", label="Parameter status description:", depth=1,
                    parent=d, marker="o", refs=[ref(f"M{code}", "value_option")])
    result = build(doc, tmp_path)
    [chunk] = leaves(result)
    assert chunk.chunk_type == "parameter" and chunk.chunk_role == "standalone"
    assert chunk.content.splitlines()[:4] == ["1 Intro", "Parameter status description:",
                                               "- M1920: Homing sensor status for axis", "    o M1920 = 0 : option 0"]
    assert chunk.scopes == ["operation", "configuration"]
    assert [r.label for r in chunk.param_refs] == ["M1920", "M1921"]
    assert {"M1920", "M1921", "F54", "1"} <= set(chunk.keywords)
    assert chunk.section_title == "1 Intro › Parameter status description:"
    assert all(c.passed is not False for c in result.quality.checks)


def test_parameter_groups_split_at_definition_boundaries(tmp_path: Path) -> None:
    doc = Doc()
    for code in range(1900, 1930):
        d = doc.add("list_item", f"M{code}: {'long description ' * 4}", label="Params:", depth=0,
                    refs=[ref(f"M{code}", "definition")])
        doc.add("list_item", f"o M{code} = 0 : off", label="Params:", depth=1, parent=d, marker="o",
                refs=[ref(f"M{code}", "value_option")])
    result = build(doc, tmp_path)
    params = [c for c in leaves(result) if c.chunk_type == "parameter"]
    assert len(params) > 1 and all(len(c.content) <= 1200 for c in params)
    cq10 = next(c for c in result.quality.checks if c.check_id == "CQ-10")
    assert cq10.passed is True and cq10.checked == 30


def test_step_label_heading_run_becomes_one_procedure_with_intro(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("label_heading", "Automatic process (M100)", label="Automatic process (M100)")
    doc.add("picture", label="Automatic process (M100)", image=True)
    for n in (1, 2, 3):
        doc.add("label_heading", f"Stage {n}:", label=f"Stage {n}:")
        doc.add("text", f"Stage text number {n}.", label=f"Stage {n}:")
    doc.add("label_heading", "Note:", label="Note:")
    doc.add("text", "At Stage 2 the controller reports an error.", label="Note:")
    doc.add("text", "The cause is that the travel limit is incorrect.", label="Note:")
    result = build(doc, tmp_path)
    kinds = [(c.chunk_type, c.chunk_role) for c in result.chunks]
    assert kinds == [("section", "parent"), ("procedure", "child"), ("alarm", "child")]
    procedure, alarm = leaves(result)
    assert procedure.content.startswith("Automatic process (M100)\nStage 1:") and "Stage 3:" in procedure.content
    assert len(procedure.assets) == 1 and procedure.assets[0].path.startswith("syn_manual_v1/syn_p001_e")
    assert alarm.related_chunk_keys == [procedure.chunk_key] and procedure.related_chunk_keys == [alarm.chunk_key]
    assert alarm.scopes == ["operation", "maintenance"]


def test_long_procedure_split_at_step_boundaries_with_part_title(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("label_heading", "How to calibrate:", label="How to calibrate:")
    for n in range(1, 13):
        doc.add("list_item", f"Step {n}: {LONG}", label="How to calibrate:", depth=0)
    result = build(doc, tmp_path)
    parts = leaves(result)
    assert len(parts) >= 2 and all(c.chunk_type == "procedure" and len(c.content) <= 2500 for c in parts)
    assert parts[0].content.startswith("How to calibrate:\n- Step 1:")
    assert parts[1].content.splitlines()[0].startswith("How to calibrate: (phần 2/")
    assert "procedure_split" in parts[1].flags
    steps = [line for c in parts for line in c.content.splitlines() if line.startswith("- Step")]
    assert len(steps) == 12   # không bước nào bị lặp hoặc mất


def test_figure_block_heading_only_section_and_excluded_elements(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("heading", "2 Wiring", path=("2 Wiring",))                     # mục chỉ có heading → không chunk
    doc.add("heading", "2.1 Input wiring diagram", path=("2 Wiring", "2.1 Input wiring diagram"))
    pic = doc.add("picture", path=("2 Wiring", "2.1 Input wiring diagram"), image=True)
    cap = doc.add("caption", "Figure 3. Input wiring", path=("2 Wiring", "2.1 Input wiring diagram"), owner=pic)
    doc.link_caption(pic, cap)
    doc.add("figure_text", "CN3", path=("2 Wiring", "2.1 Input wiring diagram"), owner=pic)
    doc.add("figure_text", "24V", path=("2 Wiring", "2.1 Input wiring diagram"), owner=pic)
    doc.add("furniture", "Page 3", path=("2 Wiring", "2.1 Input wiring diagram"), layer="furniture")
    doc.add("picture", path=("2 Wiring", "2.1 Input wiring diagram"), image=True, duplicate_of=pic)
    result = build(doc, tmp_path)
    [chunk] = result.chunks
    assert chunk.chunk_type == "wiring" and chunk.content == "2.1 Input wiring diagram\nFigure 3. Input wiring"
    assert chunk.scopes == ["installation"] and chunk.section_id == "2.1"
    assert [a.element_id for a in chunk.assets] == [pic]
    assert [lb.text for lb in chunk.figure_labels] == ["CN3", "24V"] and {"CN3", "24V"} <= set(chunk.keywords)
    assert "Page 3" not in chunk.content
    cov = result.quality.coverage
    assert cov.char_ratio == 1.0 and cov.excluded["heading_only"] == 1 and cov.excluded["duplicate_image"] == 1
    assert "asset_missing" in chunk.flags          # chạy test không có ảnh render


def test_window_parent_contains_children_and_union_assets(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("heading", "3 Setup", path=("3 Setup",))
    doc.add("text", "Short overview of the setup section.", path=("3 Setup",))
    doc.add("label_heading", "How to set:", path=("3 Setup",), label="How to set:")
    doc.add("list_item", "Press A.", path=("3 Setup",), label="How to set:", depth=0)
    doc.add("list_item", "Press B.", path=("3 Setup",), label="How to set:", depth=0)
    pic = doc.add("screenshot", path=("3 Setup",), label="How to set:", image=True)
    result = build(doc, tmp_path)
    parent, *children = result.chunks
    assert parent.chunk_role == "parent" and [c.chunk_role for c in children] == ["child", "child"]
    assert parent.content == "\n\n".join(c.content for c in children)
    assert [a.element_id for a in parent.assets] == [pic]
    assert all(c.parent_key == parent.chunk_key for c in children)
    assert [c.chunk_index for c in result.chunks] == [0, 1, 2]


def test_page_level_review_blocks_chunks_on_that_page(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("text", "Scanned page text.", page=1)
    doc.add("text", "Normal page text.", page=2, path=("2 Other",))
    review = [ReviewItem(item_id="rq-1", element_id="syn:p001", code="ocr_required", blocking=True, blocks="chunk",
                         target="syn:p001", detail="ocr")]
    result = build(doc, tmp_path, review=review, ocr={1})
    first, second = leaves(result)
    assert first.review_blockers == ["ocr_required"] and first.extraction == "ocr" and "ocr_page" in first.flags
    assert second.review_blockers == [] and second.extraction == "text_layer"
    assert result.quality.blocked_chunks == {"ocr_required": 1}
    assert next(c for c in result.quality.checks if c.check_id == "CQ-RB").passed is True


def test_control_interface_and_spec_attributes_from_registry_terms(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("heading", "4 USB port", path=("4 USB port",))
    doc.add("text", "The axis uses Pulse Train signals from the drive.", path=("4 USB port",))
    [chunk] = leaves(build(doc, tmp_path))
    assert chunk.control_interface == ["pulse_train"] and chunk.spec_attributes == ["ports"]


@pytest.fixture(scope="module")
def f54_build(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("runs")
    cli.main(["run", "--raw-dir", str(F54_DIR), "--doc-id", "f54", "--out", str(out), "--run-id", "r1",
              "--profile", "qs_controller"])
    return out / "f54" / "r1"


def test_f54_fixture_run_builds_chunks_that_pass_cq(f54_build: Path) -> None:
    quality = json.loads((f54_build / "build" / "chunk_quality.json").read_text(encoding="utf-8"))
    assert [c["check_id"] for c in quality["checks"] if c["passed"] is False] == []
    assert quality["coverage"]["char_ratio"] == 1.0 and quality["coverage"]["duplicated"] == []
    assert quality["export_errors"] == []
    report = json.loads((f54_build / "run_report.json").read_text(encoding="utf-8"))
    assert report["chunks"]["chunks"] == quality["chunks"]
    assert (f54_build / "report" / "chunks.html").is_file() and (f54_build / "build" / "chunk_review.json").is_file()
    assert "chunks.html" in (f54_build / "report" / "index.html").read_text(encoding="utf-8")


def test_f54_fixture_page19_parameter_and_param_table_parts(f54_build: Path) -> None:
    chunks = [json.loads(line) for line in (f54_build / "build" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    param = next(c for c in chunks if c["chunk_type"] == "parameter" and "M1923 = 1" in c["content"]
                 and c["logical_table_id"] is None)
    assert param["content"].startswith("Parameter stauts description:\n- M1920:")
    assert "    o M1921 = 0 : Normally closed sensor (NC" in param["content"]
    assert param["chunk_role"] == "child" and param["page_start"] == 19
    table_parts = [c for c in chunks if c["logical_table_id"] and c["chunk_type"] == "parameter"]
    assert len(table_parts) >= 3
    header = "| Parameter | Description | Work range | Default |"
    assert all(header in c["content"].splitlines() and len(c["content"]) <= 2500 for c in table_parts)
    rows = [r for c in table_parts for r in c["row_ids"]]
    assert len(rows) == len(set((c["logical_table_id"], r) for c in table_parts for r in c["row_ids"]))


def test_crop_ocr_labels_become_keywords_not_content(tmp_path: Path) -> None:
    from app.modules.doc_ingest.build.builder import build_chunks
    from app.modules.doc_ingest.build.loader import RunInput
    from app.modules.doc_ingest.parse.figure_ocr import targets
    from app.modules.doc_ingest.profile import load_profile
    from tests.doc_ingest.chunk_helpers import MANIFEST, report

    doc = Doc()
    doc.add("heading", "2.2 Homing switch wiring diagram", path=("2.2 Homing switch wiring diagram",))
    pic = doc.add("picture", path=("2.2 Homing switch wiring diagram",), image=True)
    scanned = doc.add("picture", path=("2.2 Homing switch wiring diagram",), image=True, page=2)
    for e in doc.elements:
        if e.image is not None:
            image = tmp_path / e.image.original_path
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"png")
    assert [e.element_id for e in targets(doc.elements, {2}, tmp_path, set())] == [pic]   # trang OCR bỏ qua
    assert targets(doc.elements, set(), tmp_path, {pic, scanned}) == []                   # đã OCR → bỏ qua
    run = RunInput(run_dir=tmp_path, report=report([1, 2], {2}), elements=doc.elements, tables={}, review=[],
                   ocr_pages={2}, figure_ocr={pic: ["X40 - X axis", "COM", "Signal", "OV", "24V", "NPN"]})
    [chunk] = build_chunks(run, MANIFEST, load_profile("qs_controller")).chunks
    assert [(lb.text, lb.source) for lb in chunk.figure_labels] == [
        ("X40", "crop_ocr"), ("COM", "crop_ocr"), ("24V", "crop_ocr"), ("NPN", "crop_ocr")]
    assert "X40" in chunk.keywords and "X40" not in chunk.content and "asset_missing" not in chunk.flags
