"""Bảng logic: T-01…T-05, T-15 rồi T-12, T-13 trên cell (contract §3, §5).

Luật chỉ dùng tín hiệu hình học/cấu trúc với sai số tương đối; tri thức miền (mẫu mã,
prefix parameter, lexicon điều kiện) đọc từ `Profile`. Không cell nguồn nào bị xóa: cell
không gán được cột nằm trong `unassigned_cells` kèm mục review blocking.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.modules.doc_ingest.geometry import BBox
from app.modules.doc_ingest.normalize.docling_reader import RawCell, RawItem
from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.schemas.normalized import (Box, Cell, Column, LogEntry, LogicalTable,
                                                       ReviewItem, Row, Segment, UnassignedCell)
from app.modules.doc_ingest.schemas.profile import Profile
from app.modules.doc_ingest.technical_refs.applicability import detect_applicability
from app.modules.doc_ingest.technical_refs.params import overlapping, parse_param_ref

HeaderDecision = Literal["repeated", "data", "unsure"]


@dataclass
class TableRun:
    tables: list[LogicalTable]
    review: list[ReviewItem]
    log: list[LogEntry]


def token_shape(text: str) -> str:
    """Hình dạng token: chữ số liên tiếp → `9`, chữ cái liên tiếp → `a`, giữ ký hiệu."""
    shape = re.sub(r"\d+", "9", text.strip())
    shape = re.sub(r"[^\W\d_]+", "a", shape)
    return re.sub(r"\s+", " ", shape)


def _norm_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _box(bbox: BBox) -> Box:
    return Box(x0=round(bbox.x0, 2), y0=round(bbox.y0, 2), x1=round(bbox.x1, 2), y1=round(bbox.y1, 2))


def _group_rows(item: RawItem) -> dict[int, list[RawCell]]:
    rows: dict[int, list[RawCell]] = {}
    for cell in item.cells:
        rows.setdefault(cell.row, []).append(cell)
    return {r: sorted(rows[r], key=lambda c: c.center_x) for r in sorted(rows)}


def _locate(columns: Sequence[Column], x: float) -> int | None:
    for column in columns:
        last = column.index == len(columns) - 1
        if column.x_min <= x < column.x_max or (last and x == column.x_max):
            return column.index
    return None


def _gap_clusters(cells: Sequence[RawCell]) -> list[tuple[float, float]]:
    """Gộp khoảng x chồng nhau của các cell; giữa hai cụm là một khe trắng dọc."""
    clusters: list[list[float]] = []
    for x0, x1 in sorted((c.bbox.x0, c.bbox.x1) for c in cells):
        if clusters and x0 <= clusters[-1][1]:
            clusters[-1][1] = max(clusters[-1][1], x1)
        else:
            clusters.append([x0, x1])
    return [(a, b) for a, b in clusters]


def _derive_columns(item: RawItem, rows: dict[int, list[RawCell]],
                    header_rows: list[int]) -> tuple[list[Column], bool]:
    """T-01: biên cột ở giữa các khe trắng dọc giữa cụm cell dữ liệu (cell có tâm nằm trong
    bbox bảng). Số cụm khác số cột
    Docling → dự phòng: trung điểm tâm header (hoặc trung vị tâm theo chỉ số cột Docling,
    chỉ dùng làm cụm) và trả cờ lệch số cột."""
    assert item.bbox is not None
    data_cells = [c for c in item.cells if not c.header and c.text.strip()
                  and item.bbox.x0 <= c.center_x <= item.bbox.x1]
    clusters = _gap_clusters(data_cells)
    mismatch = len(clusters) != item.num_cols or not clusters
    if not mismatch:
        inner = [(a[1] + b[0]) / 2 for a, b in zip(clusters, clusters[1:])]
    else:
        if header_rows and len(rows[header_rows[-1]]) >= item.num_cols:
            centers = [cell.center_x for cell in rows[header_rows[-1]]]
        else:
            by_col: dict[int, list[float]] = {}
            for cell in item.cells:
                by_col.setdefault(cell.col, []).append(cell.center_x)
            centers = sorted(statistics.median(xs) for xs in by_col.values())
        inner = [(a + b) / 2 for a, b in zip(centers, centers[1:])]
    source = "detected" if header_rows else "none"
    edges = [item.bbox.x0, *inner, item.bbox.x1]
    columns = [Column(index=i, header_text=None, x_min=round(edges[i], 2), x_max=round(edges[i + 1], 2),
                      header_source=source) for i in range(len(edges) - 1)]
    for r in header_rows:
        for cell in rows[r]:
            col = _locate(columns, cell.center_x)
            if col is None or not cell.text.strip():
                continue
            current = columns[col].header_text
            if current is None:
                columns[col].header_text = cell.text.strip()
            elif cell.text.strip() not in current.split(" / "):
                columns[col].header_text = f"{current} / {cell.text.strip()}"
    return columns, mismatch


@dataclass
class _Builder:
    table_id: str
    profile: Profile
    rec: Recorder
    columns: list[Column]
    x0: float
    x1: float
    segments: list[Segment] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)
    unassigned: list[UnassignedCell] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    last_page: int = -1

    # ---------------------------------------------------------------- T-01, T-02
    def _assign(self, seg_index: int, item: RawItem, rows: dict[int, list[RawCell]],
                header_rows: list[int], commit: bool) -> list[Row]:
        built: list[Row] = []
        next_id = len(self.rows)
        for r, cells in rows.items():
            row_id = f"r{next_id}"
            next_id += 1
            by_col: dict[int, Cell] = {}
            for cell in cells:
                col = _locate(self.columns, cell.center_x)
                reason = "outside_columns" if col is None else "column_collision" if col in by_col else None
                if reason is not None:
                    if commit:
                        self.unassigned.append(UnassignedCell(row_id=row_id, text=cell.text, bbox=_box(cell.bbox),
                                                              raw_cell_ref=cell.ref, reason=reason))
                        self.rec.add_review(item.element_id, "unassigned_cell",
                                            f"cell {cell.text!r} ({reason})", target=f"{self.table_id}:{row_id}",
                                            suggested_action="assign the cell to a column")
                    continue
                assert col is not None
                by_col[col] = Cell(col=col, text=cell.text, bbox=_box(cell.bbox), raw_cell_ref=cell.ref,
                                   docling_col=cell.col, docling_header=cell.header, assigned_by="bbox")
                if commit and col != cell.col:
                    self.rec.add_log("T-01", item.element_id, "cell center x lies in another column",
                                     target=cell.ref, before={"col": cell.col}, after={"col": col})
            for column in self.columns:
                if column.index not in by_col:
                    by_col[column.index] = Cell(col=column.index, text="", bbox=None, raw_cell_ref=None,
                                                docling_col=None, docling_header=False, assigned_by="empty_fill")
            built.append(Row(row_id=row_id, segment=seg_index, is_header=r in header_rows,
                             cells=[by_col[i] for i in range(len(self.columns))]))
        return built

    def add_first_segment(self, item: RawItem, rows: dict[int, list[RawCell]], header_rows: list[int],
                          column_mismatch: bool) -> None:
        built = self._assign(0, item, rows, header_rows, commit=True)
        self._commit_segment(item, header_rows, built)
        if column_mismatch:
            self.rec.add_review(item.element_id, "column_count_mismatch",
                                f"whitespace gaps do not split the table into {item.num_cols} docling columns",
                                target=self.table_id, suggested_action="confirm column boundaries")
        if any(c.col != c.docling_col for row in built for c in row.cells if c.raw_cell_ref):
            self.flags.append("column_order_repaired:segment0")
        if not header_rows:
            self.rec.add_review(item.element_id, "header_missing", "table has no header row",
                                target=self.table_id, suggested_action="confirm column labels")
        elif len(header_rows) > 1:
            self.flags.append("complex_header")
            self.rec.add_review(item.element_id, "complex_header",
                                f"{len(header_rows)} header rows joined with ' / '", target=self.table_id,
                                suggested_action="confirm column labels")

    # ---------------------------------------------------------------- T-03, T-04, T-05
    def _classify_header(self, row: Row, data_rows: Sequence[Row]) -> tuple[HeaderDecision, str]:
        header_texts = [_norm_text(c.header_text) for c in self.columns]
        if [_norm_text(c.text) for c in row.cells] == header_texts:
            return "repeated", "a"
        key = row.cells[0].text
        shapes = Counter(token_shape(r.cells[0].text) for r in data_rows if r.cells[0].text.strip())
        total = sum(shapes.values())
        th = self.profile.thresholds
        if key.strip() and total >= th.shape_min_rows:
            shape, count = shapes.most_common(1)[0]
            if count / total >= th.shape_majority and token_shape(key) == shape:
                return "data", "b"
        if any(re.search(pattern, key) for pattern in self.profile.code_patterns):
            return "data", "c"
        return "unsure", "d"

    def try_continue(self, item: RawItem, rows: dict[int, list[RawCell]],
                     header_rows: list[int]) -> Literal["merged", "ambiguous", "new"]:
        assert item.bbox is not None
        min_width = min(c.x_max - c.x_min for c in self.columns)
        tol = self.profile.thresholds.continuation_tol * min_width
        edges_ok = abs(item.bbox.x0 - self.x0) <= tol and abs(item.bbox.x1 - self.x1) <= tol
        cols_ok = item.num_cols <= len(self.columns)
        if not (edges_ok and cols_ok):
            return "ambiguous" if not header_rows else "new"
        has_header = any(c.header_source != "none" for c in self.columns)
        if header_rows and not has_header:
            return "new"
        seg_index = len(self.segments)
        tentative = self._assign(seg_index, item, rows, header_rows, commit=False)
        data_rows = [r for r in self.rows + tentative if not r.is_header]
        decisions = {row.row_id: self._classify_header(row, data_rows) for row in tentative if row.is_header}
        built = self._assign(seg_index, item, rows, header_rows, commit=True)
        for row in built:
            if row.row_id not in decisions:
                continue
            decision, step = decisions[row.row_id]
            target = f"{self.table_id}:{row.row_id}"
            if decision == "repeated":
                row.repeated_header = True
                self.rec.add_log("T-05", item.element_id, "row repeats the logical table header (step a)",
                                 target=target, after={"repeated_header": True})
            elif decision == "data":
                row.is_header = False
                self.flags.append(f"header_flag_demoted:{row.row_id}")
                self.rec.add_log("T-05", item.element_id, f"header flag demoted to data (step {step})",
                                 target=target, before={"docling_header": True}, after={"is_header": False})
            else:
                self.rec.add_review(item.element_id, "header_demotion_unsure",
                                    "header-flagged row matches neither the header nor the data shape",
                                    target=target, suggested_action="mark the row as header or data")
        self._commit_segment(item, header_rows, built)
        self.rec.add_log("T-03", item.element_id, "segment continues the logical table from the previous page",
                         target=self.table_id, after={"segment": seg_index})
        if not header_rows or all(decisions[r.row_id][0] != "unsure" for r in built if r.row_id in decisions):
            self.flags.append(f"header_inherited:segment{seg_index}")
        if item.num_cols < len(self.columns):
            for column in self.columns:
                if all(not row.cells[column.index].text for row in built):
                    self.flags.append(f"empty_column_restored:segment{seg_index}:col{column.index}")
        if any(c.col != c.docling_col for row in built for c in row.cells if c.raw_cell_ref):
            self.flags.append(f"column_order_repaired:segment{seg_index}")
        return "merged"

    def _commit_segment(self, item: RawItem, header_rows: list[int], built: list[Row]) -> None:
        assert item.bbox is not None
        self.segments.append(Segment(element_id=item.element_id, pdf_page_index=item.page, bbox=_box(item.bbox),
                                     num_cols_docling=item.num_cols, header_rows_docling=header_rows))
        self.rows.extend(built)
        self.last_page = item.page

    # ---------------------------------------------------------------- T-15
    def merge_continuation_rows(self) -> None:
        factor = self.profile.thresholds.row_gap_factor
        for seg_index, segment in enumerate(self.segments):
            seg_rows = [r for r in self.rows if r.segment == seg_index]
            spans = {r.row_id: _row_span(r) for r in seg_rows}
            heights = [span[1] - span[0] for span in spans.values() if span]
            median_height = statistics.median(heights) if heights else 0.0
            prev: Row | None = None
            for row in seg_rows:
                is_continuation = (not row.is_header and not row.cells[0].text.strip()
                                   and any(c.text.strip() for c in row.cells))
                if not is_continuation:
                    prev = row
                    continue
                span, prev_span = spans[row.row_id], spans[prev.row_id] if prev else None
                target = f"{self.table_id}:{row.row_id}"
                if (prev is None or prev.is_header or span is None or prev_span is None
                        or span[0] - prev_span[1] > factor * median_height):
                    self.rec.add_review(segment.element_id, "orphan_row",
                                        "row with empty key cell could not be merged", target=target,
                                        suggested_action="merge into the row above or keep separate")
                    prev = row
                    continue
                for cell, into in zip(row.cells, prev.cells):
                    if not cell.text.strip():
                        continue
                    into.text = f"{into.text} {cell.text}".strip()
                    if cell.raw_cell_ref:
                        into.merged_cell_refs.append(cell.raw_cell_ref)
                prev.merged_row_ids.append(row.row_id)
                self.rows.remove(row)
                spans[prev.row_id] = (prev_span[0], max(prev_span[1], span[1]))
                self.rec.add_log("T-15", segment.element_id, "row with empty key cell merged into the row above",
                                 target=target, after={"merged_into": prev.row_id})

    # ---------------------------------------------------------------- T-12, T-13
    def annotate_cells(self) -> None:
        data_rows = [r for r in self.rows if not r.is_header]
        self._parse_params(data_rows)
        for row in data_rows:
            element_id = self.segments[row.segment].element_id
            target = f"{self.table_id}:{row.row_id}"
            for cell in row.cells:
                for match in detect_applicability(cell.text, self.profile):
                    row.applicability_candidates.append(match.candidate)
                    self.rec.add_review(element_id, "applicability_note", match.candidate.note, target=target)
                    if match.unmatched:
                        self.rec.add_review(element_id, "applicability_model_unmatched",
                                            f"condition {match.candidate.condition_text!r} matches no model "
                                            "or interface in the registry", target=target,
                                            suggested_action="confirm which models the condition covers")

    def _parse_params(self, data_rows: Sequence[Row]) -> None:
        prefixes = self.profile.param_prefixes
        keyed = [r for r in data_rows if r.cells[0].text.strip()]
        if not prefixes or not keyed:
            return
        max_len = self.profile.thresholds.max_range_len
        parses = {r.row_id: parse_param_ref(r.cells[0].text, prefixes, max_len) for r in keyed}
        if sum(p.ref is not None for p in parses.values()) / len(keyed) < self.profile.thresholds.shape_majority:
            return
        self.flags.append("param_table")
        refs = []
        for row in keyed:
            parsed = parses[row.row_id]
            element_id = self.segments[row.segment].element_id
            target = f"{self.table_id}:{row.row_id}"
            if parsed.ref is None:
                self.rec.add_review(element_id, "param_unparseable", f"{row.cells[0].text!r}: {parsed.error}",
                                    target=target)
                continue
            row.param_ref = parsed.ref
            refs.append((row.row_id, parsed.ref))
            if "range_too_long" in parsed.flags:
                self.rec.add_review(element_id, "range_too_long", parsed.ref.label, target=target)
        for a, b in overlapping(refs):
            self.rec.add_review(self.segments[0].element_id, "param_code_overlap",
                                f"rows {a} and {b} share parameter codes", target=self.table_id)

    def build(self) -> LogicalTable:
        return LogicalTable(logical_table_id=self.table_id, segments=self.segments, columns=self.columns,
                            rows=self.rows, unassigned_cells=self.unassigned, flags=self.flags)


def _row_span(row: Row) -> tuple[float, float] | None:
    boxes = [c.bbox for c in row.cells if c.bbox is not None and c.text.strip()]
    if not boxes:
        return None
    return min(b.y0 for b in boxes), max(b.y1 for b in boxes)


def build_logical_tables(items: Sequence[RawItem], doc_id: str, profile: Profile,
                         rec: Recorder | None = None, screenshots: frozenset[str] = frozenset()) -> TableRun:
    """`screenshots`: bảng Docling 0 cell mà T-09 đã nhận là ảnh chụp màn hình — đóng bảng đang
    mở như một hình có caption, không vào bảng logic."""
    rec = rec if rec is not None else Recorder()
    builders: list[_Builder] = []
    open_builder: _Builder | None = None
    for item in items:
        if item.is_furniture or (item.parent_id is not None and item.label != "table"):
            continue
        if item.label != "table" or item.element_id in screenshots:
            # Picture không caption (thường là watermark) không đóng bảng đang mở.
            if not (item.label == "picture" and not item.has_caption):
                open_builder = None
            continue
        if not item.cells or item.bbox is None:
            rec.add_log("T-01", item.element_id, "table has no cells; left to T-09 (screenshot)")
            rec.add_review(item.element_id, "empty_table", "docling table with 0 cells, not a screenshot by T-09",
                           target=item.element_id, suggested_action="check whether this is a screenshot or a lost table")
            open_builder = None
            continue
        rows = _group_rows(item)
        header_rows = [r for r, cells in rows.items() if any(c.header for c in cells)]
        if open_builder is not None and open_builder.last_page == item.page - 1:
            decision = open_builder.try_continue(item, rows, header_rows)
            if decision == "merged":
                continue
            if decision == "ambiguous":
                rec.add_review(item.element_id, "ambiguous_continuation",
                               f"header-less table at page top does not align with {open_builder.table_id}",
                               target=open_builder.table_id, suggested_action="confirm whether the table continues")
        columns, column_mismatch = _derive_columns(item, rows, header_rows)
        builder = _Builder(table_id=f"{doc_id}:t{len(builders) + 1:03d}", profile=profile, rec=rec,
                           columns=columns, x0=item.bbox.x0, x1=item.bbox.x1)
        builder.add_first_segment(item, rows, header_rows, column_mismatch)
        builders.append(builder)
        open_builder = builder
    for builder in builders:
        builder.merge_continuation_rows()
        builder.annotate_cells()
    return TableRun(tables=[b.build() for b in builders], review=rec.review, log=rec.log)
