"""Ghép kết quả T-16, T-17/T-18, T-06, T-07, hình (T-09…T-11, T-14, T-19), bảng logic, T-08 và T-12/T-13 trên text thành
`NormalizedElement` (contract §2).

Chỉ gắn nhãn và tham chiếu, không sửa `text` (nguyên văn Docling/OCR).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.modules.doc_ingest.normalize.coverage import ElementCoverage
from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.normalize.figures import FigureRun
from app.modules.doc_ingest.normalize.lists import ListRun
from app.modules.doc_ingest.normalize.text_refs import TextRefRun
from app.modules.doc_ingest.normalize.sections import SectionInfo
from app.modules.doc_ingest.normalize.tables import TableRun
from app.modules.doc_ingest.schemas.normalized import (
    Box, NormalizedElement, NormalizedType, PrintedPage, RawRef, TableRef,
)

_BY_LABEL: dict[str, NormalizedType] = {
    "table": "table_segment", "document_index": "toc", "picture": "picture", "caption": "caption",
    "list_item": "list_item",
}


def _normalized_type(item: RawItem, section: SectionInfo | None, unsupported: set[str],
                     figures: FigureRun, toc_lines: set[str]) -> NormalizedType:
    if item.is_furniture:
        return "furniture"
    if item.parent_label == "picture" and item.label != "caption":
        return "figure_text"
    if item.element_id in toc_lines:
        return "toc"
    if item.element_id in figures.kinds:
        return figures.kinds[item.element_id]   # type: ignore[return-value]
    if item.element_id in unsupported:
        return "unsupported"
    if item.label in _BY_LABEL:
        return _BY_LABEL[item.label]
    if section is not None and section.normalized_type in ("heading", "label_heading"):
        return section.normalized_type  # type: ignore[return-value]
    return "text"


def build_elements(items: Sequence[RawItem], coverage: ElementCoverage, flags: Mapping[str, list[str]],
                   sections: Mapping[str, SectionInfo], printed: Mapping[int, PrintedPage],
                   tables: TableRun, figures: FigureRun, lists: ListRun | None = None,
                   refs: TextRefRun | None = None) -> list[NormalizedElement]:
    table_refs = {seg.element_id: TableRef(logical_table_id=t.logical_table_id, segment_index=i)
                  for t in tables.tables for i, seg in enumerate(t.segments)}
    reviewed = {r.element_id for r in tables.review} | {r.target for r in tables.review if r.target}
    lists = lists or ListRun()
    refs = refs or TextRefRun()
    unsupported = {i.element_id for i in coverage.unsupported}
    out = []
    for order, item in enumerate(items):
        item_flags = (list(flags.get(item.element_id, [])) + figures.flags.get(item.element_id, [])
                      + lists.flags.get(item.element_id, []))
        section = sections.get(item.element_id)
        caption = figures.captions.get(item.element_id)
        if section is not None:
            item_flags += section.flags
        b = item.bbox
        out.append(NormalizedElement(
            element_id=item.element_id,
            raw_ref=RawRef(file=f"raw/p{item.page:03d}.docling.json", self_ref=item.self_ref),
            pdf_page_index=item.page,
            printed_page=printed.get(item.page, PrintedPage()),
            content_layer="furniture" if item.is_furniture else "body",
            reading_order=order,
            source_element_type=item.label,
            normalized_type=_normalized_type(item, section, unsupported, figures, coverage.toc_lines),
            bbox=Box(x0=b.x0, y0=b.y0, x1=b.x1, y1=b.y1) if b is not None else None,
            text=item.text or None,
            section_path=section.section_path if section else [],
            section_path_source=section.section_path_source if section else "none",  # type: ignore[arg-type]
            label_heading=section.label_heading if section else None,
            parent_element_id=item.parent_id,
            list_info=lists.info.get(item.element_id),
            table_ref=table_refs.get(item.element_id),
            image=figures.images.get(item.element_id),
            caption_element_id=caption[0] if caption else None,
            caption_link=caption[1] if caption else None,
            duplicate_of=figures.duplicates.get(item.element_id),
            param_refs=refs.param_refs.get(item.element_id, []),
            applicability_candidates=refs.applicability.get(item.element_id, []),
            flags=item_flags,
            review_required=item.element_id in reviewed,
        ))
    return out
