"""Fixture tổng hợp (SYN) dạng DoclingDocument JSON cho các ca F54 không có.

Bbox phần tử ghi theo BOTTOMLEFT như Docling, bbox cell theo TOPLEFT, để đi qua đúng
đường chuyển tọa độ của reader.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PAGE_W, PAGE_H = 612.0, 792.0
# Cột mặc định của bảng 3 cột: key căn trái, mô tả căn trái, giá trị.
COLS3 = [(90.0, 150.0), (180.0, 380.0), (420.0, 540.0)]
TABLE_X = (84.0, 556.0)


@dataclass
class SynPage:
    page: int
    texts: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    pictures: list[dict[str, Any]] = field(default_factory=list)
    children: list[dict[str, str]] = field(default_factory=list)

    def _prov(self, l: float, t: float, r: float, b: float) -> list[dict[str, Any]]:
        return [{"page_no": self.page, "charspan": [0, 0],
                 "bbox": {"l": l, "t": PAGE_H - t, "r": r, "b": PAGE_H - b, "coord_origin": "BOTTOMLEFT"}}]

    def text(self, label: str, text: str, top: float, bottom: float | None = None, *,
             x: tuple[float, float] = (85.0, 500.0), parent: str | None = None) -> "SynPage":
        """`parent`: self_ref của picture/table chứa text (chữ OCR trong hình, caption); mặc định nằm
        dưới body. Caption có parent được ghi vào `captions` của parent như Docling."""
        ref = f"#/texts/{len(self.texts)}"
        layer = "furniture" if label in {"page_header", "page_footer"} else "body"
        self.texts.append({"self_ref": ref, "label": label, "text": text, "content_layer": layer,
                           "parent": {"$ref": parent or "#/body"},
                           "prov": self._prov(x[0], top, x[1], bottom or top + 15.0)})
        if parent is None:
            self.children.append({"$ref": ref})
        else:
            owner = next(p for p in self.pictures + self.tables if p["self_ref"] == parent)
            owner.setdefault("children", []).append({"$ref": ref})
            if label == "caption":
                owner["captions"].append({"$ref": ref})
        return self

    def picture(self, top: float, bottom: float, *, x: tuple[float, float] = (85.0, 500.0)) -> str:
        ref = f"#/pictures/{len(self.pictures)}"
        self.pictures.append({"self_ref": ref, "label": "picture", "content_layer": "body", "captions": [],
                              "children": [], "prov": self._prov(x[0], top, x[1], bottom)})
        self.children.append({"$ref": ref})
        return ref

    def empty_table(self, top: float, bottom: float, *, x: tuple[float, float] = TABLE_X) -> str:
        """Bảng Docling 0 cell (ảnh chụp màn hình bị nhận nhầm là bảng)."""
        ref = f"#/tables/{len(self.tables)}"
        self.tables.append({"self_ref": ref, "label": "table", "content_layer": "body", "captions": [],
                            "children": [], "prov": self._prov(x[0], top, x[1], bottom),
                            "data": {"table_cells": [], "num_rows": 0, "num_cols": 0}})
        self.children.append({"$ref": ref})
        return ref

    def table(self, rows: list[list[str]], *, top: float, header_rows: tuple[int, ...] = (0,),
              cols: list[tuple[float, float]] = COLS3, row_h: float = 15.0, x: tuple[float, float] = TABLE_X,
              num_cols: int | None = None, cell_x: dict[tuple[int, int], tuple[float, float]] | None = None,
              row_tops: list[float] | None = None) -> "SynPage":
        """`rows[i][j] == ""` → không có cell (như Docling bỏ ô trống)."""
        ref = f"#/tables/{len(self.tables)}"
        cells = []
        for i, row in enumerate(rows):
            y0 = row_tops[i] if row_tops else top + i * row_h
            for j, value in enumerate(row):
                if not value:
                    continue
                x0, x1 = (cell_x or {}).get((i, j), cols[j])
                cells.append({"bbox": {"l": x0, "t": y0 + 2, "r": x1, "b": y0 + row_h - 3, "coord_origin": "TOPLEFT"},
                              "row_span": 1, "col_span": 1, "start_row_offset_idx": i, "end_row_offset_idx": i + 1,
                              "start_col_offset_idx": j, "end_col_offset_idx": j + 1, "text": value,
                              "column_header": i in header_rows, "row_header": False, "row_section": False})
        bottom = (row_tops[-1] if row_tops else top + len(rows) * row_h) + row_h
        self.tables.append({"self_ref": ref, "label": "table", "content_layer": "body", "captions": [],
                            "prov": self._prov(x[0], top, x[1], bottom),
                            "data": {"table_cells": cells, "num_rows": len(rows),
                                     "num_cols": num_cols if num_cols is not None else len(cols)}})
        self.children.append({"$ref": ref})
        return self

    def to_doc(self) -> dict[str, Any]:
        return {"schema_name": "DoclingDocument", "version": "1.0.0", "name": f"syn{self.page}",
                "body": {"self_ref": "#/body", "children": self.children},
                "furniture": {"self_ref": "#/furniture", "children": []}, "groups": [],
                "texts": self.texts, "tables": self.tables, "pictures": self.pictures,
                "pages": {str(self.page): {"size": {"width": PAGE_W, "height": PAGE_H}, "page_no": self.page}}}


def param_rows(start: int, count: int) -> list[list[str]]:
    """Dòng dữ liệu có cột key dạng `#9` (hình dạng đồng nhất)."""
    return [[f"#{start + i:04d}", f"Setting {i}", "0: Off - 1: On"] for i in range(count)]
