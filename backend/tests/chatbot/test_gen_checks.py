"""Kiểm tự động câu trả lời của bước sinh (`evals/gen_checks.py`). Không cần DB hay LLM."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("gen_checks", ROOT / "evals" / "gen_checks.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gc = _load()

SOURCES = {
    "S1": "QS F54\n- Dimension: 220 x 140 x 30 (mm)\n- Cổng CN1: 24V, EMG",
    "S2": "Tham số #12010 đặt số xung; vít me bước 10 mm.",
}


def test_compact_and_numbers() -> None:
    assert gc.compact("220 × 140 x 30 mm") == "220x140x30mm"
    assert gc.compact("0,5 mm") == "0.5mm"
    assert gc.numbers_in("Bước 10 mm, 0,5 mm [S1]") == ["10", "0.5"]
    assert gc.codes_in("Cổng CN1 và #12010, M1920") == ["CN1", "#12010", "M1920"]


def test_facts_found() -> None:
    found, missing = gc.facts_found("Kích thước 220×140×30 mm [S1].", ["220 x 140 x 30", "24V", "re:cổng\\s+CN1"])
    assert found == ["220 x 140 x 30"] and missing == ["24V", "re:cổng\\s+CN1"]


def test_invalid_and_no_citation() -> None:
    assert gc.invalid_citations("Có [S1] và [S3, S2].", ["S1", "S2"]) == ["S3"]
    flags = gc.auto_flags("Bộ F54 có kích thước 220 x 140 x 30 mm.", "kích thước F54", SOURCES, ["220 x 140 x 30"])
    assert flags.no_citation and flags.needs_review and flags.fact_recall == 1.0


def test_unsupported_numbers_flagged() -> None:
    answer = "Kích thước 220 x 150 x 30 mm [S1]. Dùng tham số #12010 [S2]."
    flags = gc.auto_flags(answer, "kích thước?", SOURCES)
    assert "150" in flags.numbers_not_in_context
    assert flags.unsupported_sentences and flags.unsupported_sentences[0]["cited"] == ["S1"]
    assert "#12010" not in flags.numbers_not_in_context


def test_number_matches_whole_token() -> None:
    assert gc.tokens_unsupported("Có 22 cổng", ["có 220 cổng"]) == ["22"]
    assert gc.tokens_unsupported("Cổng CN1", ["Cổng cn1"]) == []


def test_user_numbers_are_not_flagged() -> None:
    flags = gc.auto_flags("Lỗ 220x130 không vừa vì cao 140 [S1].", "lỗ 220x130 lắp được không?", SOURCES)
    assert flags.numbers_not_in_context == []


def test_known_models_and_trailing_punctuation() -> None:
    assert gc.codes_in("Bộ F54. Xem CN1.") == ["F54", "CN1"]
    answer = "Chưa có tài liệu nào về đấu dây của bộ F54."
    flags = gc.auto_flags(answer, "Đấu dây báo lỗi servo?", {}, known=["F54"])
    assert flags.numbers_not_in_context == [] and flags.abstained
    assert gc.auto_flags("Bộ F54.", "Đấu dây?", {}).numbers_not_in_context == ["F54"]


def test_abstention_flags() -> None:
    flags = gc.auto_flags("Tài liệu hiện có không đề cập giá bộ F54.", "giá F54", SOURCES, expect_abstain=True)
    assert flags.abstained and not flags.abstain_mismatch
    bad = gc.auto_flags("Giá khoảng 10 triệu [S1].", "giá F54", SOURCES, expect_abstain=True)
    assert bad.abstain_mismatch and bad.needs_review
    over = gc.auto_flags("Không có thông tin về kích thước.", "kích thước F54", SOURCES, ["220"])
    assert over.abstain_mismatch
