"""Đọc DoclingDocument (dạng dict JSON) thành danh sách phần tử theo thứ tự đọc.

Mọi bbox được quy về gốc trên-trái của trang. Nhận một hoặc nhiều document (spike chạy
theo từng trang); thứ tự giữ theo thứ tự document rồi thứ tự `body`. Phần tử con của
picture/table (caption, chữ OCR trong hình) giữ `parent_id` của phần tử cha gần nhất
không phải group.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.doc_ingest.geometry import BBox

FURNITURE_LABELS = frozenset({"page_header", "page_footer"})
_Node = Mapping[str, Any]


@dataclass(frozen=True)
class RawCell:
    ref: str
    text: str
    bbox: BBox
    row: int
    col: int
    header: bool

    @property
    def center_x(self) -> float:
        return (self.bbox.x0 + self.bbox.x1) / 2


@dataclass(frozen=True)
class RawItem:
    element_id: str
    self_ref: str
    label: str
    page: int
    bbox: BBox | None
    text: str
    content_layer: str
    has_caption: bool = False
    cells: tuple[RawCell, ...] = ()
    num_cols: int = 0
    page_height: float = 0.0
    page_width: float = 0.0
    parent_id: str | None = None      # element_id của picture/table chứa phần tử này
    parent_label: str | None = None
    marker: str = ""                  # list_item: marker Docling (không đáng tin, T-08 ưu tiên glyph)

    @property
    def is_furniture(self) -> bool:
        """Theo `content_layer` (Docling đặt `furniture` cho header/footer; T-17 có thể đổi)."""
        return self.content_layer == "furniture"


def to_topleft(bbox: Mapping[str, Any], page_height: float) -> BBox:
    if bbox.get("coord_origin") == "BOTTOMLEFT":
        return BBox(bbox["l"], page_height - bbox["t"], bbox["r"], page_height - bbox["b"])
    return BBox(bbox["l"], bbox["t"], bbox["r"], bbox["b"])


def _resolve(doc: Mapping[str, Any], ref: str) -> Mapping[str, Any]:
    _, kind, index = ref.split("/")
    return doc[kind][int(index)]


def _walk(doc: _Node, node: _Node, parent: _Node | None = None) -> Iterator[tuple[_Node, _Node | None]]:
    """Duyệt cây theo thứ tự đọc; đi vào con của mọi phần tử (caption là con của
    picture/table, text trong hình là con của picture), không chỉ group. Trả kèm phần tử
    cha gần nhất không phải group (None nếu nằm trực tiếp dưới body/group)."""
    for child in node.get("children", []):
        item = _resolve(doc, child["$ref"])
        if child["$ref"].startswith("#/groups/"):
            yield from _walk(doc, item, parent)
        else:
            yield item, parent
            yield from _walk(doc, item, item)


def _cells(item: Mapping[str, Any], page_height: float) -> tuple[RawCell, ...]:
    data = item.get("data") or {}
    return tuple(
        RawCell(
            ref=f"{item['self_ref']}/cells/{index}",
            text=cell["text"],
            bbox=to_topleft(cell["bbox"], page_height),
            row=cell["start_row_offset_idx"],
            col=cell["start_col_offset_idx"],
            header=bool(cell.get("column_header")),
        )
        for index, cell in enumerate(data.get("table_cells", []))
    )


def read_items(docs: Iterable[Mapping[str, Any]], doc_id: str) -> list[RawItem]:
    items: list[RawItem] = []
    for doc in docs:
        heights = {int(no): page["size"]["height"] for no, page in doc["pages"].items()}
        widths = {int(no): page["size"]["width"] for no, page in doc["pages"].items()}
        per_page: dict[int, int] = {}
        ids: dict[str, tuple[str, str]] = {}   # self_ref -> (element_id, label), trong document này
        for item, parent in _walk(doc, doc["body"]):
            prov = item.get("prov") or []
            if not prov:
                continue
            page = prov[0]["page_no"]
            index = per_page.get(page, 0)
            per_page[page] = index + 1
            element_id = f"{doc_id}:p{page:03d}:e{index:03d}"
            ids[item["self_ref"]] = (element_id, item["label"])
            parent_id, parent_label = ids.get(parent["self_ref"], (None, None)) if parent is not None else (None, None)
            items.append(RawItem(
                element_id=element_id,
                self_ref=item["self_ref"],
                label=item["label"],
                page=page,
                bbox=to_topleft(prov[0]["bbox"], heights[page]),
                text=item.get("text", ""),
                content_layer=item.get("content_layer", "body"),
                has_caption=bool(item.get("captions")),
                cells=_cells(item, heights[page]) if item.get("data") else (),
                num_cols=(item.get("data") or {}).get("num_cols", 0),
                page_height=heights[page],
                page_width=widths[page],
                parent_id=parent_id,
                parent_label=parent_label,
                marker=item.get("marker") or "",
            ))
    return items
