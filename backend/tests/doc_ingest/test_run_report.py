"""CLI `run` + báo cáo HTML (BL-32): chạy từ Docling JSON đã lưu, không cần Docling/PDF."""
import json
from pathlib import Path

import pytest

from app.modules.doc_ingest import cli
from app.modules.doc_ingest.pipeline import step_states
from app.modules.doc_ingest.schemas.normalized import LogEntry, LogicalTable, NormalizedElement, ReviewItem
from app.modules.doc_ingest.schemas.run import RunReport
from tests.doc_ingest.f54 import F54_DIR
from tests.doc_ingest.synthetic import SynPage, param_rows


def _run(tmp_path: Path, *extra: str, raw_dir: Path = F54_DIR, run_id: str = "r1") -> Path:
    cli.main(["run", "--raw-dir", str(raw_dir), "--doc-id", "f54", "--out", str(tmp_path),
              "--run-id", run_id, *extra])
    return tmp_path / "f54" / run_id


@pytest.fixture(scope="module")
def f54_run(tmp_path_factory) -> Path:
    return _run(tmp_path_factory.mktemp("runs"), "--profile", "qs_controller")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_run_dir_follows_contract_layout(f54_run: Path) -> None:
    for name in ("raw/p167.docling.json", "raw/p167.words.json", "raw/p171.objects.json", "normalized/tables.jsonl",
                 "normalized/review_queue.jsonl", "normalized/normalization_log.jsonl",
                 "normalized/validation.jsonl", "normalized/elements.jsonl", "run_report.json",
                 "report/index.html"):
        assert (f54_run / name).is_file(), name
    tables = [LogicalTable.model_validate(t) for t in _jsonl(f54_run / "normalized/tables.jsonl")]
    [ReviewItem.model_validate(r) for r in _jsonl(f54_run / "normalized/review_queue.jsonl")]
    [LogEntry.model_validate(e) for e in _jsonl(f54_run / "normalized/normalization_log.jsonl")]
    report = RunReport.model_validate_json((f54_run / "run_report.json").read_text(encoding="utf-8"))
    assert len(tables) == report.stats.tables == 6
    assert report.profile_name == "qs_controller" and len(report.profile_hash) == 64
    assert report.steps == step_states()
    assert set(report.table_content_hashes) == {t.logical_table_id for t in tables}
    assert report.validation_summary == {"V-01": {"passed": 11, "failed": 0, "not_run": 0}}
    elements = [NormalizedElement.model_validate(e) for e in _jsonl(f54_run / "normalized/elements.jsonl")]
    assert sum(report.element_types.values()) == len(elements)
    assert report.printed_pages[167] == "160" and len(report.furniture_keys) == 4
    assert report.figures == {"picture": 5, "screenshot": 1, "watermark_candidate": 1, "caption_relinked": 1,
                              "rendered": 0}       # không có PDF: chỉ vùng crop, không render
    # T-08: fixture có trang 19 (4 cha × 2 con, GT-07)
    assert report.lists["children"] >= 8 and report.lists["orphans"] == 0 and report.lists["max_depth"] == 1
    # T-12 trên text (fixture trang 19: 4 định nghĩa M1920…M1923, 8 giá trị)
    assert report.refs["role_definition"] >= 4 and report.refs["role_value_option"] >= 8
    assert report.refs["list_param_mismatch"] == 0


def test_raw_dir_without_words_reports_v01_not_run(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    for page in (167, 168):
        name = f"p{page:03d}.docling.json"
        (raw / name).write_text((F54_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    run_dir = _run(tmp_path, raw_dir=raw)
    report = RunReport.model_validate_json((run_dir / "run_report.json").read_text(encoding="utf-8"))
    assert report.validation_summary == {"V-01": {"passed": 0, "failed": 0, "not_run": 2}}
    assert (run_dir / "normalized/validation.jsonl").read_text(encoding="utf-8") == ""
    assert "V-01 không chạy: thiếu words.json" in (run_dir / "report/index.html").read_text(encoding="utf-8")


def test_step_status_comes_from_existing_modules() -> None:
    status = {s.key: s.status for s in step_states()}
    assert status["s1_tables"] == "implemented" and status["parse"] == "implemented"
    assert status["s1_labels"] == "implemented"
    assert status["review"] == "partial" and status["validate"] == "partial"
    assert status["s0"] == "implemented"
    for key in ("s1_furniture", "s1_pages", "s1_sections", "s1_figures", "s1_lists", "s1_refs", "build"):
        assert status[key] == "implemented", key
    for key in ("facts", "publish"):
        assert status[key] == "not_implemented", key


def test_report_shows_steps_and_candidates_not_facts(f54_run: Path) -> None:
    page = (f54_run / "report/index.html").read_text(encoding="utf-8")
    for n in range(1, 7):
        assert f"f54:t{n:03d}" in page
    assert "T-05: cờ header Docling bị hạ thành dữ liệu" in page          # #4140 - #4147
    assert "ứng viên T-13 · not_available · F54 · “F54 controller” · chưa phải fact · chờ duyệt" in page
    assert "ứng viên T-13 · conditional · không khớp registry · “touch controller”" in page
    assert "Fact (parameter, applicability của fact): chưa triển khai (BL-17)." in page
    assert "V-01…V-04 kiểm bất biến</td><td><span class='badge st-partial'>một phần" in page
    assert "chỉ V-01 độ phủ text; V-02…V-04 chưa có" in page
    assert page.count("V-01 đạt · phủ") == 11 and "<td>text_coverage_gap</td>" not in page
    assert "Không có mục lục trong các trang đã chạy." in page


def test_page_subset_marks_tables_cut_by_range(tmp_path: Path) -> None:
    run_dir = _run(tmp_path, "--pages", "168-169")
    report = RunReport.model_validate_json((run_dir / "run_report.json").read_text(encoding="utf-8"))
    assert report.pages_selected == [168, 169]
    assert report.page_range_boundary["f54:t001"] == ["bảng ở đầu trang 168, trang 167 không được chọn"]
    assert "Có thể bị cắt bởi phạm vi trang" in (run_dir / "report/index.html").read_text(encoding="utf-8")
    full = _run(tmp_path, "--pages", "167-169", run_id="r2")
    tables = _jsonl(full / "normalized/tables.jsonl")
    assert len(tables[0]["segments"]) == 3       # đủ trang thì bảng 5.1 liền một khối


def test_normalized_output_is_deterministic(tmp_path: Path) -> None:
    first, second = _run(tmp_path, run_id="a"), _run(tmp_path, run_id="b")
    for name in ("tables.jsonl", "review_queue.jsonl", "normalization_log.jsonl", "validation.jsonl"):
        assert (first / "normalized" / name).read_bytes() == (second / "normalized" / name).read_bytes()


def test_report_escapes_document_text(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    page = SynPage(1).table([["Key", "Description", "Value"], ["#0001", "<script>alert(1)</script>", "1"],
                             *param_rows(2, 3)], top=100)
    (raw / "p001.docling.json").write_text(json.dumps(page.to_doc()), encoding="utf-8")
    html_text = (_run(tmp_path, raw_dir=raw) / "report/index.html").read_text(encoding="utf-8")
    assert "<script>" not in html_text and "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text


def test_run_requires_a_source(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["run", "--doc-id", "x", "--out", str(tmp_path)])


def test_report_shows_s0_profile_and_ocr_warning(tmp_path: Path) -> None:
    from datetime import datetime

    from app.modules.doc_ingest.pipeline import run_normalization, write_run
    from app.modules.doc_ingest.profile import load_profile
    from app.modules.doc_ingest.report.html_report import render_report
    from app.modules.doc_ingest.s0 import build_profile
    from app.modules.doc_ingest.schemas.run import DocumentProfile, RunSource

    profile = load_profile("default")
    measured = [{"page": 1, "text_chars": 0, "bad_char_ratio": 0.0, "rotation": 0, "bitmap_area_ratio": 0.6,
                 "vector_path_count": 900, "page_label": None}]
    s0 = build_profile(measured, profile.thresholds, "auto")
    page = SynPage(1).text("caption", "Figure 1-3. Front view", 100)
    result = run_normalization([page.to_doc()], "syn", profile, {1: []}, s0)
    report = write_run(tmp_path, result, doc_id="syn", run_id="x", created_at=datetime(2026, 11, 3),
                       source=RunSource(), timings={}, versions={})
    saved = DocumentProfile.model_validate_json((tmp_path / "raw/profile.json").read_text(encoding="utf-8"))
    assert saved == s0 == report.s0
    html_text = render_report(result, report, {})
    assert "1/1 trang không có hoặc hỏng text layer</b> (cả tài liệu được vẽ bằng hình)" in html_text
    assert "OCR · V-01 không có nguồn độc lập" in html_text
    assert "trang OCR: không có text layer độc lập để đối chiếu" in html_text


def test_report_without_s0_says_so(f54_run: Path) -> None:
    assert "Không có số đo S0" in (f54_run / "report/index.html").read_text(encoding="utf-8")


def test_report_shows_furniture_printed_pages_and_sections(f54_run: Path) -> None:
    page = (f54_run / "report/index.html").read_text(encoding="utf-8")
    assert "Chuỗi lặp được xác nhận" in page and "<code>page | #</code>" in page
    assert "Trang 167 · trang in 160" in page
    assert "PART 5 PARAMETERS TABLE › 5.1 Axis parameters" in page
    assert "Ngoại lệ cần xem" not in page          # F54: mọi header/footer đều lặp


def test_report_shows_figures_without_claiming_rendered_images(f54_run: Path) -> None:
    page = (f54_run / "report/index.html").read_text(encoding="utf-8")
    assert "<h2 id='figures'>Hình (T-09, T-10, T-11, T-14, T-18) · 7</h2>" in page
    assert "Không có ảnh crop (chạy không kèm PDF)" in page and "<img src=" not in page
    assert "Figure 5. F54 controller I/O ports<span class='muted'> (T-11 gắn lại)" in page
    assert "watermark_candidate ← picture" in page


def test_report_shows_list_tree(f54_run: Path) -> None:
    page = (f54_run / "report/index.html").read_text(encoding="utf-8")
    assert "<h2 id='lists'>List cha–con (T-08 v1)" in page and "<a href='#lists'>List</a>" in page
    assert "Lề x × marker của tài liệu" in page
    assert "o M1921 = 0 : Normally closed sensor (NC" in page
    assert "<h2 id='refs'>Mã parameter, ghi chú áp dụng trong text (T-12/T-13)</h2>" in page


def test_report_has_profile_fit(f54_run: Path) -> None:
    report = RunReport.model_validate_json((f54_run / "run_report.json").read_text(encoding="utf-8"))
    assert report.profile_fit is not None and report.profile_fit.param_tokens.get("M", 0) >= 12
    assert "ocr_majority" not in report.profile_fit.signals
    page = (f54_run / "report/index.html").read_text(encoding="utf-8")
    assert "<h2 id='fit'>Độ khớp profile với tài liệu</h2>" in page
