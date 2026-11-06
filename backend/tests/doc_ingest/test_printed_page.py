"""T-06 số trang in: /PageLabels, chuỗi số trong furniture; không bao giờ suy từ offset."""
from pathlib import Path

from app.modules.doc_ingest.pipeline import load_raw_dir, load_s0, run_normalization
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.s0 import build_profile
from tests.doc_ingest.f54 import f54_docs
from tests.doc_ingest.synthetic import SynPage

DEFAULT = load_profile("default")
F86_DIR = Path(__file__).resolve().parent / "fixtures" / "docling" / "f86_ocr"


def _footers(printed: dict[int, str]) -> list[SynPage]:
    return [SynPage(page).text("text", "Body", 300).text("page_footer", text, 760, x=(514, 560))
            for page, text in printed.items()]


def _printed(printed: dict[int, str], s0=None) -> tuple[dict[int, str | None], list[str]]:
    result = run_normalization([p.to_doc() for p in _footers(printed)], "syn", DEFAULT, None, s0)
    return ({p: v.value for p, v in (result.printed or {}).items()},
            [r.code for r in result.tables.review if r.code == "printed_page_conflict"])


def test_page_numbers_in_footer_sequence() -> None:
    values, conflicts = _printed({p: f"PAGE {p - 2}" for p in range(7, 12)})
    assert values == {7: "5", 8: "6", 9: "7", 10: "8", 11: "9"} and conflicts == []


def test_unreadable_number_stays_null_without_interpolation() -> None:
    values, conflicts = _printed({5: "PAGE 3", 6: "PAGEO", 7: "PAGE 5", 8: "PAGE 6"})
    assert values == {5: "3", 6: None, 7: "5", 8: "6"} and conflicts == []


def test_number_off_the_sequence_is_null_and_flagged() -> None:
    values, conflicts = _printed({5: "PAGE 3", 6: "PAGE 4", 7: "PAGE 9", 8: "PAGE 6", 9: "PAGE 7"})
    assert values == {5: "3", 6: "4", 7: None, 8: "6", 9: "7"} and conflicts == ["printed_page_conflict"]


def test_fewer_pages_than_minimum_gives_null() -> None:
    values, _ = _printed({5: "PAGE 3", 6: "PAGE 4"})
    assert values == {5: None, 6: None}


def test_constant_numbers_are_not_page_numbers() -> None:
    values, _ = _printed({p: "Model F54 Rev 2" for p in range(1, 5)})
    assert set(values.values()) == {None}


def test_pdf_page_labels_take_priority() -> None:
    metrics = [{"page": p, "text_chars": 500, "bad_char_ratio": 0.0, "rotation": 0, "bitmap_area_ratio": 0.0,
                "vector_path_count": 0, "page_label": "iv" if p == 7 else None} for p in range(7, 10)]
    s0 = build_profile(metrics, DEFAULT.thresholds, "auto")
    values, _ = _printed({p: f"PAGE {p - 2}" for p in range(7, 10)}, s0)
    assert values == {7: "iv", 8: "6", 9: "7"}


def test_f54_page_footer_gives_printed_pages() -> None:
    result = run_normalization(f54_docs(), "f54", DEFAULT)
    printed = result.printed or {}
    assert {p: printed[p].value for p in (9, 14, 167, 171)} == {9: "2", 14: "7", 167: "160", 171: "164"}
    assert {v.source for v in printed.values()} == {"furniture_sequence"}


def test_f86_ocr_footer_including_merged_lines() -> None:
    result = run_normalization(load_raw_dir(F86_DIR), "f86", DEFAULT, None, load_s0(F86_DIR))
    printed = {p: v.value for p, v in (result.printed or {}).items()}
    assert printed == {p: str(p - 2) for p in range(5, 18)}     # trang 6, 11: footer OCR gộp hai dòng
