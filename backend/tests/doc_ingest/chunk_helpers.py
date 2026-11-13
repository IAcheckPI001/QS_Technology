"""Dựng NormalizedElement/RunInput tổng hợp cho test chunk builder (không qua Docling)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.modules.doc_ingest.build.builder import BuildResult, build_chunks
from app.modules.doc_ingest.build.loader import RunInput
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.manifest import DocManifest
from app.modules.doc_ingest.schemas.normalized import (
    Box, Cell, Column, ImageInfo, ListInfo, LogicalTable, NormalizedElement, PrintedPage, RawRef, ReviewItem, Row,
    Segment, TableRef,
)
from app.modules.doc_ingest.schemas.run import DocumentProfile, PageProfile, RunReport, RunSource, RunStats
from app.modules.doc_ingest.technical_refs.params import ParamRef, TextParamRef

MANIFEST = DocManifest(doc_id="syn_manual_v1", run_doc_ids=["syn"], doc_type="user_guide", doc_title="Syn Manual",
                       doc_version="v1", product_models=["F54"], lang="en", default_scopes=["operation"],
                       scope_rules=[{"match": "(?i)wiring", "scopes": ["installation"]}], storage_bucket="syn-docs")


class Doc:
    """Thêm phần tử theo thứ tự đọc; `page` mặc định 1."""

    def __init__(self) -> None:
        self.elements: list[NormalizedElement] = []
        self.counter = 0

    def add(self, kind: str, text: str | None = None, *, path: tuple[str, ...] = ("1 Intro",), page: int = 1,
            label: str | None = None, depth: int | None = None, parent: str | None = None, marker: str | None = None,
            refs: list[TextParamRef] | None = None, caption: str | None = None, owner: str | None = None,
            image: bool = False, duplicate_of: str | None = None, layer: str = "body",
            table: str | None = None) -> str:
        self.counter += 1
        eid = f"syn:p{page:03d}:e{self.counter:03d}"
        self.elements.append(NormalizedElement(
            element_id=eid, raw_ref=RawRef(file="x", self_ref=f"#/{self.counter}"), pdf_page_index=page,
            printed_page=PrintedPage(value=str(page), source="page_labels"), content_layer=layer,  # type: ignore[arg-type]
            reading_order=self.counter, source_element_type=kind, normalized_type=kind,  # type: ignore[arg-type]
            bbox=Box(x0=0, y0=0, x1=10, y1=10), text=text, section_path=list(path), label_heading=label,
            parent_element_id=owner,
            list_info=ListInfo(indent_x=0, depth=depth, parent_element_id=parent, marker=marker)
            if depth is not None else None,
            image=ImageInfo(original_path=f"normalized/images/{eid.replace(':', '_')}/original.png",
                            crop_bbox=Box(x0=0, y0=0, x1=10, y1=10), crop_sources=["docling"]) if image else None,
            caption_element_id=caption, duplicate_of=duplicate_of, param_refs=refs or [],
            table_ref=TableRef(logical_table_id=table, segment_index=0) if table else None))
        return eid

    def link_caption(self, owner: str, caption: str) -> None:
        self.elements = [e.model_copy(update={"caption_element_id": caption}) if e.element_id == owner else e
                         for e in self.elements]


def ref(label: str, role: str, prefix: str = "M") -> TextParamRef:
    code = int(label[len(prefix):])
    return TextParamRef(prefix=prefix, kind="single", codes=[code], label=label, start=0, end=len(label),
                        role=role)  # type: ignore[arg-type]


def report(pages: list[int], ocr: set[int] = frozenset()) -> RunReport:  # type: ignore[assignment]
    s0 = DocumentProfile(ocr_mode="auto", page_labels_present=True, pages=[
        PageProfile(page=p, text_chars=100, bad_char_ratio=0, rotation=0, bitmap_area_ratio=0, vector_path_count=0,
                    text_layer="missing" if p in ocr else "ok", ocr=p in ocr, ocr_applied=p in ocr) for p in pages])
    return RunReport(doc_id="syn", run_id="r1", created_at=datetime(2026, 11, 9), source=RunSource(),
                     pages_selected=pages, profile_name="qs_controller", profile_hash="x", steps=[],
                     stats=RunStats(tables=0, rows=0, review_items=0, review_by_code={}, blocking_by_step={}),
                     table_content_hashes={}, page_range_boundary={}, s0=s0)


def logical_table(segment_id: str, rows: list[list[str]], headers: tuple[str, ...] = ("Parameter", "Description"),
                  table_id: str = "syn:t001") -> LogicalTable:
    """Bảng logic một segment; `rows[i][j] == ""` là ô trống. Ô cột 0 dạng `#123` thành `param_ref`."""
    seg = Segment(element_id=segment_id, pdf_page_index=1, bbox=Box(x0=0, y0=0, x1=1, y1=1),
                  num_cols_docling=len(headers))
    cols = [Column(index=i, header_text=h, x_min=i, x_max=i + 1, header_source="detected")
            for i, h in enumerate(headers)]

    def cells(values: list[str]) -> list[Cell]:
        return [Cell(col=i, text=v, bbox=None, raw_cell_ref=None, docling_col=i, docling_header=False,
                     assigned_by="bbox") for i, v in enumerate(values)]

    out = [Row(row_id="r0", segment=0, is_header=True, cells=cells(list(headers)))]
    for i, values in enumerate(rows, start=1):
        code = values[0]
        param = (ParamRef(prefix="#", kind="single", codes=[int(code[1:])], label=code)
                 if code.startswith("#") and code[1:].isdigit() else None)
        out.append(Row(row_id=f"r{i}", segment=0, is_header=False, cells=cells(values), param_ref=param))
    return LogicalTable(logical_table_id=table_id, segments=[seg], columns=cols, rows=out)


def build(doc: Doc, tmp_path: Path, *, review: list[ReviewItem] | None = None, ocr: set[int] = frozenset(),
          profile_name: str = "qs_controller", tables: dict[str, LogicalTable] | None = None,
          **kwargs) -> BuildResult:  # type: ignore[assignment]
    pages = sorted({e.pdf_page_index for e in doc.elements})
    run = RunInput(run_dir=tmp_path, report=report(pages, ocr), elements=doc.elements, tables=tables or {},
                   review=review or [], ocr_pages=set(ocr))
    return build_chunks(run, MANIFEST, load_profile(profile_name), **kwargs)


def leaves(result: BuildResult):
    return [c for c in result.chunks if c.chunk_role != "parent"]
