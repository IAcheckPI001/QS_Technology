"""OCR vùng crop hình trên trang có text layer (contract C2 §8.1): chữ nằm trong bitmap không có trong text layer.

Kết quả chỉ làm từ khóa (`figure_labels`, `keywords`), không vào `content`, không làm nguồn số liệu. Dùng RapidOCR
backend torch có sẵn trong `.venv-ingest` (cùng engine Docling dùng), không thêm dependency. Ghi nối tiếp
`build/figure_ocr.jsonl` theo từng hình nên chạy lại sẽ bỏ qua hình đã có (chạy tiếp được khi bị dừng).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from app.modules.doc_ingest.schemas.normalized import NormalizedElement

VISUAL = ("picture", "screenshot")


def targets(elements: Sequence[NormalizedElement], ocr_pages: set[int], run_dir: Path,
            done: set[str]) -> list[NormalizedElement]:
    """Hình cần OCR: picture/screenshot thân có ảnh render, không trùng, trang không chạy OCR toàn trang."""
    return [e for e in elements
            if e.normalized_type in VISUAL and e.content_layer == "body" and e.duplicate_of is None
            and e.pdf_page_index not in ocr_pages and e.image is not None and e.image.original_path
            and (run_dir / e.image.original_path).is_file() and e.element_id not in done]


def _engine() -> Callable[[str], object]:
    from rapidocr import EngineType, RapidOCR

    return RapidOCR(params={"Det.engine_type": EngineType.TORCH, "Cls.engine_type": EngineType.TORCH,
                            "Rec.engine_type": EngineType.TORCH})


def run_figure_ocr(run_dir: Path, elements: Sequence[NormalizedElement], ocr_pages: set[int],
                   limit: int | None = None) -> Iterator[tuple[str, int, float]]:
    """OCR từng hình, ghi nối tiếp `build/figure_ocr.jsonl`; yield (element_id, số nhãn, giây)."""
    out = run_dir / "build" / "figure_ocr.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["element_id"] for line in out.read_text(encoding="utf-8").splitlines()
            if line.strip()} if out.is_file() else set()
    todo = targets(elements, ocr_pages, run_dir, done)[:limit]
    if not todo:
        return
    engine = _engine()
    with out.open("a", encoding="utf-8") as handle:
        for element in todo:
            assert element.image is not None and element.image.original_path is not None
            started = time.perf_counter()
            result = engine(str(run_dir / element.image.original_path))
            texts = [str(t) for t in (getattr(result, "txts", None) or [])]
            scores = [round(float(s), 3) for s in (getattr(result, "scores", None) or [])]
            handle.write(json.dumps({"element_id": element.element_id, "page": element.pdf_page_index,
                                     "labels": texts, "scores": scores, "engine": "rapidocr-torch"},
                                    ensure_ascii=False) + "\n")
            handle.flush()
            yield element.element_id, len(texts), time.perf_counter() - started
