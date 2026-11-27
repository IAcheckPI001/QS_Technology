"""Nhánh nguồn biên soạn có duyệt (`doc_ingest/curated`): schema, kiểm chữ in, sinh chunk bám sát PDF, cổng duyệt."""

from __future__ import annotations

from collections import Counter

import pytest

from app.modules.doc_ingest.curated import check as ck
from app.modules.doc_ingest.curated.build import DOC_ID, build_chunks, review_template
from app.modules.doc_ingest.curated.schema import load_matrix, load_products
from app.modules.doc_ingest.export.doc_chunks_v2 import ApprovalContext, export_rows, review_status

MODELS = {"F54", "F86", "F10T", "10S", "6AH", "6AV", "10i"}


@pytest.fixture(scope="module")
def products():
    return load_products()


@pytest.fixture(scope="module")
def matrix():
    return load_matrix()


def _by_title(chunks, title):
    return next(c for c in chunks if c.section_title == title)


def test_curated_data_loads_and_is_reviewed(products, matrix):
    assert {p.model for p in products} == MODELS
    assert len(matrix.rows) == 43 and set(matrix.models) == MODELS
    report = ck.check(products, matrix)
    assert report.unverified == [] and report.matrix_mismatch == []


def test_build_chunks_follow_pdf_sections(products, matrix):
    result = build_chunks(products, matrix, "2026-11-14")
    chunks = result.chunks
    # Phương án C: 37 chunk theo mục in trên trang + 35 lát bảng theo model (7 model × 5 lát) nối tiếp ở cuối.
    assert len(chunks) == 72 and result.unverified == []
    assert Counter(c.chunk_type for c in chunks) == {"overview": 14, "spec": 7, "table": 51}
    assert len({c.chunk_key for c in chunks}) == 72 and all(c.chunk_key.startswith(f"{DOC_ID}:C") for c in chunks)
    assert [c.chunk_key for c in chunks][:37] == [f"{DOC_ID}:C{i:04d}" for i in range(37)]
    assert len({tuple(c.section_path) for c in chunks}) == 72      # section_path duy nhất (hai bảng không còn trùng tên)
    assert all(c.source == "manual" and c.domain == "product_catalog" and c.scopes == [] for c in chunks)
    rows, errors = export_rows(chunks, ApprovalContext(gate_2b_final=False))
    assert errors == [] and {r["review_status"] for r in rows} == {"draft"}

    f54 = _by_title(chunks, "QS F54 › THÔNG SỐ KỸ THUẬT (SPECIFICATIONS)")
    assert f54.product_models == ["F54"] and f54.page_start == 8
    lines = f54.content.split("\n")
    assert lines[:3] == ["QS F54", "THÔNG SỐ KỸ THUẬT (SPECIFICATIONS)", "Phần mềm (Software)"]
    # C-01: dòng gộp in trên trang được tách vì hai giá trị khác nhau
    assert "- Backlash compensation: Yes" in lines and "- Pitch error compensation: No" in lines
    assert [d.code for d in f54.curated_decisions] == ["C-01"]
    # Cùng giá trị → giữ đúng dòng gộp như in
    assert "- Backlash/Pitch error compensation: Yes" in _by_title(
        chunks, "QS ASTRO 6AV › THÔNG SỐ KỸ THUẬT (SPECIFICATIONS)").content.split("\n")


def test_decisions_replace_printed_values_and_are_traced(products, matrix):
    chunks = build_chunks(products, matrix, "2026-11-14").chunks
    spec = _by_title(chunks, "QS ASTRO 6AH › THÔNG SỐ KỸ THUẬT (SPECIFICATIONS)")
    assert "- Control system: Closed loop" in spec.content
    assert "- Look-Ahead: 1000 lines" in spec.content
    codes = {d.code: d for d in spec.curated_decisions}
    assert set(codes) == {"C-02", "C-03", "C-04", "C-05"}
    assert codes["C-02"].page_value == "Open loop" and codes["C-03"].page_value == "500 lines"
    rows, _ = export_rows([spec], ApprovalContext(gate_2b_final=False))
    assert {d["code"] for d in rows[0]["metadata"]["curated_decisions"]} == set(codes)


def test_selection_table_keeps_printed_columns(products, matrix):
    chunks = build_chunks(products, matrix, "2026-11-14").chunks
    general = [c for c in chunks if c.chunk_type == "table" and c.section_path[-1] == "General"]
    assert [c.product_models for c in general] == [["F54", "F86", "F10T", "10S"], ["6AV", "6AH", "10i"]]
    assert "| Specification | F54 | F86 | F10T | ASTRO-10S |" in general[0].content
    assert "| Specification | ASTRO 6AV/H | ASTRO 10i |" in general[1].content
    assert "6AV: 220 x 460 x 42 (mm); 6AH: 325 x 285 x 42 (mm)" in general[1].content
    multi = next(c for c in chunks if c.chunk_type == "table" and c.page_start == 6
                 and c.section_path[-1] == "Multi axis control mode (Optional)")
    assert "| RTCP | ✗ | (Option) | (Option) | (Option) |" in multi.content     # 10S: C-09
    assert {(d.code, d.model) for d in multi.curated_decisions} == {("C-09", "10S")}


def _table_rows(content: str) -> dict[str, list[str]]:
    """Hàng bảng markdown → {nhãn: [ô theo cột]} (bỏ dòng tiêu đề và phân cách)."""
    rows: dict[str, list[str]] = {}
    for line in content.split("\n"):
        if line.startswith("| ") and not line.startswith("| Specification") and not line.startswith("|---"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows[cells[0]] = cells[1:]
    return rows


def _header(content: str) -> list[str]:
    line = next(x for x in content.split("\n") if x.startswith("| Specification"))
    return [c.strip() for c in line.strip("|").split("|")][1:]


def test_model_slices_are_faithful_column_extracts(products, matrix):
    chunks = build_chunks(products, matrix, "2026-11-14").chunks
    slices = [c for c in chunks if len(c.section_path) == 4]
    assert len(slices) == 35 and all(len(c.product_models) == 1 and c.chunk_type == "table" for c in slices)
    assert [c.chunk_key for c in slices][0] == f"{DOC_ID}:C0037"
    assert Counter(c.product_models[0] for c in slices) == {m: 5 for m in MODELS}
    tables = [c for c in chunks if c.chunk_type == "table" and len(c.section_path) == 3]
    assert len(tables) == 16
    seen_rows = 0
    for chunk in slices:
        model = chunk.product_models[0]
        column = matrix.models[model].column
        assert _header(chunk.content) == [column]
        for label, cells in _table_rows(chunk.content).items():
            # cùng nhãn hàng ở bảng gốc cùng trang: ô của cột model phải giống hệt
            original = next(t for t in tables if t.page_start == chunk.page_start and label in _table_rows(t.content))
            expected = _table_rows(original.content)[label][_header(original.content).index(column)]
            if f"{model}: " in expected:      # ô gộp theo model của cột dùng chung (hàng Dimension của 6AV/6AH)
                expected = next(p.split(": ", 1)[1] for p in expected.split("; ") if p.startswith(f"{model}: "))
            assert cells == [expected], (model, label)
            seen_rows += 1
    assert seen_rows == 43 * len(MODELS)                   # mọi hàng của mọi model có đúng một lát


def test_slice_search_text_has_words_not_symbols_and_content_stays_printed(products, matrix):
    chunks = build_chunks(products, matrix, "2026-11-14").chunks
    f54 = next(c for c in chunks if c.section_path == ["MOTION CONTROLLER", "Selection table", "F54", "Vận hành và quản lý dao"])
    assert "| Tool-life management | ✗ |" in f54.content and "có" not in f54.content.lower().replace("coordinate", "")
    assert "Tóm tắt:" in f54.embed_text and "Quản lý tuổi thọ dao (Tool-life management): không" in f54.embed_text
    assert "✗" not in f54.embed_text.split("---")[0]
    six = next(c for c in chunks if c.section_path[-2:] == ["6AH", "Phần cứng"])
    assert "(cột in chung cho 6AV và 6AH)" in six.embed_text and "| Specification | ASTRO 6AV/H |" in six.content
    general_table = next(c for c in chunks if c.section_path[-1] == "General" and c.page_start == 6)
    assert "Tóm tắt:" not in general_table.embed_text          # hàng toàn chữ/số không cần đổi ký hiệu
    tool = next(c for c in chunks if c.section_path[-1] == "Tool Manager")
    assert "F54 không" in tool.embed_text and tool.section_path[1].startswith("Selection table (F54, F86, F10T, 10S)")
    assert any(c.section_path[-1] == "Builder Support" for c in chunks) and not any(c.section_path[-1] == "Builder Supp" for c in chunks)
    assert "| Intergrate PLC |" in next(c for c in chunks if c.section_path[-1] == "Builder Support").content   # chữ in giữ nguyên


def test_slice_decisions_and_attributes(products, matrix):
    chunks = build_chunks(products, matrix, "2026-11-14").chunks
    multi = next(c for c in chunks if c.section_path[-2:] == ["10S", "Bù và đa trục"])
    assert {(d.code, d.key) for d in multi.curated_decisions} == {("C-09", "dwo"), ("C-09", "twp"), ("C-09", "rtcp")}
    assert "| RTCP | (Option) |" in multi.content and "rtcp" in multi.spec_attributes
    general = next(c for c in chunks if c.section_path[-2:] == ["F54", "Tổng quát"])
    assert {"dimension", "max_axis", "spindle", "look_ahead"} <= set(general.spec_attributes)


def test_summary_chunk_keeps_only_unique_lines_and_pages(products, matrix):
    chunks = build_chunks(products, matrix, "2026-11-14").chunks
    f54 = next(c for c in chunks if c.section_path[-1] == "Trọn bộ hệ thống và tùy chọn" and c.product_models == ["F54"])
    assert not any(line.startswith(("- Dimension:", "- Monitor size:", "- Control interface:", "- I/O integrated:")) for line in f54.content.split("\n"))
    assert "- Max 4 axis" not in f54.content and "- Open loop control" not in f54.content
    assert "MODEL: F54" in f54.content and "- Servo drive" in f54.content
    assert f54.page_start == f54.page_end == 19 and "source_pages:4,19" in f54.flags
    ten_i = next(c for c in chunks if c.section_path[-1] == "Trọn bộ hệ thống và tùy chọn" and c.product_models == ["10i"])
    assert "- High speed RTCP (Option)" in ten_i.content and "- Premium anodized aluminum keys" in ten_i.content


def test_without_slices_keeps_the_first_37_chunks_identical(products, matrix):
    """Biến thể B (`--no-slices`): đúng 37 chunk đầu của phương án C, không có lát theo model."""
    full = build_chunks(products, matrix, "2026-11-14").chunks
    plain = build_chunks(products, matrix, "2026-11-14", model_slices=False).chunks
    assert len(plain) == 37 and not any(len(c.section_path) == 4 for c in plain)
    assert [(c.chunk_key, c.content_hash, c.embed_text) for c in plain] == [
        (c.chunk_key, c.content_hash, c.embed_text) for c in full[:37]]


def test_unchanged_chunks_keep_hash_and_key(products, matrix):
    """Chunk trang riêng model không đổi `content` → hash cũ còn nguyên (verdict `ok` giữ được)."""
    chunks = build_chunks(products, matrix, "2026-11-14").chunks
    assert chunks[0].chunk_key == f"{DOC_ID}:C0000"
    assert chunks[0].content_hash == "7472976e81fa3a1fa210bd9c8b4f63a71d731d22829411780d3e59f7c7aa358b"
    assert chunks[1].content_hash == "61cc763933282baacf4cd987adafcd24d823bbe194a8486a64b6a2f0634e83fb"


def test_unverified_values_are_left_out(products, matrix):
    sheet = next(p for p in products if p.model == "F86")
    specs = [s.model_copy(update={"verified": False}) if s.key == "look_ahead" else s for s in sheet.specs]
    changed = [sheet.model_copy(update={"specs": specs}) if p is sheet else p for p in products]
    result = build_chunks(changed, matrix, "2026-11-14")
    assert result.unverified == ["F86/look_ahead"]
    assert "Look-Ahead" not in _by_title(result.chunks, "QS F86 › THÔNG SỐ KỸ THUẬT (SPECIFICATIONS)").content
    assert "F86/look_ahead" in ck.check(changed, matrix).unverified


def test_vietnamese_labels_only_proposed_by_default(products, matrix):
    plain = build_chunks(products, matrix, "2026-11-14")
    spec = _by_title(plain.chunks, "QS F54 › THÔNG SỐ KỸ THUẬT (SPECIFICATIONS)")
    assert "Hệ thống điều khiển" not in spec.keywords
    assert "Hệ thống điều khiển" in plain.proposed_keywords_vi[spec.chunk_key]
    with_vi = build_chunks(products, matrix, "2026-11-14", vi_keywords=True)
    assert "Hệ thống điều khiển" in _by_title(with_vi.chunks, spec.section_title).keywords


def test_check_flags_text_missing_and_matrix_mismatch(products, matrix):
    report = ck.check(products, matrix, pages={})
    assert report.text_missing and not report.passed
    row = next(r for r in matrix.rows if r.key == "look_ahead")
    values = {**row.values, "F54": "999"}
    rows = [r.model_copy(update={"values": values}) if r is row else r for r in matrix.rows]
    bad = matrix.model_copy(update={"rows": rows})
    assert any(m.startswith("F54/look_ahead") for m in ck.check(products, bad).matrix_mismatch)


def test_text_status_levels():
    page = ck.norm("Standard: 6 Optional: 8 Max.Spindle Simultaneous Control")
    assert ck.text_status("Max.Spindle Simultaneous Control", page) == "ok"
    assert ck.text_status("Optional: 8, Standard: 6", page) == "reordered"
    assert ck.text_status("Profinet", page) == "missing"


def test_content_check_finds_words_not_in_pdf(products, matrix):
    chunk = build_chunks(products, matrix, "2026-11-14").chunks[0]
    pages = {chunk.page_start: ck.norm(chunk.content)}
    assert ck.content_issues([chunk], pages) == []
    invented = chunk.model_copy(update={"content": chunk.content + "\n- Hỗ trợ Profinet"})
    issues = ck.content_issues([invented], pages)
    assert len(issues) == 1 and "profinet" in issues[0]


def test_manual_chunk_approval_needs_reviewed_source_and_ok_verdict(products, matrix):
    chunk = build_chunks(products, matrix, "2026-11-14").chunks[0]
    review = review_template([chunk], None)
    assert review_status(chunk, ApprovalContext(gate_2b_final=False, curated_verified=True)) == "draft"
    ok = {chunk.chunk_key: chunk.content_hash}
    assert review_status(chunk, ApprovalContext(gate_2b_final=False, ok_hashes=ok, curated_verified=True)) == "approved"
    assert review_status(chunk, ApprovalContext(gate_2b_final=False, ok_hashes=ok, curated_verified=False)) == "draft"
    # Verdict cũ giữ khi content_hash không đổi
    review.reviews[0].verdict = "ok"
    assert review_template([chunk], review).reviews[0].verdict == "ok"
    changed = chunk.model_copy(update={"content_hash": "x"})
    assert review_template([changed], review).reviews[0].verdict == "pending"
