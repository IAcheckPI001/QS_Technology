"""BL-16 chunk builder (contract C2 §5, §6, §8): luật chia đơn vị, cha–con, trường lọc, trên dữ liệu tổng hợp
và fixture F54 (qua `cli run`, bước build chạy ở cuối)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.doc_ingest import cli
from app.modules.doc_ingest.build.chunker import Block, Chunker, TableItem
from app.modules.doc_ingest.manifest import MANIFESTS_DIR, find_manifest, load_manifest
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.normalized import ReviewItem
from tests.doc_ingest.chunk_helpers import Doc, build, leaves, logical_table, ref
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


def test_content_scope_rules_add_but_never_remove(tmp_path: Path) -> None:
    """I-46: scope theo nội dung được THÊM vào scope theo mục (manifest), không bớt; tên phần cấp 1 không xét."""
    from app.modules.doc_ingest.build.fields import Assembler
    from app.modules.doc_ingest.build.chunker import Unit
    from app.modules.doc_ingest.profile import load_profile
    from tests.doc_ingest.chunk_helpers import MANIFEST, report
    from app.modules.doc_ingest.build.loader import RunInput

    run = RunInput(run_dir=tmp_path, report=report([1]), elements=[], tables={}, review=[], ocr_pages=set())
    asm = Assembler(run, MANIFEST, load_profile("qs_controller"))

    def scopes(path: tuple[str, ...], text: str, chunk_type: str = "overview", label: str | None = None):
        return asm._scopes(Unit(chunk_type=chunk_type, section_path=path, label=label, elements=[],
                                lines=text.splitlines()))

    part = "PART 2: WIRING - CONNECTION - SETTING"
    # Tên phần cấp 1 có "SETTING" nhưng không xét → chỉ scope theo manifest (wiring → installation).
    assert scopes((part, "2.3 Input devices wiring"), "Connect the sensor to X40.") == ["installation"]
    # Tiêu đề từ cấp 2 có "configuration"/"setting" → thêm configuration, giữ installation.
    assert scopes((part, "2.6 Axis wiring", "2.6.4 Axis configuration"), "Note: set gear ratio.") == \
        ["installation", "configuration"]
    # Nội dung thủ tục cài tham số → thêm configuration dù tiêu đề là sơ đồ đấu dây.
    assert scopes((part, "2.3.2.4 Homing switch wiring diagram"),
                  "From the PARAMETER screen, use the arrow keys.\nEnter the user password.") == \
        ["installation", "configuration"]
    # Dấu hiệu vận hành rõ ràng → thêm operation; "press"/"screen" thường thì không.
    assert scopes((part, "2.6.5 Automatic tool setter wiring"), "Automatic tool setting process (M100)\nStage 1:") == \
        ["installation", "operation"]
    assert scopes(("3 Functions", "3.9 Search"), "Press the ENTER button on the screen.") == ["operation"]
    # Nguyên nhân lỗi → thêm maintenance.
    assert "maintenance" in scopes((part, "2.6.5 Automatic tool setter wiring"),
                                   "If not, the controller reports an error. The cause is the limit.")
    # Bản vẽ kích thước (manifest mặc định operation) → thêm installation theo loại chunk.
    assert scopes(("1 Overview", "1.2 Dimension"), "Figure 3. dimension drawing", "dimension") == \
        ["installation", "operation"]


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


def test_short_note_after_figure_merges_into_figure_chunk(tmp_path: Path) -> None:
    """I-45 (F54 2.2): hình + caption rồi "Note:" ngắn cùng mục → một chunk hình; ghi chú dài thì vẫn tách."""
    path = ("2.2 Controller power supply",)
    for note, merged in (("Using pulse-type power supply is better than transformer.", True), (LONG * 2, False)):
        doc = Doc()
        doc.add("heading", path[0], path=path)
        pic = doc.add("picture", path=path, image=True)
        cap = doc.add("caption", "Figure 6. Commonly used power supply type", path=path, owner=pic)
        doc.link_caption(pic, cap)
        doc.add("label_heading", "Note:", path=path, label="Note:")
        doc.add("list_item", note, path=path, label="Note:", depth=0)
        chunks = leaves(build(doc, tmp_path / str(merged)))
        if merged:
            [chunk] = chunks
            assert chunk.chunk_type == "figure" and "Figure 6." in chunk.content and note.strip() in chunk.content
        else:
            assert len(chunks) == 2 and chunks[0].chunk_type == "figure" and note.strip() in chunks[1].content


def test_manifest_excluded_pages_and_sections_are_not_chunked(tmp_path: Path) -> None:
    from app.modules.doc_ingest.build.builder import build_chunks
    from app.modules.doc_ingest.build.loader import RunInput
    from tests.doc_ingest.chunk_helpers import MANIFEST, report

    doc = Doc()
    doc.add("text", "We sincerely thank you for choosing our controller.", path=(), page=1)
    doc.add("heading", "9 Revision history", path=("9 Revision history",), page=2)
    doc.add("text", "V.02 updated wiring.", path=("9 Revision history",), page=2)
    doc.add("heading", "2.2 Power", path=("2.2 Power",), page=3)
    doc.add("text", "Connect 24V to the controller.", path=("2.2 Power",), page=3)
    manifest = MANIFEST.model_copy(update={"exclude_pages": [1], "exclude_sections": ["9 Revision"]})
    run = RunInput(run_dir=tmp_path, report=report([1, 2, 3]), elements=doc.elements, tables={}, review=[])
    result = build_chunks(run, manifest, load_profile("qs_controller"))
    text = "\n".join(c.content for c in result.chunks)
    assert "thank you" not in text and "Revision" not in text and "Connect 24V" in text
    cov = result.quality.coverage
    assert cov.excluded["manifest_excluded"] == 3 and not cov.missing


def test_text_frame_is_not_an_asset_and_ocr_labels_only_key_wiring(tmp_path: Path) -> None:
    """I-44: khung chữ `text_frame` không là asset, không làm khối thành chunk hình; nhãn OCR hình chỉ vào từ khóa
    của chunk wiring/pinout/dimension."""
    from app.modules.doc_ingest.build.builder import build_chunks
    from app.modules.doc_ingest.build.loader import RunInput
    from tests.doc_ingest.chunk_helpers import MANIFEST, report

    path = ("4.2.2 Divide by 2",)
    doc = Doc()
    doc.add("heading", path[0], path=path)
    shot = doc.add("picture", path=path, image=True)
    frame = doc.add("picture", path=path, image=True)
    doc.add("label_heading", "Step 1:", path=path, label="Step 1:")
    doc.add("text", "From relative coordinates screen, select HALF.", path=path, label="Step 1:")
    doc.add("label_heading", "Step 2:", path=path, label="Step 2:")
    doc.add("text", "Select the axis.", path=path, label="Step 2:")
    doc.elements = [e.model_copy(update={"flags": ["text_frame"]}) if e.element_id == frame else e
                    for e in doc.elements]
    run = RunInput(run_dir=tmp_path, report=report([1]), elements=doc.elements, tables={}, review=[],
                   figure_ocr={shot: ["X41", "PUL1+"]})
    [chunk] = [c for c in build_chunks(run, MANIFEST, load_profile("qs_controller")).chunks]
    assert [a.element_id for a in chunk.assets] == [shot] and chunk.chunk_type == "procedure"
    assert {lb.text for lb in chunk.figure_labels} >= {"X41", "PUL1+"}
    assert not {"X41", "PUL1+"} & set(chunk.keywords)   # procedure: nhãn OCR không vào từ khóa
    wiring = Doc()
    wpath = ("2.3 Input wiring diagram",)
    wiring.add("heading", wpath[0], path=wpath)
    pic = wiring.add("picture", path=wpath, image=True)
    run = RunInput(run_dir=tmp_path, report=report([1]), elements=wiring.elements, tables={}, review=[],
                   figure_ocr={pic: ["X41", "PUL1+"]})
    [wchunk] = build_chunks(run, MANIFEST, load_profile("qs_controller")).chunks
    assert wchunk.chunk_type == "wiring" and {"X41", "PUL1+"} <= set(wchunk.keywords)


def test_step_restart_splits_procedures_and_moves_lead_and_diagram(tmp_path: Path) -> None:
    """I-42 (F54 4.4.3): hai thủ tục liền nhau, mỗi thủ tục câu dẫn + sơ đồ + Step 1–2; số bước quay về 1 →
    thủ tục mới; câu dẫn + sơ đồ cùng trang đi theo thủ tục của nó; khối tiêu đề + sơ đồ + câu dẫn đầu mục
    gộp vào thủ tục đầu."""
    path = ("4.4.3 Center",)
    doc = Doc()
    doc.add("heading", "4.4.3 Center", path=path)
    pic1 = doc.add("picture", path=path, image=True)
    doc.add("text", "Determine the center using 4 points.", path=path)
    for page, n in ((1, 4), (2, 3)):
        doc.add("label_heading", "Step 1:", path=path, page=page, label="Step 1:")
        doc.add("text", f"Select function for {n} points", path=path, page=page, label="Step 1:")
        doc.add("label_heading", "Step 2:", path=path, page=page, label="Step 2:")
        doc.add("text", f"Touch the {n} edges of the workpiece. " + LONG[:150], path=path, page=page, label="Step 2:")
        if page == 1:   # sơ đồ + câu dẫn thủ tục 2 nằm cuối khối "Step 2:" của thủ tục 1 (trang sau)
            pic2 = doc.add("picture", path=path, page=2, image=True, label="Step 2:")
            doc.add("text", "Determine the center using 3 points.", path=path, page=2, label="Step 2:")
    procs = [c for c in leaves(build(doc, tmp_path)) if c.chunk_type == "procedure"]
    assert len(procs) == 2
    first, second = procs
    assert first.content.startswith("4.4.3 Center\nDetermine the center using 4 points.\nStep 1:")
    assert "3 points" not in first.content and [a.element_id for a in first.assets] == [pic1]
    assert second.content.startswith("Determine the center using 3 points.\nStep 1:")
    assert [a.element_id for a in second.assets] == [pic2]


def _case_doc(cases: int, words: bool = True, long_case: int | None = None) -> tuple[Doc, dict[int, str]]:
    """Khối "Gear ratio calculation:" + công thức + n ví dụ, mỗi ví dụ mở bằng ảnh và "Case n:" (F54 mục 2.6.4.7)."""
    doc = Doc()
    label = "Gear ratio calculation:"
    doc.add("label_heading", label, label=label)
    doc.add("text", "Formula: ratio = pulses / lead", label=label)
    pics = {}
    for n in range(1, cases + 1):
        pics[n] = doc.add("picture", label=label, image=True)
        doc.add("text", f"Case {n}: drive type {n}" if words else f"Drive type {n}", label=label)
        doc.add("text", (f"Example {n}: " if words else "") + LONG * (7 if n == long_case else 1), label=label)
        doc.add("text", f"Result of drive {n}: " + LONG, label=label)
        doc.add("list_item", f"#12010 = {n}000", label=label, depth=0)
    return doc, pics


def test_long_block_splits_at_case_boundaries_and_repeats_lead(tmp_path: Path) -> None:
    """I-39: khối dài chỉ chia ở đầu "Case n"; phần sau lặp tiêu đề + công thức; ảnh đi cùng Case của nó."""
    doc, pics = _case_doc(4)
    parts = leaves(build(doc, tmp_path))
    assert len(parts) >= 2 and all("block_split" in c.flags and len(c.content) <= 2500 for c in parts)
    assert parts[0].content.startswith("Gear ratio calculation:\nFormula: ratio = pulses / lead\n")
    for i, c in enumerate(parts[1:], start=2):
        assert c.content.splitlines()[:2] == [f"Gear ratio calculation: (phần {i}/{len(parts)})",
                                              "Formula: ratio = pulses / lead"]
        assert c.content.splitlines()[2].startswith("Case ")
    for n in range(1, 5):   # mỗi Case (đầu, giữa, kết quả, giá trị) và ảnh của nó nằm trọn trong một chunk
        [owner] = [c for c in parts if f"Case {n}:" in c.content]
        assert f"Result of drive {n}:" in owner.content and f"#12010 = {n}000" in owner.content
        assert pics[n] in [a.element_id for a in owner.assets]
        assert sum(c.content.count(f"Case {n}:") for c in parts) == 1


def test_long_block_without_part_starts_keeps_element_split(tmp_path: Path) -> None:
    doc, _ = _case_doc(4, words=False)
    parts = leaves(build(doc, tmp_path))
    assert len(parts) >= 2 and all("block_split" in c.flags for c in parts)
    assert not any("(phần" in c.content for c in parts)


def test_case_longer_than_limit_is_split_by_element_and_flagged(tmp_path: Path) -> None:
    doc, _ = _case_doc(3, long_case=2)
    parts = leaves(build(doc, tmp_path))
    assert all(len(c.content) <= 2500 and "block_split" in c.flags for c in parts)
    flagged = [c for c in parts if "block_part_oversize" in c.flags]   # chỉ phần chứa Case 2 (bị chia theo phần tử)
    assert flagged and all("Case 2:" in c.content or "Result of drive 2:" in c.content for c in flagged)
    assert not any("block_part_oversize" in c.flags for c in parts if "Case 1:" in c.content)
    text = "\n".join(c.content for c in parts)
    assert all(text.count(f"Result of drive {n}:") == 1 for n in range(1, 4))


def test_private_use_bullet_glyph_renders_as_dash() -> None:
    from app.modules.doc_ingest.build.render import element_line

    doc = Doc()
    t = doc.add("text", " Number of pulse = 1000")
    li = doc.add("list_item", " #12010 = 1", depth=0)
    by_id = {e.element_id: e for e in doc.elements}
    assert element_line(by_id[t]) == "- Number of pulse = 1000"
    assert element_line(by_id[li]) == "- #12010 = 1"


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


def test_title_with_uncaptioned_picture_merges_into_next_block(tmp_path: Path) -> None:
    """I-37 (F54 PART 4): heading + ảnh "Description images" không sinh chunk hình chỉ có tiêu đề."""
    path = ("4 Operation", "4.3.3 Go to any command line")
    doc = Doc()
    doc.add("heading", "4.3.3 Go to any command line", path=path)
    pic = doc.add("picture", path=path, image=True)
    for n in (1, 2):
        doc.add("label_heading", f"Step {n}:", path=path, label=f"Step {n}:")
        doc.add("text", f"Press button number {n}.", path=path, label=f"Step {n}:")
    result = build(doc, tmp_path)
    [chunk] = result.chunks
    assert (chunk.chunk_type, chunk.chunk_role) == ("procedure", "standalone")
    assert chunk.content.splitlines() == ["4.3.3 Go to any command line", "Step 1:", "Press button number 1.",
                                          "Step 2:", "Press button number 2."]
    assert [a.element_id for a in chunk.assets] == [pic]
    assert result.quality.coverage.char_ratio == 1.0


def test_title_with_uncaptioned_picture_at_section_end_or_alone(tmp_path: Path) -> None:
    doc = Doc()
    doc.add("heading", "4.2 Coordinate screen", path=("4.2 Coordinate screen",))
    doc.add("text", "The user can view the machine coordinates on this screen.", path=("4.2 Coordinate screen",))
    doc.add("label_heading", "Screen:", path=("4.2 Coordinate screen",), label="Screen:")
    end = doc.add("picture", path=("4.2 Coordinate screen",), label="Screen:", image=True)
    doc.add("heading", "2.2 Input low diagram", path=("2.2 Input low diagram",))     # mục chỉ có tiêu đề + hình
    alone = doc.add("picture", path=("2.2 Input low diagram",), image=True)
    first, second = build(doc, tmp_path).chunks
    assert first.content.splitlines()[-1] == "Screen:" and [a.element_id for a in first.assets] == [end]
    assert second.content == "2.2 Input low diagram" and [a.element_id for a in second.assets] == [alone]
    assert second.chunk_type in ("figure", "wiring")


def test_merge_title_blocks_before_table() -> None:
    """R-04: dòng dẫn kết thúc bằng ":" thành dòng dẫn của bảng; khối tiêu đề + hình trước bảng giữ nguyên."""
    doc = Doc()
    doc.add("heading", "1.1 Overview")
    doc.add("text", "Specification:")
    doc.add("heading", "1.2 Views")
    doc.add("picture", image=True)
    doc.add("text", "A normal sentence that is not a lead-in line.")
    heading, lead, title, picture, sentence = doc.elements
    chunker = Chunker(load_profile("qs_controller"), doc.elements, {})
    table = TableItem(table=None, first=heading, caption=None)   # type: ignore[arg-type]
    [block] = chunker._merge_title_blocks([Block(None, [heading, lead]), Block(None, table=table)])
    assert block.table is table and block.lead == [heading, lead]
    kept = chunker._merge_title_blocks([Block(None, [title, picture]), Block(None, table=table)])
    assert [b.elements for b in kept] == [[title, picture], []] and kept[1].lead == []
    kept = chunker._merge_title_blocks([Block(None, [heading, sentence]), Block(None, table=table)])
    assert [b.elements for b in kept] == [[heading, sentence], []]


def test_unlabelled_step_block_joins_following_step_blocks(tmp_path: Path) -> None:
    """F54 3.9.2: "Step 1:" ở trang đầu là text không nhãn → vẫn cùng một thủ tục với Step 3, Step 4."""
    doc = Doc()
    doc.add("heading", "3 Load")
    doc.add("text", "Step 1:")
    doc.add("text", "On main screen select SYSTEM")
    doc.add("text", "Step 2: Enter the user password and press the OK button.")
    for n in (3, 4):
        doc.add("label_heading", f"Step {n}:", label=f"Step {n}:")
        doc.add("text", f"Select item number {n}.", label=f"Step {n}:")
    [chunk] = build(doc, tmp_path).chunks
    assert chunk.chunk_type == "procedure" and chunk.content.startswith("3 Load\nStep 1:")
    assert chunk.content.endswith("Step 4:\nSelect item number 4.")


def test_step_label_counts_as_a_step_of_its_block(tmp_path: Path) -> None:
    """F54 4.5.3: nhãn "Step 1:" + dòng "Step 2: …" viết liền trong text là thủ tục, không phải chunk hình."""
    doc = Doc()
    doc.add("heading", "4.5.3 Working history")
    doc.add("picture", image=True)
    doc.add("label_heading", "Step 1:", label="Step 1:")
    doc.add("text", "Press the right arrow button to move to the next page.", label="Step 1:")
    doc.add("text", "Step 2: Press the PART LOG button.", label="Step 1:")
    [chunk] = build(doc, tmp_path).chunks
    assert chunk.chunk_type == "procedure" and len(chunk.assets) == 1
    lone = Doc()
    lone.add("label_heading", "Step 1:", label="Step 1:")
    lone.add("text", "Only one step in this block.", label="Step 1:")
    assert build(lone, tmp_path).chunks[0].chunk_type == "overview"       # một bước chưa là thủ tục


def _table_doc(rows: list[list[str]]):
    doc = Doc()
    doc.add("heading", "5.1 Axis parameters", path=("5 Parameters", "5.1 Axis parameters"))
    seg = doc.add("table_segment", path=("5 Parameters", "5.1 Axis parameters"), table="syn:t001")
    return doc, {"syn:t001": logical_table(seg, rows)}


def _table_lines(chunk) -> list[str]:
    return [line for line in chunk.content.splitlines() if line.startswith("|") and not line.startswith("|---")]


def test_long_table_is_split_by_embed_token_budget_with_balanced_parts(tmp_path: Path) -> None:
    """I-38: bảng dài chia ở ranh giới dòng theo token của `embed_text`, lặp tiêu đề + header, các phần cân nhau."""
    rows = [[f"#{1000 + i}", f"Axis setting number {i} with a long description of the work range"] for i in range(70)]
    doc, tables = _table_doc(rows)
    result = build(doc, tmp_path, tables=tables)
    parts = leaves(result)
    assert len(parts) >= 3 and all(c.chunk_type == "parameter" and "table_part" in c.flags for c in parts)
    assert all("embed_truncated" not in c.flags for c in parts)
    assert [r for c in parts for r in c.row_ids] == [f"r{i}" for i in range(1, 71)]       # mỗi dòng đúng một lần
    assert all(_table_lines(c)[0] == "| Parameter | Description |" for c in parts)        # header lặp ở mọi phần
    assert parts[0].content.splitlines()[0] == "5.1 Axis parameters"
    assert parts[1].content.splitlines()[0] == f"5.1 Axis parameters (phần 2/{len(parts)})"
    sizes = [len(c.row_ids) for c in parts]
    assert max(sizes) - min(sizes) <= 2                                                   # không còn phần đuôi 1 dòng
    limit = 800 - 150                                                                     # chừa chỗ cho Bước 3
    count = result.chunks[0].token_count
    if count is not None:                                                                 # venv có tiktoken
        assert all(c.token_count <= limit for c in parts)
    assert all(c.passed is not False for c in result.quality.checks)


def test_short_table_stays_in_one_chunk(tmp_path: Path) -> None:
    doc, tables = _table_doc([[f"#{i}", f"Setting {i}"] for i in range(1, 6)])
    [chunk] = build(doc, tmp_path, tables=tables).chunks
    assert chunk.flags == ["asset_missing"] or "table_part" not in chunk.flags
    assert len(chunk.row_ids) == 5


def test_table_group_row_stays_with_its_rows_and_repeats_in_next_part(tmp_path: Path) -> None:
    """Dòng nhóm (một ô có chữ): không đứng cuối một phần; nhóm bị chia thì phần sau lặp lại dòng nhóm."""
    rows: list[list[str]] = []
    for axis in ("X axis", "Y axis"):
        rows.append([axis, ""])
        rows += [[f"#{len(rows) + 2000}", f"{axis} parameter with a fairly long description text {i}"]
                 for i in range(30)]
    doc, tables = _table_doc(rows)
    table = tables["syn:t001"]
    parts = leaves(build(doc, tmp_path, tables=tables))
    assert len(parts) >= 3
    group_ids = {r.row_id for r in table.rows if not r.is_header and r.cells[1].text == ""}
    all_ids = [r for c in parts for r in c.row_ids]
    assert all_ids == [r.row_id for r in table.rows[1:]]                 # dòng nhóm cũng chỉ được tính một lần
    for c in parts:
        assert c.row_ids[-1] not in group_ids                            # không kết thúc phần bằng dòng nhóm
        first_data = _table_lines(c)[1]
        if c.row_ids[0] not in group_ids:                                # phần bắt đầu giữa nhóm: lặp dòng nhóm
            assert first_data in ("| X axis |  |", "| Y axis |  |")
            assert len(_table_lines(c)) - 1 == len(c.row_ids) + 1
    assert any(c.row_ids[0] not in group_ids for c in parts)


def test_table_row_longer_than_budget_becomes_its_own_part(tmp_path: Path) -> None:
    huge = "word " * 480                                                 # ~2.400 ký tự: một dòng vượt ngân sách token
    doc, tables = _table_doc([["#1", "short"], ["#2", huge.strip()], ["#3", "short"]])
    result = build(doc, tmp_path, tables=tables)
    sizes = [c.row_ids for c in leaves(result)]
    assert ["r2"] in sizes and sorted(r for ids in sizes for r in ids) == ["r1", "r2", "r3"]
    cq11 = next(c for c in result.quality.checks if c.check_id == "CQ-11")
    assert cq11.passed is not False                                      # một dòng đơn lẻ không tính là lỗi chia


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


def test_crop_ocr_label_needs_document_vocab_or_trusted_pattern(tmp_path: Path) -> None:
    """I-40b: nhãn OCR crop vào `keywords` khi có trong từ vựng text layer của tài liệu hoặc khớp mẫu tin cậy của
    profile; nhãn khác (OCR đọc sai, điểm tin cậy vẫn cao) giữ trong `figure_labels` với `verified = False`."""
    from app.modules.doc_ingest.build.builder import build_chunks
    from app.modules.doc_ingest.build.loader import RunInput
    from app.modules.doc_ingest.profile import load_profile
    from tests.doc_ingest.chunk_helpers import MANIFEST, report

    path = ("2.3.5.1 MPG wiring diagram",)   # chunk `wiring`: nhãn OCR được vào từ khóa (luật 2026-11-13)
    doc = Doc()
    doc.add("heading", path[0], path=path)
    doc.add("text", "The MPG signal is connected via the CN3 port.", path=path)
    pic = doc.add("picture", path=path, image=True)
    run = RunInput(run_dir=tmp_path, report=report([1]), elements=doc.elements, tables={}, review=[],
                   figure_ocr={pic: ["CN3", "PUL1+", "X40", "FUL2-", "QFF54", "M1942 X50"]})
    [chunk] = build_chunks(run, MANIFEST, load_profile("qs_controller")).chunks
    verified = {lb.text: lb.verified for lb in chunk.figure_labels}
    assert verified == {"CN3": True, "PUL1+": True, "X40": True, "FUL2-": False, "QFF54": False,
                        "M1942 X50": True}
    assert {"CN3", "PUL1+", "X40", "M1942 X50"} <= set(chunk.keywords)
    assert not {"FUL2-", "QFF54"} & set(chunk.keywords) and "FUL2-" not in chunk.embed_text


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
