"""Thống kê chất lượng chunk theo trạng thái duyệt và nguyên nhân chặn, xuyên nhiều tài liệu (chỉ đọc).

Đọc các file đã có của một lần build (`build/chunks.jsonl`, `chunk_quality.json`, `chunk_review.json`,
`doc_chunks_v2.jsonl`, `normalized/review_queue.jsonl`, `validation.jsonl`); không chạy lại pipeline, không ghi vào run.
Chỉ chunk **lá** được thống kê (D-008: chỉ chunk lá được tìm kiếm và duyệt; chunk cha chỉ mở rộng ngữ cảnh).

Trạng thái của một chunk lá (loại trừ nhau, theo thứ tự ưu tiên):

| Trạng thái | Điều kiện |
|---|---|
| `approved` | `review_status = approved` trong `doc_chunks_v2.jsonl` (đủ cổng 2b, verdict `ok`, 2c, không mã chặn) |
| `needs_fix` | verdict `fix` đúng `content_hash` |
| `stale` | có verdict nhưng `content_hash` đã đổi |
| `blocked_defect` | có mã chặn không phải OCR (bảng, hụt text, khác) |
| `blocked_ocr` | mã chặn chỉ là `ocr_required` (chưa kiểm chứng, không phải lỗi phát hiện được) |
| `reviewed_ok` | verdict `ok`, không mã chặn, nhưng chưa `approved` (chờ cổng 2b/2c) |
| `pending` | còn lại: chưa có verdict |

`review_blockers` khác rỗng thì `review_status` luôn là `draft` (`export/doc_chunks_v2.review_status`); hiện chưa có
cơ chế gỡ mã chặn nên chunk `blocked_*` không thể thành `approved` nếu không đổi đầu ra của pipeline.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from app.modules.doc_ingest.export.doc_chunks_v2 import ApprovalContext, review_status
from app.modules.doc_ingest.schemas.chunk import ChunkQuality, ChunkReviewEntry, ChunkReviewFile, DraftChunk
from app.modules.doc_ingest.schemas.normalized import ReviewItem

STATUSES = ("approved", "reviewed_ok", "needs_fix", "stale", "blocked_defect", "blocked_ocr", "pending")
STATUS_TEXT = {
    "approved": "Đã duyệt (approved)",
    "reviewed_ok": "Đã duyệt nội dung, chờ cổng 2b/2c",
    "needs_fix": "Cần sửa (verdict fix)",
    "stale": "Verdict lỗi thời (nội dung đã đổi)",
    "blocked_defect": "Bị chặn: lỗi phát hiện (bảng, hụt text, khác)",
    "blocked_ocr": "Bị chặn: chỉ vì OCR chưa kiểm chứng",
    "pending": "Chờ duyệt",
}
CAUSES = ("ocr", "table", "coverage", "other")
CAUSE_TEXT = {"ocr": "OCR chưa kiểm chứng", "table": "Cấu trúc bảng", "coverage": "Hụt text (V-01)", "other": "Khác"}
TABLE_CODES = frozenset({
    "column_count_mismatch", "unassigned_cell", "empty_table", "ambiguous_continuation", "header_demotion_unsure",
    "header_missing", "complex_header", "orphan_row", "table_crosscheck_mismatch", "column_type_inconsistent",
    "table_patch_unmatched",
})
CODE_CAUSE = {"ocr_required": "ocr", "text_coverage_gap": "coverage", **{c: "table" for c in TABLE_CODES}}
_PAGE_ID = re.compile(r":p(\d+)$")        # cùng quy ước với `build/fields.review_index`
GARBLED = "￾"


def cause_of(code: str) -> str:
    return CODE_CAUSE.get(code, "other")


# ----------------------------------------------------------------------------- dữ liệu
@dataclass
class ChunkRow:
    doc_id: str
    run: str
    chunk_key: str
    role: str
    chunk_type: str
    status: str
    verdict: str
    causes: list[str]
    codes: list[str]
    item_ids: list[str]
    pages: list[int]
    section: str
    extraction: str
    enrichment: str


@dataclass
class PageGap:
    """Trang V-01 không đạt: `failed_by` = coverage (độ phủ dưới ngưỡng), duplicate (lặp vượt ngưỡng) hoặc cả hai."""

    page: int
    score: float | None
    threshold: float
    missing_count: int | None
    duplicate_ratio: float | None
    duplicate_max: float | None
    failed_by: list[str]
    garbled_text_layer: bool
    missing_sample: list[str]


@dataclass
class DocSummary:
    doc_id: str
    run: str                                       # hai cấp cuối của thư mục chạy, như `source_run`
    leaves: int
    parents: int
    statuses: dict[str, int]
    cause_groups: dict[str, int]                   # nhóm loại trừ: "ocr", "ocr+table", "table+coverage", …
    causes: dict[str, int]                         # số chunk lá chịu mỗi nguyên nhân (giao nhau)
    codes: dict[str, int]                          # số chunk lá mang mỗi mã chặn (giao nhau)
    enrichment: dict[str, int]
    gate_passed: bool | None
    provisional: bool | None
    checks_failed: list[str]
    coverage_ratio: float | None
    page_gaps: list[PageGap] = field(default_factory=list)
    attribution_mismatch: list[str] = field(default_factory=list)   # chunk có mã chặn không truy được về mục review
    rows: list[ChunkRow] = field(default_factory=list)


@dataclass
class Summary:
    at: str
    runs_dir: str
    run_id: str | None
    documents: list[DocSummary]

    @property
    def statuses(self) -> Counter[str]:
        return sum((Counter(d.statuses) for d in self.documents), Counter())

    @property
    def leaves(self) -> int:
        return sum(d.leaves for d in self.documents)


# ----------------------------------------------------------------------------- đọc run
def _jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def blocking_items(chunk: DraftChunk, items: Sequence[ReviewItem]) -> list[ReviewItem]:
    """Mục review chạm tới chunk: cấp trang (`{doc}:pNNN`) khi chunk có phần tử trên trang đó, cấp phần tử theo
    `element_ids`, cấp bảng theo `logical_table_id` (mục theo dòng `rN` chỉ khi dòng đó thuộc chunk).
    Cùng luật với `Assembler._reviews`; `blocks == "chunk"` là mã chặn, loại khác chỉ là ghi chú."""
    pages = {loc.page for loc in chunk.locations} | {chunk.page_start, chunk.page_end}
    elements, table, rows = set(chunk.element_ids), chunk.logical_table_id, set(chunk.row_ids)
    found: list[ReviewItem] = []
    for item in items:
        hit = False
        for ref in {item.element_id, item.target or item.element_id}:
            page = _PAGE_ID.search(ref)
            hit = hit or (int(page.group(1)) in pages if page else ref in elements)
        if not hit and table and item.target and (item.target == table or item.target.startswith(table + ":")):
            row = item.target[len(table) + 1:].split(":")[0] if item.target != table else None
            hit = row is None or not row.startswith("r") or row in rows
        if hit:
            found.append(item)
    return found


def _status(chunk: DraftChunk, approved: bool, entry: ChunkReviewEntry | None) -> str:
    if approved:
        return "approved"
    verdict = entry.verdict if entry is not None else "pending"
    fresh = entry is not None and entry.content_hash == chunk.content_hash
    if verdict == "fix" and fresh:
        return "needs_fix"
    if verdict != "pending" and not fresh:
        return "stale"
    blockers = set(chunk.review_blockers)
    if blockers - {"ocr_required"}:
        return "blocked_defect"
    if blockers:
        return "blocked_ocr"
    return "reviewed_ok" if verdict == "ok" else "pending"


def _gaps(run_dir: Path) -> list[PageGap]:
    gaps: list[PageGap] = []
    for row in _jsonl(run_dir / "normalized" / "validation.jsonl"):
        if row.get("check_id") != "V-01" or row.get("passed") is not False:
            continue
        detail = row.get("detail") or {}
        score = row.get("score")
        threshold = float(row.get("threshold") or 0)  # type: ignore[arg-type]
        dup, dup_max = detail.get("duplicate_ratio"), detail.get("duplicate_max")  # type: ignore[union-attr]
        failed = []
        if score is not None and float(score) < threshold:  # type: ignore[arg-type]
            failed.append("coverage")
        if dup is not None and dup_max is not None and float(dup) > float(dup_max):
            failed.append("duplicate")
        sample = [str(x) for x in (detail.get("missing_sample") or [])]  # type: ignore[union-attr]
        match = _PAGE_ID.search(str(row.get("target")))
        gaps.append(PageGap(
            page=int(match.group(1)) if match else -1, score=score, threshold=threshold,  # type: ignore[arg-type]
            missing_count=detail.get("missing_count"), duplicate_ratio=dup, duplicate_max=dup_max,  # type: ignore[union-attr,arg-type]
            failed_by=failed, garbled_text_layer=any(GARBLED in token for token in sample), missing_sample=sample[:8]))
    return sorted(gaps, key=lambda g: g.page)


def load_doc(run_dir: Path) -> DocSummary | None:
    """Thống kê một lần build; `None` nếu run chưa có `build/chunks.jsonl`."""
    build = run_dir / "build"
    chunks = [DraftChunk.model_validate(row) for row in _jsonl(build / "chunks.jsonl")]
    if not chunks:
        return None
    quality = (ChunkQuality.model_validate_json((build / "chunk_quality.json").read_text(encoding="utf-8"))
               if (build / "chunk_quality.json").is_file() else None)
    review = (ChunkReviewFile.model_validate_json((build / "chunk_review.json").read_text(encoding="utf-8"))
              if (build / "chunk_review.json").is_file() else None)
    status_v2 = {str(r["chunk_key"]): str(r["review_status"]) for r in _jsonl(build / "doc_chunks_v2.jsonl")}
    if not status_v2 and quality is not None:       # run cũ chưa có file v2: tính lại bằng cùng hàm của export
        ctx = ApprovalContext.from_build(quality, review)
        status_v2 = {c.chunk_key: review_status(c, ctx) for c in chunks}
    entries = {e.chunk_key: e for e in (review.reviews if review else [])}
    items = [ReviewItem.model_validate(r) for r in _jsonl(run_dir / "normalized" / "review_queue.jsonl")]
    run = "/".join(run_dir.resolve().parts[-2:])
    doc_id = chunks[0].doc_id
    leaves = [c for c in chunks if c.chunk_role != "parent"]
    rows: list[ChunkRow] = []
    mismatch: list[str] = []
    for c in leaves:
        hit = [i for i in blocking_items(c, items) if i.blocks == "chunk"]
        if {i.code for i in hit} != set(c.review_blockers):
            mismatch.append(c.chunk_key)
        entry = entries.get(c.chunk_key)
        status = _status(c, status_v2.get(c.chunk_key) == "approved", entry)
        pages = sorted({loc.page for loc in c.locations} or set(range(c.page_start, c.page_end + 1)))
        rows.append(ChunkRow(
            doc_id=doc_id, run=run, chunk_key=c.chunk_key, role=c.chunk_role, chunk_type=c.chunk_type, status=status,
            verdict=entry.verdict if entry is not None else "pending",
            causes=[x for x in CAUSES if x in {cause_of(code) for code in c.review_blockers}],
            codes=sorted(c.review_blockers), item_ids=sorted({i.item_id for i in hit}), pages=pages,
            section=" › ".join(c.section_path) or c.section_title, extraction=c.extraction,
            enrichment=c.enrichment_status))
    groups = Counter("+".join(r.causes) for r in rows if r.causes)
    return DocSummary(
        doc_id=doc_id, run=run, leaves=len(leaves), parents=len(chunks) - len(leaves),
        statuses={s: sum(1 for r in rows if r.status == s) for s in STATUSES},
        cause_groups=dict(groups.most_common()),
        causes={k: sum(1 for r in rows if k in r.causes) for k in CAUSES},
        codes=dict(Counter(code for r in rows for code in r.codes).most_common()),
        enrichment=dict(Counter(r.enrichment for r in rows)),
        gate_passed=quality.gate_passed if quality else None, provisional=quality.provisional if quality else None,
        checks_failed=[c.check_id for c in quality.checks if c.passed is False] if quality else [],
        coverage_ratio=quality.coverage.char_ratio if quality and quality.coverage else None,
        page_gaps=_gaps(run_dir), attribution_mismatch=mismatch, rows=rows)


def select_runs(runs_dir: Path, run_id: str | None = None, docs: Iterable[str] | None = None) -> list[Path]:
    """Mỗi thư mục tài liệu một run có `build/chunks.jsonl`: đúng `run_id` nếu cho, không thì run build mới nhất.
    Thư mục bắt đầu bằng `_` (vd. `_summary`) bị bỏ qua."""
    wanted = set(docs) if docs is not None else None
    chosen: list[Path] = []
    for doc_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir() and not p.name.startswith("_")):
        if wanted is not None and doc_dir.name not in wanted:
            continue
        candidates = [doc_dir / run_id] if run_id else [p for p in doc_dir.iterdir() if p.is_dir()]
        built = [p for p in candidates if (p / "build" / "chunks.jsonl").is_file()]
        if built:
            chosen.append(max(built, key=lambda p: (p / "build" / "chunks.jsonl").stat().st_mtime))
    return chosen


def summarize(runs: Iterable[Path], runs_dir: Path, run_id: str | None = None) -> Summary:
    docs = [d for d in (load_doc(r) for r in runs) if d is not None]
    return Summary(at=datetime.now().strftime("%Y-%m-%d %H:%M"), runs_dir=str(runs_dir), run_id=run_id,
                   documents=docs)


# ----------------------------------------------------------------------------- xuất
def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "—"


def _short(token: str, limit: int = 24) -> str:
    """Token thiếu để hiển thị: ký tự hỏng U+FFFE thành `?`, cắt dòng chấm dẫn mục lục, không phá bảng markdown."""
    text = token.replace(GARBLED, "?").replace("|", "/")
    return text if len(text) <= limit else text[:limit] + "…"


def _group_text(group: str) -> str:
    return " + ".join(CAUSE_TEXT[c] for c in group.split("+"))


def render_markdown(summary: Summary) -> str:
    total, leaves = summary.statuses, summary.leaves
    lines = [
        "# Thống kê chất lượng chunk", "",
        f"- Thời điểm: {summary.at} · thư mục run: `{summary.runs_dir}` · run: {summary.run_id or 'mới nhất mỗi tài liệu'}"
        f" · {len(summary.documents)} tài liệu, {leaves} chunk lá (chunk cha không tính).",
        "- Đọc: `Bị chặn: chỉ vì OCR` là chưa kiểm chứng được, không phải lỗi phát hiện; `Bị chặn: lỗi phát hiện` có "
        "mã cụ thể và gợi ý xử lý trong `normalized/review_queue.jsonl`. Chunk có mã chặn luôn là `draft` và hiện chưa "
        "có cơ chế gỡ mã chặn.", "",
        "## Toàn bộ", "", "| Trạng thái | Chunk lá | Tỉ lệ |", "|---|---|---|",
    ]
    lines += [f"| {STATUS_TEXT[s]} | {total[s]} | {_pct(total[s], leaves)} |" for s in STATUSES]
    heads = " | ".join(s for s in STATUSES)
    lines += ["", "## Theo tài liệu", "",
              f"| Tài liệu | Run | Lá | {heads} | Cổng 2b |", "|---|---|---|" + "---|" * len(STATUSES) + "---|"]
    for d in summary.documents:
        gate = {True: "đạt", False: "không đạt", None: "chưa đủ"}[d.gate_passed] + (" (tạm)" if d.provisional else "")
        lines.append(f"| {d.doc_id} | {d.run} | {d.leaves} | " + " | ".join(str(d.statuses[s]) for s in STATUSES)
                     + f" | {gate} |")
    lines += ["", "Cột: " + "; ".join(f"`{s}` = {STATUS_TEXT[s]}" for s in STATUSES) + ".", ""]

    groups: Counter[str] = Counter()
    for d in summary.documents:
        groups.update(d.cause_groups)
    blocked = sum(groups.values())
    lines += ["## Nhóm nguyên nhân chặn", "",
              f"{blocked}/{leaves} chunk lá có mã chặn. Nhóm loại trừ nhau:", "",
              "| Nhóm | Chunk lá | Tỉ lệ trong số bị chặn |", "|---|---|---|"]
    lines += [f"| {_group_text(g)} | {n} | {_pct(n, blocked)} |" for g, n in groups.most_common()]
    causes = {k: sum(d.causes[k] for d in summary.documents) for k in CAUSES}
    lines += ["", "Theo nguyên nhân (một chunk có thể thuộc nhiều nguyên nhân): "
              + ", ".join(f"{CAUSE_TEXT[k]} {v}" for k, v in causes.items()) + ".", ""]
    codes: Counter[str] = Counter()
    for d in summary.documents:
        codes.update(d.codes)
    lines += ["| Mã chặn | Nguyên nhân | Chunk lá |", "|---|---|---|"]
    lines += [f"| `{c}` | {CAUSE_TEXT[cause_of(c)]} | {n} |" for c, n in codes.most_common()]

    gaps = [(d, g) for d in summary.documents for g in d.page_gaps]
    lines += ["", "## Trang V-01 không đạt", ""]
    if gaps:
        lines += ["| Tài liệu | Trang | Độ phủ | Lặp | Không đạt vì | Text layer hỏng (U+FFFE) | Token thiếu (mẫu) |",
                  "|---|---|---|---|---|---|---|"]
        for d, g in gaps:
            score = f"{g.score:.1%}" if g.score is not None else "—"
            dup = f"{g.duplicate_ratio:.1%}" if g.duplicate_ratio is not None else "—"
            sample = ", ".join(_short(t) for t in g.missing_sample[:4])
            lines.append(f"| {d.doc_id} | {g.page} | {score} | {dup} | {'+'.join(g.failed_by) or '—'} | "
                         f"{'có' if g.garbled_text_layer else 'không'} | {sample} |")
        by = Counter(f for _, g in gaps for f in g.failed_by)
        lines += ["", f"Tổng {len(gaps)} trang: không đạt vì độ phủ {by['coverage']}, vì lặp vượt ngưỡng {by['duplicate']}."]
    else:
        lines.append("Không có.")
    bad = [(d.doc_id, d.attribution_mismatch) for d in summary.documents if d.attribution_mismatch]
    lines += ["", "## Kiểm nhất quán", ""]
    lines.append("Mọi mã chặn đều truy được về mục review." if not bad else
                 "Chunk có mã chặn không truy được về mục review (kiểm `blocking_items`): "
                 + "; ".join(f"{doc}: {len(keys)}" for doc, keys in bad))
    return "\n".join(lines) + "\n"


CSV_COLUMNS = ("doc_id", "run", "chunk_key", "role", "chunk_type", "status", "verdict", "causes", "codes", "item_ids",
               "pages", "section", "extraction", "enrichment")


def write_outputs(summary: Summary, out_dir: Path) -> dict[str, Path]:
    """`quality_summary.md`, `quality_summary.json` (không kèm từng chunk) và `chunks.csv` (mỗi chunk lá một dòng,
    UTF-8 có BOM để Excel đọc được tiếng Việt)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"md": out_dir / "quality_summary.md", "json": out_dir / "quality_summary.json",
             "csv": out_dir / "chunks.csv"}
    paths["md"].write_text(render_markdown(summary), encoding="utf-8")
    payload = {
        "at": summary.at, "runs_dir": summary.runs_dir, "run_id": summary.run_id, "leaves": summary.leaves,
        "statuses": dict(summary.statuses),
        "documents": [{k: v for k, v in asdict(d).items() if k != "rows"} for d in summary.documents],
    }
    paths["json"].write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    with paths["csv"].open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for d in summary.documents:
            for r in d.rows:
                writer.writerow([r.doc_id, r.run, r.chunk_key, r.role, r.chunk_type, r.status, r.verdict,
                                 "+".join(r.causes), " ".join(r.codes), " ".join(r.item_ids),
                                 " ".join(str(p) for p in r.pages), r.section, r.extraction, r.enrichment])
    return paths


def console_table(summary: Summary) -> str:
    """Bảng ngắn để in ra terminal."""
    short = {"approved": "duyệt", "reviewed_ok": "ok-chờ", "needs_fix": "fix", "stale": "cũ",
             "blocked_defect": "chặn-lỗi", "blocked_ocr": "chặn-OCR", "pending": "chờ"}
    head = f"{'tài liệu':26} {'lá':>4} " + " ".join(f"{short[s]:>8}" for s in STATUSES)
    body = [f"{d.doc_id[:26]:26} {d.leaves:4} " + " ".join(f"{d.statuses[s]:8}" for s in STATUSES)
            for d in summary.documents]
    total = summary.statuses
    foot = f"{'TỔNG':26} {summary.leaves:4} " + " ".join(f"{total[s]:8}" for s in STATUSES)
    return "\n".join([head, *body, foot])
