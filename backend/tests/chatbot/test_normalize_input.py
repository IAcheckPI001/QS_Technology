




from app.util.normalize import (
    normalize_nfc,
    make_casefold_view,
    make_accent_folded_view,
    normalize_for_detection,
)


def test_nfc_composes_unicode():
    assert normalize_nfc("a\u0301") == "á"


def test_casefold_is_case_insensitive():
    assert make_casefold_view("AI HƯỚNG DẪN") == "ai hướng dẫn"


def test_accent_fold_handles_vietnamese_d():
    assert make_accent_folded_view("Đặng Thị Hương") == "dang thi huong"


def test_detection_views_preserve_punctuation():
    result = normalize_for_detection("Xin, HƯỚNG dẫn!")

    assert result.original_text == "Xin, HƯỚNG dẫn!"
    assert result.casefolded_text == "xin, hướng dẫn!"
    assert result.accent_folded_text == "xin, huong dan!"