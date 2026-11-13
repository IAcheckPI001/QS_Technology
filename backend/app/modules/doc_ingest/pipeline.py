"""Điều phối một lần chạy chuẩn hóa và ghi thư mục chạy (contract §1). Không import Docling.

Bước chưa có code được báo `not_implemented` dựa trên việc module của bước đó (theo
backlog) có tồn tại hay không, không khai báo tay là "xong".
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.modules.doc_ingest.eval.profile_fit import profile_fit
from app.modules.doc_ingest.normalize.coverage import ElementCoverage, classify_items
from app.modules.doc_ingest.normalize.docling_reader import RawItem, read_items
from app.modules.doc_ingest.normalize.elements import build_elements
from app.modules.doc_ingest.normalize.figures import FigureRun, PageObjects, decide_figures, release_text_frames
from app.modules.doc_ingest.normalize.lists import ListRun, decide_lists
from app.modules.doc_ingest.normalize.text_refs import TextRefRun, annotate_text
from app.modules.doc_ingest.normalize.pages import decide_furniture, printed_pages
from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.normalize.sections import assign_sections, fix_figures_above_heading
from app.modules.doc_ingest.normalize.tables import TableRun, build_logical_tables
from app.modules.doc_ingest.profile import profile_hash
from app.modules.doc_ingest.review.approval import content_hash, table_unit_payload
from app.modules.doc_ingest.schemas.normalized import (
    ImageInfo, LogicalTable, NormalizedElement, PrintedPage, ValidationResult,
)
from app.modules.doc_ingest.schemas.profile import Profile
from app.modules.doc_ingest.s0 import ocr_pages, s0_review
from app.modules.doc_ingest.schemas.run import (
    DocumentProfile, FurnitureKey, RunReport, RunSource, RunStats, StepState,
)
from app.modules.doc_ingest.validate.coverage import text_coverage

PACKAGE = "app.modules.doc_ingest"

# (key, nhãn, module theo backlog, mã backlog, ghi chú khi module có nhưng mới một phần)
_STEPS: tuple[tuple[str, str, str, str, str], ...] = (
    ("s0", "S0 hồ sơ tài liệu", "parse.profile_probe", "BL-24", ""),
    ("parse", "Parse Docling theo trang (OCR theo trang khi S0 yêu cầu)", "parse.docling_runner", "—", ""),
    ("s1_furniture", "T-20 khung chữ, T-17 xác nhận header/footer, chữ trong hình", "normalize.pages", "BL-07", ""),
    ("s1_labels", "Phân loại nhãn Docling, T-16 mục lục", "normalize.coverage", "BL-33", ""),
    ("s1_tables", "S1 bảng logic T-01…T-05, T-15", "normalize.tables", "BL-05, BL-06, BL-27", ""),
    ("s1_refs", "T-12 mã parameter, T-13 ứng viên applicability (ô bảng + text)", "normalize.text_refs", "BL-11", ""),
    ("s1_pages", "T-06 trang in", "normalize.pages", "BL-07", ""),
    ("s1_sections", "T-07 section path", "normalize.sections", "BL-08", ""),
    ("s1_lists", "T-08 list cha–con", "normalize.lists", "BL-09", ""),
    ("s1_figures", "T-18 nhãn sát hình, T-09…T-11, T-14, T-19 screenshot, watermark, caption, crop, hình trùng",
     "normalize.figures", "BL-10", ""),
    ("validate", "V-01…V-04 kiểm bất biến", "validate", "BL-25", "chỉ V-01 độ phủ text; V-02…V-04 chưa có"),
    ("build", "Chunk builder", "build", "BL-16", ""),
    ("enrich", "Làm giàu tiếng Việt cho chunk lá (Bước 3)", "enrich", "—",
     "bản nháp; chưa duyệt `approved`, chưa đánh giá tra cứu"),
    ("facts", "Trích fact (gồm applicability của fact)", "facts", "BL-17", ""),
    ("review", "Review / HITL theo unit", "review.approval", "BL-18…BL-21",
     "lõi trạng thái/approval; gán unit, CLI review chưa có"),
    ("publish", "Gói xuất bản → doc_chunks", "build.package_writer", "BL-22, BL-90…", ""),
)


def _module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(f"{PACKAGE}.{name}") is not None
    except ModuleNotFoundError:
        return False


def step_states() -> list[StepState]:
    states = []
    for key, label, module, backlog, partial_note in _STEPS:
        exists = _module_exists(module)
        status = "not_implemented" if not exists else "partial" if partial_note else "implemented"
        states.append(StepState(key=key, label=label, status=status, module=module, backlog=backlog,
                                note=partial_note if exists else ""))
    return states


def doc_page(doc: dict[str, Any]) -> int:
    return min(int(no) for no in doc["pages"])


def load_raw_dir(raw_dir: Path, pages: Sequence[int] | None = None) -> list[dict[str, Any]]:
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(raw_dir.glob("*.docling.json"))]
    if pages is not None:
        wanted = set(pages)
        docs = [d for d in docs if doc_page(d) in wanted]
    return sorted(docs, key=doc_page)


Words = dict[int, list[dict[str, Any]]]


def load_s0(raw_dir: Path) -> DocumentProfile | None:
    path = raw_dir / "profile.json"
    return DocumentProfile.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_words(raw_dir: Path, pages: Sequence[int]) -> Words:
    """`p{n}.words.json` của các trang có trong `raw_dir` (thiếu trang nào thì bỏ trang đó)."""
    words: Words = {}
    for page in pages:
        path = raw_dir / f"p{page:03d}.words.json"
        if path.is_file():
            words[page] = json.loads(path.read_text(encoding="utf-8"))["words"]
    return words


def load_objects(raw_dir: Path, pages: Sequence[int]) -> PageObjects:
    """`p{n}.objects.json` (bitmap + nét vector, T-09/T-10/T-14); thiếu trang nào thì bỏ trang đó."""
    objects: PageObjects = {}
    for page in pages:
        path = raw_dir / f"p{page:03d}.objects.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            objects[page] = {"bitmaps": data.get("bitmaps", []), "paths": data.get("paths", [])}
    return objects


@dataclass
class RunResult:
    docs: list[dict[str, Any]]
    items: list[RawItem]
    tables: TableRun
    profile: Profile
    pages: list[int]
    elements: ElementCoverage
    words: Words
    validation: list[ValidationResult]
    s0: DocumentProfile | None = None
    normalized: list[NormalizedElement] | None = None
    furniture_keys: list[FurnitureKey] | None = None
    printed: dict[int, PrintedPage] | None = None
    objects: PageObjects | None = None
    figures: FigureRun | None = None
    lists: ListRun | None = None
    refs: TextRefRun | None = None


def run_normalization(docs: list[dict[str, Any]], doc_id: str, profile: Profile,
                      words: Words | None = None, s0: DocumentProfile | None = None,
                      objects: PageObjects | None = None) -> RunResult:
    """S0 → T-20 khung chữ → T-17/T-18 furniture, nhãn sát hình → T-16 phân loại nhãn → T-06 → T-07 → hình
    (T-09, T-10, T-19, T-11, T-14) → bảng logic → T-08 list → T-12/T-13 trên text → V-01 (khi có words) → NormalizedElement, chung một
    recorder. Hình chạy trước bảng: screenshot (T-09) không thành bảng rỗng, caption gắn lại
    (T-11) đổi điều kiện đóng bảng của T-03."""
    rec = Recorder()
    if s0 is not None:
        s0_review(s0, doc_id, rec)
    pages = sorted(doc_page(d) for d in docs)
    ocr = ocr_pages(s0) if s0 is not None else set()
    # T-20 cần biết trang nào có text layer; không có S0 thì không chạy.
    text_pages = {p.page for p in s0.pages if not p.ocr_applied} if s0 is not None else set()
    frames = release_text_frames(read_items(docs, doc_id), text_pages, profile, rec)
    furniture = decide_furniture(frames.items, profile, rec, frames.frames)
    for element_id, frame_flags in frames.flags.items():
        furniture.flags.setdefault(element_id, []).extend(frame_flags)
    items, moved = fix_figures_above_heading(furniture.items, text_pages, profile, rec)
    for element_id, moved_flags in moved.items():
        furniture.flags.setdefault(element_id, []).extend(moved_flags)
    elements = classify_items(items, rec, profile)
    printed = printed_pages(items, pages, doc_id, profile, rec, s0)
    sections = assign_sections(items, furniture.demoted, profile, rec, elements.toc_lines)
    figures = decide_figures(items, objects, profile, rec)
    items = figures.items
    tables = build_logical_tables(items, doc_id, profile, rec, figures.screenshots)
    not_flow = frozenset(k for k, v in figures.kinds.items() if v == "watermark_candidate") | frozenset(figures.duplicates)
    lists = decide_lists(items, profile, rec, not_flow)
    refs = annotate_text(items, lists, profile, rec, not_flow)
    words = words or {}
    validation = text_coverage(doc_id, words, items, elements.kept, profile, rec, ocr) if words else []
    normalized = build_elements(items, elements, furniture.flags, sections, printed, tables, figures, lists, refs)
    return RunResult(docs=docs, items=items, tables=tables, profile=profile, pages=pages, elements=elements,
                     words=words, validation=validation, s0=s0, normalized=normalized,
                     furniture_keys=furniture.keys, printed=printed, objects=objects, figures=figures,
                     lists=lists, refs=refs)


def image_dir(element_id: str) -> str:
    """`normalized/images/{element_id}/` với `:` đổi thành `_` (Windows không cho `:` trong tên)."""
    return f"normalized/images/{element_id.replace(':', '_')}"


@dataclass(frozen=True)
class CropRequest:
    element_id: str
    page: int
    crop: tuple[float, float, float, float]   # x0, y0, x1, y1 pt, gốc trên-trái
    native_px_per_pt: float                   # độ phân giải bitmap trong vùng crop; 0 nếu là vector


def crop_requests(result: RunResult) -> list[CropRequest]:
    """Vùng cần render (T-14) cho mọi phần tử có `image`."""
    out = []
    for element in result.normalized or []:
        if element.image is None:
            continue
        box = element.image.crop_bbox
        native = 0.0
        for raw in (result.objects or {}).get(element.pdf_page_index, {}).get("bitmaps", []):
            inside = (raw["x0"] >= box.x0 - 1 and raw["x1"] <= box.x1 + 1
                      and raw["y0"] >= box.y0 - 1 and raw["y1"] <= box.y1 + 1)
            if inside and raw.get("px_w") and raw["x1"] > raw["x0"]:
                native = max(native, raw["px_w"] / (raw["x1"] - raw["x0"]))
        out.append(CropRequest(element.element_id, element.pdf_page_index, (box.x0, box.y0, box.x1, box.y1), native))
    return out


def apply_rendered(result: RunResult, rendered: dict[str, dict[str, Any]]) -> None:
    """Ghi đường dẫn/kích thước ảnh đã render vào `image` (CLI gọi sau khi render bằng pdfium)."""
    for index, element in enumerate(result.normalized or []):
        info = rendered.get(element.element_id)
        if element.image is None or info is None:
            continue
        image = ImageInfo.model_validate({**element.image.model_dump(), **info})
        result.normalized[index] = element.model_copy(update={"image": image})  # type: ignore[index]


def _closing_items(items: Sequence[RawItem], page: int) -> list[RawItem]:
    """Phần tử body có thể đóng/mở bảng trên trang (bỏ furniture, phần tử con của picture/table,
    picture không caption)."""
    return [i for i in items if i.page == page and not i.is_furniture and i.parent_id is None
            and not (i.label == "picture" and not i.has_caption)]


def page_range_boundary(result: RunResult, total_pages: int | None) -> dict[str, list[str]]:
    """Bảng có thể bị cắt vì trang liền kề không nằm trong tập trang đã chọn (chỉ hiển thị)."""
    selected = set(result.pages)
    flagged: dict[str, list[str]] = {}
    for table in result.tables.tables:
        first, last = table.segments[0], table.segments[-1]
        reasons = []
        head = _closing_items(result.items, first.pdf_page_index)
        if (first.pdf_page_index > 1 and first.pdf_page_index - 1 not in selected
                and head and head[0].element_id == first.element_id):
            reasons.append(f"bảng ở đầu trang {first.pdf_page_index}, trang {first.pdf_page_index - 1} không được chọn")
        tail = _closing_items(result.items, last.pdf_page_index)
        has_next = total_pages is None or last.pdf_page_index < total_pages
        if (has_next and last.pdf_page_index + 1 not in selected
                and tail and tail[-1].element_id == last.element_id):
            reasons.append(f"bảng ở cuối trang {last.pdf_page_index}, trang {last.pdf_page_index + 1} không được chọn")
        if reasons:
            flagged[table.logical_table_id] = reasons
    return flagged


def validation_summary(result: RunResult) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for check in result.validation:
        key = "passed" if check.passed else "not_run" if check.passed is None else "failed"
        bucket = summary.setdefault(check.check_id, {"passed": 0, "failed": 0, "not_run": 0})
        bucket[key] += 1
    missing = [p for p in result.pages if p not in result.words]
    if missing:
        summary.setdefault("V-01", {"passed": 0, "failed": 0, "not_run": 0})["not_run"] += len(missing)
    return summary


def figure_summary(result: RunResult) -> dict[str, int]:
    elements = result.normalized or []
    counts = Counter(e.normalized_type for e in elements
                     if e.normalized_type in ("picture", "screenshot", "watermark_candidate"))
    flags = Counter(f for e in elements for f in e.flags
                    if f in ("caption_relinked", "figure_text_attached", "repeated_image", "duplicate_image"))
    return {**dict(sorted(counts.items())), **dict(sorted(flags.items())),
            "rendered": sum(1 for e in elements if e.image is not None and e.image.original_path)}


def list_summary(result: RunResult) -> dict[str, int]:
    """T-08: số list_item, con, độ sâu lớn nhất, mồ côi, mơ hồ, nối qua trang, marker trộn."""
    infos = [e.list_info for e in result.normalized or [] if e.list_info is not None]
    flags = Counter(f for e in result.normalized or [] for f in e.flags
                    if f in ("list_cross_page", "list_marker_mixed"))
    run = result.lists or ListRun()
    return {"list_items": len(infos), "children": sum(1 for i in infos if i.parent_element_id),
            "max_depth": max((i.depth for i in infos), default=0),
            "orphans": len(run.orphans), "ambiguous": len(run.ambiguous), **dict(sorted(flags.items()))}


def ref_summary(result: RunResult) -> dict[str, int]:
    """T-12/T-13 trên text: số ref theo vai trò, kiểu, prefix; cụm áp dụng; lỗi; near-miss."""
    refs = [r for e in result.normalized or [] for r in e.param_refs]
    run = result.refs or TextRefRun()
    out: dict[str, int] = {"elements_with_refs": sum(1 for e in result.normalized or [] if e.param_refs),
                           "text_param_refs": len(refs)}
    out.update({f"role_{k}": v for k, v in sorted(Counter(r.role for r in refs).items())})
    out.update({f"kind_{k}": v for k, v in sorted(Counter(r.kind for r in refs).items())})
    out.update({f"prefix_{k}": v for k, v in sorted(Counter(r.prefix for r in refs).items())})
    out.update({"applicability_text": sum(len(v) for v in run.applicability.values()),
                "unparseable": run.unparseable, "near_miss": sum(run.near_miss.values()),
                "list_param_mismatch": run.list_mismatch})
    return out


def table_hash(table: LogicalTable) -> str:
    return content_hash(table_unit_payload(table))


def _jsonl(path: Path, rows: Sequence[Any]) -> None:
    path.write_text("".join(row.model_dump_json() + "\n" for row in rows), encoding="utf-8")


def write_run(run_dir: Path, result: RunResult, *, doc_id: str, run_id: str, created_at: datetime,
              source: RunSource, timings: dict[str, float], versions: dict[str, str]) -> RunReport:
    raw_dir, normalized = run_dir / "raw", run_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized.mkdir(parents=True, exist_ok=True)
    for doc in result.docs:
        (raw_dir / f"p{doc_page(doc):03d}.docling.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    run = result.tables
    _jsonl(normalized / "tables.jsonl", run.tables)
    _jsonl(normalized / "review_queue.jsonl", run.review)
    _jsonl(normalized / "normalization_log.jsonl", run.log)
    _jsonl(normalized / "validation.jsonl", result.validation)
    _jsonl(normalized / "elements.jsonl", result.normalized or [])
    if result.s0 is not None:
        (raw_dir / "profile.json").write_text(result.s0.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for page, objects in sorted((result.objects or {}).items()):
        (raw_dir / f"p{page:03d}.objects.json").write_text(
            json.dumps({"pdf_page_index": page, **objects}, separators=(",", ":")) + "\n", encoding="utf-8")
    for page, words in sorted(result.words.items()):
        (raw_dir / f"p{page:03d}.words.json").write_text(
            json.dumps({"pdf_page_index": page, "words": words}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")

    blocking = Counter(item.blocks for item in run.review if item.blocking)
    report = RunReport(
        doc_id=doc_id, run_id=run_id, created_at=created_at, source=source, pages_selected=result.pages,
        profile_name=result.profile.name, profile_hash=profile_hash(result.profile),
        tool_versions=versions, timings_s=timings, steps=step_states(),
        stats=RunStats(tables=len(run.tables), rows=sum(len(t.rows) for t in run.tables),
                       review_items=len(run.review),
                       review_by_code=dict(sorted(Counter(i.code for i in run.review).items())),
                       blocking_by_step=dict(sorted(blocking.items()))),
        table_content_hashes={t.logical_table_id: table_hash(t) for t in run.tables},
        page_range_boundary=page_range_boundary(result, source.total_pages),
        validation_summary=validation_summary(result),
        s0=result.s0,
        furniture_keys=result.furniture_keys or [],
        printed_pages={p: pp.value for p, pp in sorted((result.printed or {}).items())},
        element_types=dict(sorted(Counter(e.normalized_type for e in result.normalized or []).items())),
        figures=figure_summary(result),
        lists=list_summary(result),
        refs=ref_summary(result),
        profile_fit=profile_fit(result),
    )
    (run_dir / "run_report.json").write_text(report.model_dump_json(indent=1) + "\n", encoding="utf-8")
    return report
