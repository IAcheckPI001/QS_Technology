"""Fixture golden F54 (BL-02): đọc được không cần Docling/PDF và khớp số liệu P-1 assessment."""
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

F54 = Path(__file__).parent / "fixtures" / "docling" / "f54"
SPIKE_PAGES = [9, 11, 14, 18, 19, 40, 167, 168, 169, 170, 171]
PDF_SHA256 = "7cd0e69c1e94d41649fd361a47bd089279897b085f8c2b0b93c99dc1591bce21"
MAX_FIXTURE_BYTES = 3 * 1024 * 1024


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _doc(page: int) -> dict[str, Any]:
    return _load(F54 / f"p{page:03d}.docling.json")


def _header_texts(table: dict[str, Any]) -> list[str]:
    return [cell["text"] for cell in table["data"]["table_cells"] if cell.get("column_header")]


def _shape(table: dict[str, Any]) -> tuple[int, int]:
    return table["data"]["num_rows"], table["data"]["num_cols"]


def test_fixture_covers_spike_pages_within_size_limit() -> None:
    docs = sorted(F54.glob("p*.docling.json"))
    objects = sorted(F54.glob("p*.objects.json"))
    assert [int(path.name[1:4]) for path in docs] == SPIKE_PAGES
    assert [int(path.name[1:4]) for path in objects] == SPIKE_PAGES
    assert sum(path.stat().st_size for path in F54.iterdir()) <= MAX_FIXTURE_BYTES


def test_readme_pins_source_pdf() -> None:
    assert PDF_SHA256 in (F54 / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("page", SPIKE_PAGES)
def test_page_is_single_page_without_images(page: int) -> None:
    doc = _doc(page)
    assert list(doc["pages"]) == [str(page)]
    assert doc["pages"][str(page)]["image"] is None
    assert all(picture["image"] is None for picture in doc["pictures"])


def test_p011_table_is_port_functions() -> None:
    (table,) = _doc(11)["tables"]
    assert _shape(table) == (11, 2)
    assert _header_texts(table) == ["Port", "Functions"]


def test_p168_header_flag_sits_on_first_data_row() -> None:
    (table,) = _doc(168)["tables"]
    assert _shape(table) == (32, 4)
    assert _header_texts(table)[:2] == ["#4140 - #4147", "Axis type"]


def test_p169_continuation_table_lost_empty_column() -> None:
    continuation, spindle = _doc(169)["tables"]
    assert _shape(continuation) == (17, 3)
    assert _header_texts(continuation) == []
    assert _shape(spindle) == (9, 4)


def test_p018_screenshot_is_empty_table() -> None:
    (table,) = _doc(18)["tables"]
    assert _shape(table) == (0, 0)


def test_watermark_bitmap_repeats_on_pages() -> None:
    sizes: Counter[tuple[int, int]] = Counter()
    for page in SPIKE_PAGES:
        objects = _load(F54 / f"p{page:03d}.objects.json")
        assert objects["pdf_page_index"] == page
        sizes.update({(b["px_w"], b["px_h"], b["hash"]) for b in objects["bitmaps"]})
    assert sizes[(671, 427, "20953f60866f6155")] == len(SPIKE_PAGES)    # cùng nội dung mọi trang (T-10)


def test_bitmap_inside_form_xobject_uses_form_bounds() -> None:
    """F54 trang 18: ảnh chụp màn hình Figure 15 nằm trong Form XObject; pdfium báo bounds
    theo hệ tọa độ form (0,720–72,792) nếu không quy về form cấp trang."""
    boxes = [(round(b["x0"]), round(b["y0"]), round(b["x1"]), round(b["y1"]))
             for b in _load(F54 / "p018.objects.json")["bitmaps"]]
    assert (141, 492, 500, 695) in boxes and (0, 720, 72, 792) not in boxes


@pytest.mark.requires_docling
@pytest.mark.parametrize("page", SPIKE_PAGES)
def test_fixture_validates_as_docling_document(page: int) -> None:
    from docling_core.types.doc import DoclingDocument

    doc = DoclingDocument.model_validate(_doc(page))
    assert page in doc.pages
