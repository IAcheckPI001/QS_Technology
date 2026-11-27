"""`curate-check`: kiểm dữ liệu biên soạn với PDF nguồn (qua run `run` của tài liệu đó) và giữa các file.

Kiểm:
- (a) schema (lúc nạp), (b) số giá trị chưa `verified`;
- (c) chữ in: mọi giá trị/nhãn `origin: text|recovered` có nguyên văn trong chữ trang nguồn (`elements.jsonl`, kể cả
  phần tử bị T-17 loại thành furniture); `page_value` được dùng thay giá trị đã chốt; không khớp nguyên văn nhưng đủ
  từ (thứ tự khác do đọc bố cục) → `reordered`, không tính lỗi;
- (d) key trùng giữa file sản phẩm và bảng chọn phải cùng giá trị;
- (e) `sha256` nguồn khớp `run_report.json` của run.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from app.modules.doc_ingest.curated.schema import ProductSheet, SelectionMatrix, Spec, Value

# key file sản phẩm → key bảng chọn (cùng thông số)
MATRIX_PAIRS: dict[str, str] = {
    "dimension": "dimension", "look_ahead": "look_ahead", "control_system": "system_control",
    "usb_port": "usb_port", "io_link": "standard_io", "backlash_compensation": "backlash_compensation",
    "pitch_error_compensation": "pitch_error_compensation",
}
# Trang riêng model in một dòng gộp cho hai thông số (tách theo C-01 để ghi giá trị riêng).
COMBINED_LABELS: dict[str, str] = {
    "backlash_compensation": "Backlash/Pitch error compensation",
    "pitch_error_compensation": "Backlash/Pitch error compensation",
}
_WS = re.compile(r"\s+")
_WORD = re.compile(r"[\w.%+-]+", re.UNICODE)


def norm(text: str) -> str:
    return _WS.sub(" ", text).strip().casefold()


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def page_texts(run_dir: Path) -> dict[int, str]:
    """Chữ đã chuẩn hóa của từng trang: nối mọi phần tử có chữ (gồm furniture/figure_text) theo thứ tự đọc, chữ các ô
    bảng (`tables.jsonl`, bảng gán vào trang của đoạn đầu), rồi toàn bộ từ của text layer PDF (`raw/p{n}.words.json`
    — chữ mà Docling gộp/làm mất ô vẫn có ở đây; thứ tự từ không theo đọc nên chỉ khớp ở mức `reordered`)."""
    pages: dict[int, list[str]] = {}
    for path in sorted((run_dir / "raw").glob("p*.words.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        pages.setdefault(data["pdf_page_index"], []).append(" ".join(w["text"] for w in data.get("words", [])))
    rows = _jsonl(run_dir / "normalized" / "elements.jsonl")
    for row in sorted(rows, key=lambda r: (r["pdf_page_index"], r["reading_order"])):
        if row.get("text"):
            pages.setdefault(row["pdf_page_index"], []).append(row["text"])
    for table in _jsonl(run_dir / "normalized" / "tables.jsonl"):
        page = table["segments"][0]["pdf_page_index"]
        pages.setdefault(page, []).extend(
            cell["text"] for row in table["rows"] for cell in row["cells"] if cell.get("text"))
        pages[page].extend(c["header_text"] for c in table.get("columns", []) if c.get("header_text"))
    return {page: norm(" ".join(texts)) for page, texts in pages.items()}


def text_status(text: str, page_text: str) -> str:
    """`ok` (nguyên văn), `reordered` (đủ từ, khác thứ tự), `missing`."""
    probe = norm(text)
    if probe in page_text:
        return "ok"
    words = set(_WORD.findall(page_text))
    return "reordered" if all(w in words for w in _WORD.findall(probe)) else "missing"


@dataclass
class CheckReport:
    unverified: list[str] = field(default_factory=list)
    text_missing: list[str] = field(default_factory=list)
    text_reordered: list[str] = field(default_factory=list)
    matrix_mismatch: list[str] = field(default_factory=list)
    source_mismatch: list[str] = field(default_factory=list)
    checked_texts: int = 0

    @property
    def passed(self) -> bool:
        return not (self.unverified or self.text_missing or self.matrix_mismatch or self.source_mismatch)


def _texts_of_spec(spec: Spec) -> Iterable[str]:
    """Chuỗi in trên trang của một spec: nhãn + giá trị (hoặc `page_value`). Giá trị Yes/No không kiểm (quá chung)."""
    yield COMBINED_LABELS.get(spec.key, spec.en.split(" (")[0])
    printed = spec.page_value if spec.page_value is not None else spec.value
    if isinstance(printed, str) and printed not in ("Yes", "No") and spec.decision is None:
        yield printed


def _product_texts(sheet: ProductSheet) -> Iterable[tuple[str, int, str]]:
    """(mô tả, trang, chuỗi) cần có trong chữ PDF."""
    h = sheet.heading
    for text in (h.title, h.subtitle, h.interfaces):
        yield f"{sheet.model}/heading", h.page, text
    for spec in sheet.specs:
        if spec.origin == "image":
            continue
        for text in _texts_of_spec(spec):
            yield f"{sheet.model}/{spec.key}", spec.page, text
    for block_name in ("features", "operation_interface"):
        block = getattr(sheet, block_name)
        for text in [*block.vi, *block.en]:
            yield f"{sheet.model}/{block_name}", block.page, text
    sp = sheet.summary_page
    for text in [sp.heading, *sp.items]:
        yield f"{sheet.model}/summary_page", sp.page, text
    pkg = sheet.system_package
    for text in [pkg.label, *pkg.specifications, *pkg.control_interface, *pkg.items]:
        yield f"{sheet.model}/system_package", pkg.page, text


def _matrix_texts(matrix: SelectionMatrix) -> Iterable[tuple[str, int, str]]:
    """Nhóm, nhãn hàng, tên cột và giá trị chữ của bảng chọn (bỏ icon ✓/✗, "option", ô đã override)."""
    for page in sorted({m.page for m in matrix.models.values()}):
        models = [name for name, m in matrix.models.items() if m.page == page]
        for name in models:
            yield f"matrix/column/{name}", page, matrix.models[name].column
        for row in matrix.rows:
            yield f"matrix/{row.key}/group", page, row.group
            yield f"matrix/{row.key}", page, row.en
            for model in models:
                if model in row.override:
                    continue
                value = matrix.value(row, model)
                for v in (value.values() if isinstance(value, dict) else [value]):
                    if isinstance(v, str) and v != "option":
                        yield f"matrix/{row.key}/{model}", page, v


def content_issues(chunks: Iterable, pages: Mapping[int, str]) -> list[str]:
    """Kiểm "bám sát PDF" trên `content` đã sinh: mọi từ của mỗi dòng phải có trong chữ các trang nguồn của chunk,
    trừ ký hiệu bảng (|, ✓, ✗, ---), giá trị Yes/No, tên giao tiếp và giá trị đã chốt khác bản in (`curated_decisions`).
    Trả về các dòng có từ lạ."""
    issues = []
    allowed = {"yes", "no", "option", "pulse", "train", "ethercat", "mii", "miii", "mechatrolink", "-", "·"}
    for chunk in chunks:
        words = {m.casefold() for m in chunk.product_models}   # nhãn model trong ô gộp (vd. cột ASTRO 6AV/H)
        numbers = set(range(chunk.page_start, chunk.page_end + 1))
        for flag in getattr(chunk, "flags", []):               # chunk ghép trang rời nhau (trang tóm tắt + trang trọn bộ)
            if flag.startswith("source_pages:"):
                numbers |= {int(p) for p in flag.split(":", 1)[1].split(",") if p.strip().isdigit()}
        for page in sorted(numbers):
            words |= set(_WORD.findall(pages.get(page, "")))
        for d in chunk.curated_decisions:
            words |= set(_WORD.findall(norm(f"{d.model or ''} {d.value}")))
        for line in chunk.content.split("\n"):
            probe = norm(line.replace("✓", " ").replace("✗", " ").replace("|", " ").replace("---", " "))
            strange = [w for w in _WORD.findall(probe) if w not in words and w not in allowed]
            if strange:
                issues.append(f"{chunk.chunk_key}: {line!r} → {strange}")
    return issues


def _unverified(sheet: ProductSheet) -> Iterable[str]:
    for name in ("heading", "summary_page", "features", "operation_interface", "system_package"):
        if not getattr(sheet, name).verified:
            yield f"{sheet.model}/{name}"
    for spec in sheet.specs:
        if not spec.verified:
            yield f"{sheet.model}/{spec.key}"


def _canon(value: Value) -> dict[str, str]:
    """Giá trị so sánh: bỏ " lines", Yes/No ↔ true/false; giá trị đơn → khóa "*"."""
    items = value.items() if isinstance(value, dict) else [("*", value)]
    out = {}
    for key, v in items:
        text = str(v).casefold().replace(" lines", "")
        out[key] = {"yes": "true", "no": "false"}.get(text, text)
    return out


def _same(a: Value, b: Value) -> bool:
    ca, cb = _canon(a), _canon(b)
    return set(ca.values()) == set(cb.values()) and (len(set(ca.values())) == 1 or ca == cb)


def check(products: list[ProductSheet], matrix: SelectionMatrix, pages: Mapping[int, str] | None = None,
          run_sha256: str | None = None) -> CheckReport:
    report = CheckReport()
    for sheet in products:
        report.unverified += list(_unverified(sheet))
        if pages is not None:
            for where, page, text in _product_texts(sheet):
                report.checked_texts += 1
                status = text_status(text, pages.get(page, ""))
                if status == "missing":
                    report.text_missing.append(f"{where} (trang {page}): {text!r}")
                elif status == "reordered":
                    report.text_reordered.append(f"{where} (trang {page}): {text!r}")
        rows = {r.key: r for r in matrix.rows}
        for spec in sheet.specs:
            pair = MATRIX_PAIRS.get(spec.key)
            if pair is None or sheet.model not in matrix.models:
                continue
            table = matrix.value(rows[pair], sheet.model)
            if not _same(spec.value, table):
                report.matrix_mismatch.append(f"{sheet.model}/{spec.key}: file={spec.value!r} bảng={table!r}")
        if run_sha256 is not None:
            for name, source in sheet.sources.items():
                if source.sha256 != run_sha256:
                    report.source_mismatch.append(f"{sheet.model}/{name}: sha256 khác run")
    report.unverified += [f"matrix/{r.key}" for r in matrix.rows if not r.verified]
    if pages is not None:
        for where, page, text in _matrix_texts(matrix):
            report.checked_texts += 1
            status = text_status(text, pages.get(page, ""))
            if status == "missing":
                report.text_missing.append(f"{where} (trang {page}): {text!r}")
            elif status == "reordered":
                report.text_reordered.append(f"{where} (trang {page}): {text!r}")
    if run_sha256 is not None and matrix.source.sha256 != run_sha256:
        report.source_mismatch.append("matrix: sha256 khác run")
    return report


def run_sha256(run_dir: Path) -> str | None:
    report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8"))
    return (report.get("source") or {}).get("pdf_sha256")
