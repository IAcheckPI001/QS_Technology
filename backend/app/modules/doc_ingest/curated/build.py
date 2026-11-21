"""`curated-build`: dữ liệu biên soạn đã duyệt → `DraftChunk` (`source = manual`) → `doc_chunks_v2.jsonl`.

Nguyên tắc nội dung (Toma 2026-11-14): **bám sát nội dung PDF**. `content` dựng lại tiêu đề mục, nhãn và giá trị như in
trên trang, theo thứ tự in; chỉ khôi phục cặp "nhãn: giá trị" mà pipeline tách (I-48) và giá trị bị T-17 loại. Không
thêm câu, không dịch. Ngoại lệ: giá trị đã chốt khác bản in (C-xx) → in giá trị đã chốt và ghi `curated_decisions`.
Nhãn tiếng Việt do người biên soạn đặt (`vi`) không vào `content`; chỉ vào `keywords` khi bật `vi_keywords`.

Ranh giới chunk theo mục trên trang PDF (đều `standalone`):
- trang riêng model: phần trên (`overview`) và "THÔNG SỐ KỸ THUẬT (SPECIFICATIONS)" (`spec`);
- khối "QS - <MODEL> CONTROLLER" (trang tóm tắt) + khối "MODEL: <MODEL>" (trang trọn bộ) (`overview`);
- bảng chọn "MOTION CONTROLLER – Selection table": mỗi nhóm hàng của mỗi trang một chunk (`table`).
"""

from __future__ import annotations

import hashlib
import html
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.modules.doc_ingest.curated.schema import (
    MatrixRow, ProductSheet, Scalar, SelectionMatrix, Spec, Value,
)
from app.modules.doc_ingest.export.doc_chunks_v2 import ApprovalContext, export_rows, ok_hashes
from app.modules.doc_ingest.schemas.chunk import ChunkReviewEntry, ChunkReviewFile, CuratedDecision, DraftChunk

DOC_ID = "qs_product_catalogue"
DOC_TYPE = "product_catalogue"
DOC_TITLE = "QS Product Catalogue"
LANG = "vi,en"
EMBED_MAX_TOKENS = 800

# Mục trên trang riêng model (catalog trang 8–14): key → mục, theo thứ tự in.
HEADER_KEYS = ("dimension", "monitor_size", "axis_control", "io_link")
CONNECTION_KEYS = ("connection_type", "io_integrated", "usb_port", "mpg_port", "voltage_input")
SOFTWARE_KEYS = ("control_system", "plc_ladder", "macro", "backlash_compensation", "pitch_error_compensation",
                 "encoder_feedback", "torque_feedback", "servo_parameter_management")
AXIS_KEYS = ("feedrate_override", "feedrate_interpolation", "pulse_output_frequency", "mpg_feed",
             "rotary_axis_endless", "max_spindle", "look_ahead")
SECTION_KEYS = {*HEADER_KEYS, *CONNECTION_KEYS, *SOFTWARE_KEYS, *AXIS_KEYS}
COMBINED = ("backlash_compensation", "pitch_error_compensation")
COMBINED_LABEL = "Backlash/Pitch error compensation"
# Tên giao tiếp như in trong nhãn trang riêng model ("Encoder feedback (EtherCAT, MII/MIII)").
IFACE_LABEL = {"pulse_train": "Pulse Train", "ethercat": "EtherCAT", "mechatrolink": "MII/MIII"}
# Tiêu đề cột con của bảng chọn như in.
IFACE_COLUMN = {"pulse_train": "Pulse Train (Standard)", "ethercat": "EtherCAT (Optional)",
                "mechatrolink": "Mechatrolink MII/MIII (Optional)"}
# key thông số → `spec_attributes` (từ vựng registry chatbot, qua registry_snapshot).
SPEC_ATTRIBUTE = {
    "dimension": "dimension", "monitor_size": "monitor_size", "monitor": "monitor_size", "axis_control": "max_axis",
    "max_plc_axis": "max_axis", "io_link": "io", "io_integrated": "io", "standard_io": "io", "max_option_io": "io",
    "control_system": "loop_type", "system_control": "loop_type", "look_ahead": "look_ahead",
    "max_spindle": "spindle", "max_analog_spindle": "spindle", "max_spindle_simultaneous": "spindle",
    "rtcp": "rtcp", "usb_port": "ports", "mpg_port": "ports", "rs485": "ports",
}


@dataclass
class CuratedBuild:
    chunks: list[DraftChunk]
    unverified: list[str] = field(default_factory=list)      # giá trị bị loại vì chưa duyệt
    proposed_keywords_vi: dict[str, list[str]] = field(default_factory=dict)   # chunk_key -> nhãn vi (chưa dùng)
    over_budget: list[str] = field(default_factory=list)


@dataclass
class _Draft:
    chunk_type: str
    section_path: list[str]
    pages: list[int]
    models: list[str]
    interfaces: list[str]
    content: str
    attributes: list[str]
    keywords_vi: list[str]
    decisions: list[CuratedDecision]
    extraction: str = "text_layer"


# ----------------------------------------------------------------------------- hiển thị giá trị
def _scalar(value: Scalar) -> str:
    if value is True:
        return "✓"
    if value is False:
        return "✗"
    return "(Option)" if value == "option" else str(value)


def _grouped(value: dict[str, Scalar]) -> list[tuple[list[str], Scalar]]:
    """Gom giao tiếp cùng giá trị, giữ thứ tự: {pt: 1, ec: 2, ml: 2} → [([pt], 1), ([ec, ml], 2)]."""
    groups: list[tuple[list[str], Scalar]] = []
    for iface, v in value.items():
        for names, existing in groups:
            if existing == v:
                names.append(iface)
                break
        else:
            groups.append(([iface], v))
    return groups


def _spec_lines(spec: Spec) -> list[str]:
    """Dòng "nhãn: giá trị" như trang riêng model in; giá trị theo giao tiếp → mỗi nhóm giao tiếp một dòng."""
    value = spec.value
    if not isinstance(value, dict):
        return [f"{spec.en}: {value}"]
    groups = _grouped(value)
    if len(groups) == 1:
        return [f"{spec.en}: {groups[0][1]}"]
    return [f"{spec.en} ({', '.join(IFACE_LABEL[i] for i in names)}): {v}" for names, v in groups]


def _decision(spec: Spec, model: str) -> CuratedDecision | None:
    if spec.decision is None:
        return None
    value = spec.value if not isinstance(spec.value, dict) else "; ".join(
        f"{', '.join(IFACE_LABEL[i] for i in n)}: {v}" for n, v in _grouped(spec.value))
    return CuratedDecision(code=spec.decision, key=spec.key, value=str(value), page_value=spec.page_value, model=model)


def _bullets(items: Sequence[str]) -> list[str]:
    return [f"- {item}" for item in items]


# ----------------------------------------------------------------------------- chunk của một model
def _specs(sheet: ProductSheet, keys: Sequence[str], skipped: list[str]) -> list[Spec]:
    by_key = {s.key: s for s in sheet.specs}
    out = []
    for key in keys:
        spec = by_key.get(key)
        if spec is None:
            continue
        if not spec.verified:
            skipped.append(f"{sheet.model}/{key}")
            continue
        out.append(spec)
    return out


def _spec_block(sheet: ProductSheet, keys: Sequence[str], skipped: list[str]
                ) -> tuple[list[str], list[str], list[CuratedDecision], list[str]]:
    """(dòng, nhãn vi, quyết định, spec_attributes). Backlash/Pitch: một dòng gộp như in khi cùng giá trị."""
    specs = _specs(sheet, keys, skipped)
    by_key = {s.key: s for s in specs}
    lines: list[str] = []
    vi: list[str] = []
    decisions: list[CuratedDecision] = []
    attrs: list[str] = []
    for spec in specs:
        pair = [by_key[k] for k in COMBINED if k in by_key]
        if spec.key in COMBINED and len(pair) == 2:
            if spec.key == COMBINED[1]:
                continue
            backlash, pitch = pair
            if backlash.value == pitch.value and not isinstance(backlash.value, dict):
                lines.append(f"{COMBINED_LABEL}: {backlash.value}")
            else:
                lines += _spec_lines(backlash) + _spec_lines(pitch)
            for s in pair:
                vi.append(s.vi)
                if (d := _decision(s, sheet.model)) is not None:
                    decisions.append(d)
            continue
        lines += _spec_lines(spec)
        vi.append(spec.vi)
        if (d := _decision(spec, sheet.model)) is not None:
            decisions.append(d)
        if (a := SPEC_ATTRIBUTE.get(spec.key)) is not None and a not in attrs:
            attrs.append(a)
    return lines, vi, decisions, attrs


def _product_drafts(sheet: ProductSheet, skipped: list[str]) -> list[_Draft]:
    unknown = sorted({s.key for s in sheet.specs} - SECTION_KEYS)
    if unknown:
        raise ValueError(f"{sheet.model}: key chưa xếp mục {unknown}")
    title = sheet.heading.title
    drafts: list[_Draft] = []

    # 1) Trang riêng model, phần trên: tiêu đề + đầu trang, tính năng, kết nối, giao diện vận hành.
    head, head_vi, head_dec, head_attr = _spec_block(sheet, HEADER_KEYS, skipped)
    conn, conn_vi, conn_dec, conn_attr = _spec_block(sheet, CONNECTION_KEYS, skipped)
    lines = [title, sheet.heading.subtitle, *_bullets(head), f"- {sheet.heading.interfaces}"]
    if sheet.features.verified:
        lines += ["TÍNH NĂNG NỔI BẬT", *_bullets(sheet.features.vi), "ADVANCED FEATURES", *_bullets(sheet.features.en)]
    else:
        skipped.append(f"{sheet.model}/features")
    lines += ["KẾT NỐI (CONNECTION)", *_bullets(conn)]
    if sheet.operation_interface.verified:
        lines += ["GIAO DIỆN VẬN HÀNH (OPERATION INTERFACE)", *_bullets(sheet.operation_interface.vi),
                  *_bullets(sheet.operation_interface.en)]
    else:
        skipped.append(f"{sheet.model}/operation_interface")
    page = sheet.heading.page
    drafts.append(_Draft("overview", ["MOTION CONTROLLER", title], [page], [sheet.model],
                         list(sheet.control_interface), "\n".join(lines),
                         _merge(head_attr, conn_attr), head_vi + conn_vi, head_dec + conn_dec))

    # 2) Trang riêng model: THÔNG SỐ KỸ THUẬT (SPECIFICATIONS).
    soft, soft_vi, soft_dec, soft_attr = _spec_block(sheet, SOFTWARE_KEYS, skipped)
    axis, axis_vi, axis_dec, axis_attr = _spec_block(sheet, AXIS_KEYS, skipped)
    lines = [title, "THÔNG SỐ KỸ THUẬT (SPECIFICATIONS)", "Phần mềm (Software)", *_bullets(soft),
             "Thông số trục (Axis)", *_bullets(axis)]
    drafts.append(_Draft("spec", ["MOTION CONTROLLER", title, "THÔNG SỐ KỸ THUẬT (SPECIFICATIONS)"], [page],
                         [sheet.model], list(sheet.control_interface), "\n".join(lines),
                         _merge(soft_attr, axis_attr), soft_vi + axis_vi, soft_dec + axis_dec))

    # 3) Trang tóm tắt + trang trọn bộ hệ thống.
    sp, pkg = sheet.summary_page, sheet.system_package
    lines = []
    pages = []
    if sp.verified:
        lines += ["QS MOTION CONTROLLER", sp.heading, *_bullets(sp.items)]
        pages.append(sp.page)
    else:
        skipped.append(f"{sheet.model}/summary_page")
    if pkg.verified:
        lines += ["CNC SOLUTION CONTROLLER", pkg.label, "Specifications", *_bullets(pkg.specifications),
                  "Control interface", *_bullets(pkg.control_interface), *_bullets(pkg.items)]
        pages.append(pkg.page)
    else:
        skipped.append(f"{sheet.model}/system_package")
    if lines:
        drafts.append(_Draft("overview", ["MOTION CONTROLLER", sp.heading], sorted(pages), [sheet.model],
                             list(sheet.control_interface), "\n".join(lines), list(sheet.spec_attributes), [], []))
    return drafts


def _merge(*lists: Sequence[str]) -> list[str]:
    out: list[str] = []
    for items in lists:
        out += [x for x in items if x not in out]
    return out


# ----------------------------------------------------------------------------- bảng chọn
def _matrix_cell(matrix: SelectionMatrix, row: MatrixRow, models: Sequence[str]) -> str:
    """Ô của một cột in (một hoặc nhiều model cùng cột, vd. ASTRO 6AV/H)."""
    values = [(m, matrix.value(row, m)) for m in models]
    if len(models) > 1 and any(v != values[0][1] for _, v in values):
        return "; ".join(f"{m}: {_cell(v)}" for m, v in values)
    return _cell(values[0][1])


def _cell(value: Value) -> str:
    if not isinstance(value, dict):
        return _scalar(value)
    groups = _grouped(value)
    if len(groups) == 1:
        return _scalar(groups[0][1])
    if all(isinstance(v, str) and v.startswith(IFACE_COLUMN[n[0]].split(" ")[0]) for n, v in groups):
        return " · ".join(_scalar(v) for _, v in groups)      # ô tự nêu giao tiếp (hàng Control Interface)
    return " · ".join(f"{' / '.join(IFACE_COLUMN[i].split(' (')[0] for i in names)}: {_scalar(v)}"
                      for names, v in groups)


def _matrix_drafts(matrix: SelectionMatrix, skipped: list[str]) -> list[_Draft]:
    drafts: list[_Draft] = []
    for page in sorted({m.page for m in matrix.models.values()}):
        columns: dict[str, list[str]] = {}
        for model, meta in matrix.models.items():
            if meta.page == page:
                columns.setdefault(meta.column, []).append(model)
        models = [m for ms in columns.values() for m in ms]
        interfaces = _merge(*(matrix.models[m].interfaces for m in models))
        groups: dict[str, list[MatrixRow]] = {}
        for row in matrix.rows:
            groups.setdefault(row.group, []).append(row)
        for group, rows in groups.items():
            header = "| Specification | " + " | ".join(columns) + " |"
            lines = ["MOTION CONTROLLER", "Selection table", group, header,
                     "|" + "---|" * (len(columns) + 1)]
            vi: list[str] = []
            decisions: list[CuratedDecision] = []
            attrs: list[str] = []
            for row in rows:
                if not row.verified:
                    skipped.append(f"matrix/{row.key}")
                    continue
                cells = [_matrix_cell(matrix, row, ms) for ms in columns.values()]
                lines.append(f"| {row.en} | " + " | ".join(cells) + " |")
                vi.append(row.vi)
                if (a := SPEC_ATTRIBUTE.get(row.key)) is not None and a not in attrs:
                    attrs.append(a)
                for model, ov in row.override.items():
                    if model in models:
                        decisions.append(CuratedDecision(code=ov.decision, key=row.key, model=model,
                                                         value=_cell(matrix.value(row, model)),
                                                         page_value=_scalar(ov.table_value)))
            if len(lines) > 5:
                drafts.append(_Draft("table", ["MOTION CONTROLLER", "Selection table", group], [page], models,
                                     interfaces, "\n".join(lines), attrs, vi, decisions, extraction="mixed"))
    return drafts


# ----------------------------------------------------------------------------- lắp DraftChunk
def _embed(models: Sequence[str], path: Sequence[str], keywords: Sequence[str], content: str) -> str:
    head = [f"{', '.join(models)} · {DOC_TITLE} · {' › '.join(path)}"]
    if keywords:
        head.append(f"Từ khóa: {', '.join(keywords)}")
    head.append("---")
    return "\n".join(head + [content])


def build_chunks(products: Sequence[ProductSheet], matrix: SelectionMatrix, doc_version: str,
                 counter: Callable[[str], int] | None = None, vi_keywords: bool = False) -> CuratedBuild:
    skipped: list[str] = []
    ordered = sorted(products, key=lambda p: p.heading.page)
    display = {p.model: [p.model, p.heading.title] for p in ordered}
    drafts = [d for sheet in ordered for d in _product_drafts(sheet, skipped)] + _matrix_drafts(matrix, skipped)
    result = CuratedBuild(chunks=[], unverified=skipped)
    for index, d in enumerate(drafts):
        key = f"{DOC_ID}:C{index:04d}"
        keywords = _merge(*(display.get(m, [m]) for m in d.models))
        vi = _merge(d.keywords_vi)
        if vi_keywords:
            keywords = _merge(keywords, vi)
        elif vi:
            result.proposed_keywords_vi[key] = vi
        embed = _embed(d.models, d.section_path, keywords, d.content)
        tokens = counter(embed) if counter else None
        flags = ["curated"]
        if tokens is not None and tokens > EMBED_MAX_TOKENS:
            flags.append("embed_over_budget")
            result.over_budget.append(key)
        result.chunks.append(DraftChunk(
            chunk_key=key, chunk_role="standalone", source="manual", chunk_index=index,
            domain="product_catalog", scopes=[], product_models=list(d.models),
            # Giao tiếp model hỗ trợ (cấp sản phẩm), không suy từ chữ của chunk.
            control_interface=list(d.interfaces),
            spec_attributes=list(d.attributes), chunk_type=d.chunk_type,  # type: ignore[arg-type]
            doc_id=DOC_ID, doc_type=DOC_TYPE, doc_title=DOC_TITLE, doc_version=doc_version, lang=LANG,
            audience="public",   # catalog công ty đã công bố cho khách
            section_path=list(d.section_path), section_title=" › ".join(d.section_path[1:]) or d.section_path[0],
            page_start=min(d.pages), page_end=max(d.pages), content=d.content, keywords=keywords,
            embed_text=embed, token_count=tokens,
            content_hash=hashlib.sha256(d.content.encode("utf-8")).hexdigest(),
            extraction=d.extraction,  # type: ignore[arg-type]
            flags=flags, curated_decisions=list(d.decisions),
        ))
    return result


# ----------------------------------------------------------------------------- ghi kết quả
def review_template(chunks: Sequence[DraftChunk], previous: ChunkReviewFile | None) -> ChunkReviewFile:
    """Giữ verdict cũ khi `content_hash` không đổi (cùng chunk_key)."""
    old = {e.chunk_key: e for e in (previous.reviews if previous else [])}
    reviews = []
    for c in chunks:
        prev = old.get(c.chunk_key)
        if prev is not None and prev.content_hash == c.content_hash:
            reviews.append(prev)
        else:
            reviews.append(ChunkReviewEntry(chunk_key=c.chunk_key, content_hash=c.content_hash))
    return ChunkReviewFile(doc_id=DOC_ID, reviews=reviews)


def write_build(result: CuratedBuild, out_dir: Path, source_run: str, all_verified: bool) -> dict:
    build = out_dir / "build"
    build.mkdir(parents=True, exist_ok=True)
    (build / "chunks.jsonl").write_text("".join(c.model_dump_json() + "\n" for c in result.chunks), encoding="utf-8")
    review_path = build / "chunk_review.json"
    previous = (ChunkReviewFile.model_validate_json(review_path.read_text(encoding="utf-8"))
                if review_path.is_file() else None)
    review = review_template(result.chunks, previous)
    review_path.write_text(review.model_dump_json(indent=1) + "\n", encoding="utf-8")
    ctx = ApprovalContext(gate_2b_final=False, ok_hashes=ok_hashes(review), curated_verified=all_verified)
    rows, errors = export_rows(result.chunks, ctx, source_run)
    (build / "doc_chunks_v2.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    status: dict[str, int] = {}
    for r in rows:
        status[r["review_status"]] = status.get(r["review_status"], 0) + 1
    summary = {"chunks": len(result.chunks), "export_errors": errors, "review_status": status,
               "unverified": result.unverified, "over_budget": result.over_budget,
               "verdicts": {v: sum(1 for e in review.reviews if e.verdict == v) for v in ("ok", "fix", "pending")}}
    (build / "curated_build.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
                                              encoding="utf-8")
    report = out_dir / "report" / "chunks.html"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(result, review, summary), encoding="utf-8")
    return summary


def render_report(result: CuratedBuild, review: ChunkReviewFile, summary: dict) -> str:
    e = html.escape
    verdict = {r.chunk_key: r.verdict for r in review.reviews}
    cards = []
    for c in result.chunks:
        decisions = "".join(f"<li>{e(d.code)} · {e(d.model or '')} · {e(d.key)}: <b>{e(d.value)}</b>"
                            f"{f' (in: {e(d.page_value)})' if d.page_value else ''}</li>" for d in c.curated_decisions)
        proposed = result.proposed_keywords_vi.get(c.chunk_key, [])
        cards.append(
            f"<section class='card'><h3>{e(c.chunk_key)} · {e(c.chunk_type)} · {e(c.section_title)}</h3>"
            f"<p>Model: {e(', '.join(c.product_models))} · trang {c.page_start}"
            f"{'' if c.page_end == c.page_start else '–' + str(c.page_end)} · token {c.token_count} · "
            f"giao tiếp: {e(', '.join(c.control_interface))} · spec_attributes: {e(', '.join(c.spec_attributes))} · "
            f"verdict: <b>{e(verdict.get(c.chunk_key, 'pending'))}</b></p>"
            f"<p>Từ khóa: {e(', '.join(c.keywords))}</p>"
            + (f"<p class='muted'>Từ khóa tiếng Việt đề xuất (chưa dùng): {e(', '.join(proposed))}</p>" if proposed else "")
            + (f"<p>Giá trị đã chốt khác bản in:</p><ul>{decisions}</ul>" if decisions else "")
            + f"<pre>{e(c.content)}</pre></section>")
    head = (f"<p>Chunk: {summary['chunks']} · trạng thái: {e(json.dumps(summary['review_status']))} · "
            f"verdict: {e(json.dumps(summary['verdicts']))} · lỗi ràng buộc: {len(summary['export_errors'])} · "
            f"giá trị chưa duyệt bị loại: {len(summary['unverified'])} · vượt {EMBED_MAX_TOKENS} token: "
            f"{len(summary['over_budget'])}</p>")
    return ("<!doctype html><html lang='vi'><meta charset='utf-8'><title>Chunk biên soạn – catalog</title>"
            "<style>body{font-family:system-ui,sans-serif;margin:24px;max-width:1100px}"
            ".card{border:1px solid #ccc;border-radius:6px;padding:8px 14px;margin:12px 0}"
            "pre{white-space:pre-wrap;background:#f6f6f6;padding:8px}.muted{color:#666}</style>"
            f"<h1>Chunk biên soạn – {e(DOC_TITLE)}</h1>{head}{''.join(cards)}</html>")
