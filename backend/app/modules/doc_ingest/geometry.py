"""Hình học trang PDF thuần Python (point, gốc trên-trái); không phụ thuộc Docling/pdfium."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    """Bbox theo point, gốc tọa độ góc trên-trái của trang."""

    x0: float
    y0: float
    x1: float
    y1: float

    def scaled(self, scale: float) -> tuple[int, int, int, int]:
        return (
            int(self.x0 * scale), int(self.y0 * scale),
            int(round(self.x1 * scale)), int(round(self.y1 * scale)),
        )

    def padded(self, pad: float, width: float, height: float) -> "BBox":
        return BBox(
            max(0.0, self.x0 - pad), max(0.0, self.y0 - pad),
            min(width, self.x1 + pad), min(height, self.y1 + pad),
        )

    def as_dict(self) -> dict[str, float]:
        return {"x0": round(self.x0, 1), "y0": round(self.y0, 1),
                "x1": round(self.x1, 1), "y1": round(self.y1, 1)}


def parse_pages(spec: str) -> list[int]:
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = (int(value) for value in part.split("-", 1))
            pages.extend(range(start, end + 1))
        elif part:
            pages.append(int(part))
    return sorted(set(pages))


def overlap_ratio(target: BBox, others: list[BBox]) -> float:
    """Tỷ lệ diện tích `target` bị phủ bởi ảnh bitmap (xấp xỉ, cộng dồn)."""
    area = max(1e-6, (target.x1 - target.x0) * (target.y1 - target.y0))
    covered = 0.0
    for other in others:
        w = min(target.x1, other.x1) - max(target.x0, other.x0)
        h = min(target.y1, other.y1) - max(target.y0, other.y0)
        if w > 0 and h > 0:
            covered += w * h
    return round(min(1.0, covered / area), 3)
