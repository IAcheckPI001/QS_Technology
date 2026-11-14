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
    assert len(chunks) == 37 and result.unverified == []
    assert Counter(c.chunk_type for c in chunks) == {"overview": 14, "spec": 7, "table": 16}
    assert len({c.chunk_key for c in chunks}) == 37 and all(c.chunk_key.startswith(f"{DOC_ID}:C") for c in chunks)
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
