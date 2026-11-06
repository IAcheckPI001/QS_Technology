from app.modules.doc_ingest.geometry import BBox, overlap_ratio, parse_pages


def test_parse_pages_expands_ranges_and_deduplicates() -> None:
    assert parse_pages("9,11, 167-171,11") == [9, 11, 167, 168, 169, 170, 171]


def test_padded_is_clamped_to_page() -> None:
    box = BBox(5.0, 10.0, 590.0, 830.0).padded(12.0, width=595.0, height=842.0)
    assert box == BBox(0.0, 0.0, 595.0, 842.0)


def test_scaled_rounds_far_edge() -> None:
    assert BBox(10.4, 20.6, 30.5, 40.4).scaled(2.0) == (20, 41, 61, 81)


def test_overlap_ratio() -> None:
    target = BBox(0, 0, 100, 100)
    assert overlap_ratio(target, []) == 0.0
    assert overlap_ratio(target, [BBox(50, 0, 150, 100)]) == 0.5
    assert overlap_ratio(target, [BBox(-10, -10, 110, 110)]) == 1.0
    assert overlap_ratio(target, [BBox(200, 200, 300, 300)]) == 0.0
