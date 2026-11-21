"""Bậc 0 (2026-11-20): I-55 toàn vẹn text layer, I-59 cột chữ cạnh ảnh chụp màn hình, I-54 V-01, header không rõ, CQ."""
from __future__ import annotations

from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.pipeline import run_normalization
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.s0 import build_profile, decide, hash_code_counts, s0_review
from app.modules.doc_ingest.schemas.normalized import NormalizedElement
from app.modules.doc_ingest.schemas.profile import Thresholds
from tests.doc_ingest.synthetic import SynPage

PROFILE = load_profile("qs_controller")
TH = Thresholds()


# ------------------------------------------------------------------ I-55
def _metrics(text: str, chars: int = 900) -> dict[str, object]:
    codes, damaged = hash_code_counts(text)
    return {"page": 1, "text_chars": chars, "bad_char_ratio": 0.0, "rotation": 0, "bitmap_area_ratio": 0.2,
            "vector_path_count": 5, "page_label": None, "hash_codes": codes, "hash_damaged": damaged}


def test_hash_code_counts_separates_valid_and_damaged_codes() -> None:
    assert hash_code_counts("#8090 - #8097 Axis dir (0.1us) #12000") == (3, 0)
    assert hash_code_counts("# 9 - # 97 Axis dir ( . us) # ,  # #") == (5, 5)
    assert hash_code_counts("no codes here") == (0, 0)
    assert hash_code_counts("#8090 and # 9") == (2, 1)


def test_damaged_text_layer_is_poor_and_ocr_applied() -> None:
    damaged = "\n".join(f"# {i % 9} - # {i % 97}" for i in range(20))
    page = decide(_metrics(damaged), TH)
    assert page.text_layer == "poor" and page.ocr is True and (page.hash_codes, page.hash_damaged) == (40, 40)
    profile = build_profile([_metrics(damaged)], TH, "auto")
    assert profile.pages[0].ocr_applied is True
    rec = Recorder()
    s0_review(profile, "doc", rec)
    [item] = rec.review
    assert item.code == "ocr_required" and "lack digits" in item.detail


def test_healthy_or_few_codes_stay_text_layer() -> None:
    healthy = "\n".join(f"#{8000 + i} - #{8007 + i} Axis" for i in range(20))
    assert decide(_metrics(healthy), TH).text_layer == "ok"
    few = "# 9 - # 97 and #8090"        # dưới `text_integrity_min_codes`: không đủ bằng chứng
    assert decide(_metrics(few), TH).text_layer == "ok"
    mostly_ok = "\n".join([f"#{8000 + i}" for i in range(9)] + ["# 9"])   # 10% hỏng ≤ 30%
    assert decide(_metrics(mostly_ok), TH).text_layer == "ok"


# ------------------------------------------------------------------ I-54
def test_v01_tokens_normalise_ordinals_garbled_chars_and_toc_leaders() -> None:
    from app.modules.doc_ingest.validate.coverage import reference_tokens, tokens

    assert tokens("federate 1 st") == tokens("federate 1st") == ["federate", "1st"]
    assert tokens("(1 st ,2 nd ,3 rd )") == tokens("(1st ,2nd ,3rd )")
    assert tokens("1 st") != tokens("1 sta")                                  # chỉ ghép đúng hậu tố thứ tự
    assert tokens("D￾driver") == tokens("Ddriver")
    assert reference_tokens("D￾driver") == []                        # từ text layer có U+FFFE: không tin cậy
    assert reference_tokens("controller.................................3") == []   # dòng mục lục
    assert reference_tokens("controller…………………26") == []
    assert reference_tokens("limit") == ["limit"]


# ------------------------------------------------------------------ I-59
LEFT, RIGHT = (36.0, 300.0), (339.0, 568.0)


def _ocr_page() -> SynPage:
    """6AH tr.80: picture phủ cả hai cột; cột trái là ảnh chụp màn hình (đám nhãn ngắn), cột phải là chữ thủ tục."""
    page = SynPage(80).text("section_header", "3.8.1 PARAMETER SETTING STEPS", 92)
    pic = page.picture(104, 677, x=(36.0, 576.0))
    page.text("section_header", "Memo", 110, parent=pic, x=RIGHT)
    page.text("text", "Model: ASTRO 6AH, ASTRO 6AH, Astro 6A", 125, parent=pic, x=RIGHT)
    page.text("section_header", "Step 1:", 150, parent=pic, x=RIGHT)
    page.text("text", "Select parameter type such as: Axis, Spindle, Hardware, Macro.", 180, parent=pic, x=RIGHT)
    page.text("section_header", "Step 2:", 390, parent=pic, x=RIGHT)
    page.text("text", "Press PAGE DOWN button to scroll the page down and find the parameter.", 415, parent=pic, x=RIGHT)
    for i, label in enumerate(["Addr", "+0", "+1", "AX1.ENA", "AX2.ENA", "General", "Axis", "Spindle"]):
        page.text("text", label, 170 + i * 12, parent=pic, x=(80.0 + (i % 4) * 30, 100.0 + (i % 4) * 30))
    return page


def _all(result, text: str) -> list[NormalizedElement]:
    return [e for e in result.normalized or [] if e.text == text]


def test_column_text_beside_screenshot_is_released_on_ocr_page() -> None:
    from tests.doc_ingest.test_text_frames import _s0

    result = run_normalization([_ocr_page().to_doc()], "6ah", PROFILE, s0=_s0(80, ocr=True))
    for text in ("Step 1:", "Select parameter type such as: Axis, Spindle, Hardware, Macro.", "Step 2:"):
        [e] = _all(result, text)
        assert e.normalized_type != "figure_text" and e.parent_element_id is None, text
        assert "figure_column_released" in e.flags
    # đám nhãn của ảnh chụp màn hình vẫn là chữ trong hình
    [label] = _all(result, "AX1.ENA")
    assert label.normalized_type == "figure_text" and label.parent_element_id is not None


def test_picture_without_a_column_gap_is_untouched() -> None:
    """Sơ đồ chỉ có một cụm chữ (không dải trắng ≥ 24 pt): giữ nguyên, không trả về thân."""
    from tests.doc_ingest.test_text_frames import _s0

    page = SynPage(81).text("section_header", "3.9 Wiring", 80)
    pic = page.picture(100, 600)
    for i in range(10):
        page.text("text", f"Select the terminal number {i} on the board", 120 + i * 20, parent=pic, x=(90.0, 400.0))
    result = run_normalization([page.to_doc()], "6ah", PROFILE, s0=_s0(81, ocr=True))
    assert not [e for e in result.normalized or [] if "figure_column_released" in e.flags]
