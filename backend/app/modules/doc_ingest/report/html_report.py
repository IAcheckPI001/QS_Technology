"""Dựng `report/index.html` từ kết quả chạy: một file tự chứa, CSS inline, không script.

Nguyên tắc hiển thị:
- Bước chưa có code ghi "chưa triển khai", không giả lập kết quả.
- Applicability ở lớp chuẩn hóa là **ứng viên T-13**, không phải fact; fact thuộc BL-17.
- `logical_table_id` là định danh của lần chạy; so giữa các lần chạy bằng content hash.
- Chữ OCR trong hình (`figure_text`) gom dưới picture, ghi rõ chưa duyệt; không vẽ nhãn từng mảnh.
- Hình: ảnh crop (T-14) là nội dung có thẩm quyền; chữ trong/sát hình chỉ là từ khóa, không phải fact.
"""

from __future__ import annotations

import html
from collections.abc import Sequence

from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.pipeline import RunResult, doc_page
from app.modules.doc_ingest.schemas.normalized import (
    LogEntry, LogicalTable, NormalizedElement, ReviewItem, Row, ValidationResult,
)
from app.modules.doc_ingest.schemas.run import RunReport

LABEL_COLORS = {
    "section_header": "#d62728", "title": "#d62728", "text": "#1f77b4", "list_item": "#17becf",
    "table": "#2ca02c", "picture": "#ff7f0e", "caption": "#9467bd", "page_header": "#7f7f7f",
    "page_footer": "#7f7f7f", "footnote": "#8c564b", "formula": "#e377c2",
}
STATUS_TEXT = {"implemented": "đã có", "partial": "một phần", "not_implemented": "chưa triển khai"}

_STYLE = """
:root{--fg:#1d1d1f;--muted:#5f6368;--line:#d0d4d9;--bg:#fff;--soft:#f5f6f8}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;color:var(--fg);background:var(--bg)}
main{max-width:1400px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:8px 0}h2{font-size:18px;margin:28px 0 8px;border-bottom:2px solid var(--line)}
h3{font-size:15px;margin:18px 0 6px}
nav a{margin-right:12px}
table.t{border-collapse:collapse;margin:6px 0;font-size:13px}
table.t th,table.t td{border:1px solid var(--line);padding:3px 6px;vertical-align:top;text-align:left}
table.t th{background:var(--soft)}
.muted{color:var(--muted);font-size:12px}
.badge{display:inline-block;padding:0 6px;border-radius:9px;font-size:12px;border:1px solid var(--line);margin:1px}
.st-implemented{background:#e6f4ea}.st-partial{background:#fef7e0}.st-not_implemented{background:#f1f3f4;color:var(--muted)}
.blocking{background:#fce8e6}
.cand{border:1px dashed #b06000;background:#fff8ec;color:#5f3b00}
.warn{background:#fef7e0;border-left:4px solid #f9ab00;padding:4px 8px;margin:6px 0}
.pair{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}
.pair>div{min-width:0;overflow-x:auto}
td.hdr{background:#e8f0fe;font-weight:600}td.rep{background:#e8f0fe;font-style:italic;color:var(--muted)}
td.demoted{outline:2px solid #e37400}td.moved{background:#fff3c4}td.empty{background:#f1f3f4;color:var(--muted)}
tr.merged td{box-shadow:inset 3px 0 0 #188038}
.page svg{max-width:100%;height:auto;border:1px solid var(--line);background:#fff}
.legend span{margin-right:10px}
.path{color:var(--muted);font-size:12px}
.figs{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.fig{border:1px solid var(--line);padding:8px;min-width:0}
.fig img{max-width:100%;height:auto;border:1px solid var(--line);background:#fff}
"""


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _anchor(table_id: str) -> str:
    return "t-" + "".join(ch if ch.isalnum() else "-" for ch in table_id)


def _belongs(item_target: str | None, table: LogicalTable) -> bool:
    return item_target is not None and (item_target == table.logical_table_id
                                        or item_target.startswith(table.logical_table_id + ":"))


def _table_review(review: Sequence[ReviewItem], table: LogicalTable) -> list[ReviewItem]:
    elements = {s.element_id for s in table.segments}
    return [r for r in review if _belongs(r.target, table) or (r.target is None and r.element_id in elements)]


def _table_log(log: Sequence[LogEntry], table: LogicalTable) -> list[LogEntry]:
    elements = {s.element_id for s in table.segments}
    return [e for e in log if _belongs(e.target, table) or e.element_id in elements]


# ---------------------------------------------------------------------- tổng quan

def _overview(report: RunReport, result: RunResult) -> str:
    src = report.source
    rows = [
        ("Tài liệu", report.doc_id), ("Lần chạy", f"{report.run_id} · {report.created_at:%Y-%m-%d %H:%M:%S}"),
        ("Nguồn", src.pdf_name or src.raw_dir or "—"), ("sha256 PDF", src.pdf_sha256 or "— (không có PDF)"),
        ("Trang đã chọn", ", ".join(map(str, report.pages_selected))
         + (f" / {src.total_pages} trang" if src.total_pages else "")),
        ("Profile", f"{report.profile_name} · hash {report.profile_hash[:12]}"),
        ("Phiên bản tool", ", ".join(f"{k} {v}" for k, v in report.tool_versions.items()) or "—"),
        ("Thời gian", ", ".join(f"{k} {v:.2f}s" for k, v in report.timings_s.items()) or "—"),
    ]
    info = "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in rows)
    steps = "".join(
        f"<tr><td>{_e(s.label)}</td><td><span class='badge st-{s.status}'>{_e(STATUS_TEXT[s.status])}</span></td>"
        f"<td><code>{_e(s.module)}</code></td><td>{_e(s.backlog)}</td><td>{_e(s.note)}</td></tr>"
        for s in report.steps)
    by_code = "".join(f"<tr><td>{_e(c)}</td><td>{n}</td></tr>" for c, n in report.stats.review_by_code.items())
    by_step = ", ".join(f"{k}: {v}" for k, v in report.stats.blocking_by_step.items()) or "không có"
    index = "".join(
        f"<tr><td><a href='#{_anchor(t.logical_table_id)}'>{_e(t.logical_table_id)}</a></td>"
        f"<td>{_e(', '.join(str(s.pdf_page_index) for s in t.segments))}</td><td>{len(t.columns)}</td>"
        f"<td>{len(t.rows)}</td><td><code>{_e(report.table_content_hashes[t.logical_table_id][:12])}</code></td>"
        f"<td>{len(_table_review(result.tables.review, t))}</td>"
        f"<td>{'có thể bị cắt' if t.logical_table_id in report.page_range_boundary else ''}</td></tr>"
        for t in result.tables.tables)
    return (
        "<h2 id='overview'>Tổng quan</h2>"
        f"<table class='t'>{info}</table>"
        "<h3>Trạng thái các bước</h3><table class='t'><tr><th>Bước</th><th>Trạng thái</th><th>Module</th>"
        f"<th>Backlog</th><th>Ghi chú</th></tr>{steps}</table>"
        f"<h3>Review queue</h3><p>{report.stats.review_items} mục; blocking theo bước bị chặn: {_e(by_step)}</p>"
        f"<table class='t'><tr><th>code</th><th>số mục</th></tr>{by_code}</table>"
        "<h3>Bảng logic</h3><p class='muted'>ID là định danh của lần chạy này (đánh số theo thứ tự xuất hiện); "
        "so sánh giữa các lần chạy dùng content hash.</p>"
        "<table class='t'><tr><th>ID</th><th>Trang</th><th>Cột</th><th>Dòng</th><th>content hash</th>"
        f"<th>Review</th><th>Phạm vi trang</th></tr>{index}</table>"
    )


# ---------------------------------------------------------------------- theo trang

def _elements_by_id(result: RunResult) -> dict[str, NormalizedElement]:
    return {e.element_id: e for e in result.normalized or []}


def _page_svg(page: int, size: dict[str, float], items: Sequence[RawItem], tables: Sequence[LogicalTable],
              image: str | None, elements: dict[str, NormalizedElement]) -> str:
    w, h = size["width"], size["height"]
    parts = [f"<svg viewBox='0 0 {w:.1f} {h:.1f}' width='{w * 1.2:.0f}' xmlns='http://www.w3.org/2000/svg'>"]
    if image:
        parts.append(f"<image href='{_e(image)}' x='0' y='0' width='{w:.1f}' height='{h:.1f}'/>")
    for order, item in enumerate(i for i in items if i.page == page and i.bbox is not None):
        b, color = item.bbox, LABEL_COLORS.get(item.label, "#000")
        assert b is not None
        element = elements.get(item.element_id)
        flags = element.flags if element else []
        box = f"x='{b.x0:.1f}' y='{b.y0:.1f}' width='{b.x1 - b.x0:.1f}' height='{b.y1 - b.y0:.1f}' fill='none'"
        if element is not None and element.normalized_type == "figure_text":
            parts.append(f"<rect {box} stroke='#9aa0a6' stroke-width='0.4'><title>{_e(item.element_id)} · "
                         f"chữ trong hình: {_e(item.text[:60])}</title></rect>")
            continue
        name, dash = item.label, ""
        if "furniture_demoted" in flags:
            color, name, dash = "#d62728", f"heading ← {item.label}", " stroke-dasharray='4 2'"
        elif item.is_furniture:
            dash = " stroke-dasharray='2 2'"
        if element is not None and element.normalized_type in ("screenshot", "watermark_candidate"):
            name = f"{element.normalized_type} ← {item.label}"
        parts.append(f"<rect {box} stroke='{color}' stroke-width='1'{dash}><title>{_e(item.element_id)} · "
                     f"{_e(name)} · {_e(', '.join(flags))}</title></rect><text x='{b.x0 + 1:.1f}' y='{b.y0 + 6:.1f}' "
                     f"font-size='6' fill='{color}'>{order}:{_e(name)}</text>")
        if element is not None and element.image is not None:
            c = element.image.crop_bbox
            parts.append(f"<rect x='{c.x0:.1f}' y='{c.y0:.1f}' width='{c.x1 - c.x0:.1f}' height='{c.y1 - c.y0:.1f}' "
                         f"fill='none' stroke='#ff7f0e' stroke-width='0.8' stroke-dasharray='6 3'><title>crop T-14: "
                         f"{_e(', '.join(element.image.crop_sources))}</title></rect>")
    for table in tables:
        for segment in table.segments:
            if segment.pdf_page_index != page:
                continue
            s = segment.bbox
            for column in table.columns[1:]:
                parts.append(f"<line x1='{column.x_min:.1f}' y1='{s.y0:.1f}' x2='{column.x_min:.1f}' y2='{s.y1:.1f}' "
                             "stroke='#2ca02c' stroke-width='0.8' stroke-dasharray='3 2'/>")
            parts.append(f"<rect x='{s.x0:.1f}' y='{s.y0:.1f}' width='{s.x1 - s.x0:.1f}' height='{s.y1 - s.y0:.1f}' "
                         "fill='none' stroke='#2ca02c' stroke-width='2'/>"
                         f"<a href='#{_anchor(table.logical_table_id)}'><text x='{s.x1 - 2:.1f}' y='{s.y0 - 2:.1f}' "
                         f"font-size='8' text-anchor='end' fill='#2ca02c'>{_e(table.logical_table_id)}</text></a>")
    parts.append("</svg>")
    return "".join(parts)


def _v01(result: RunResult) -> dict[int, ValidationResult]:
    return {int(v.target.rsplit(":p", 1)[1]): v for v in result.validation if v.check_id == "V-01"}


def _s0_page(result: RunResult, page: int):
    if result.s0 is None:
        return None
    return next((p for p in result.s0.pages if p.page == page), None)


def _s0(result: RunResult) -> str:
    if result.s0 is None:
        return ("<h2 id='s0'>S0 hồ sơ trang</h2><p class='muted'>Không có số đo S0 (chạy từ Docling JSON không "
                "kèm PDF và raw không có profile.json).</p>")
    pages = result.s0.pages
    missing = [p.page for p in pages if p.text_layer != "ok"]
    out = ["<h2 id='s0'>S0 hồ sơ trang</h2>",
           f"<p class='muted'>Chế độ OCR: <code>{_e(result.s0.ocr_mode)}</code> · /PageLabels: "
           f"{'có' if result.s0.page_labels_present else 'không'} · ngưỡng: &lt; {result.profile.thresholds.ocr_min_chars} "
           f"ký tự hoặc &gt; {result.profile.thresholds.text_bad_char_max:.0%} ký tự lỗi → cần OCR (giá trị tạm, D-12).</p>"]
    if missing:
        share = len(missing) / len(pages)
        out.append(f"<p class='warn'><b>{len(missing)}/{len(pages)} trang không có hoặc hỏng text layer</b>"
                   f"{' (cả tài liệu được vẽ bằng hình)' if share == 1 else ''}. Chữ của các trang này chỉ có từ OCR, "
                   "không có nguồn độc lập để V-01 đối chiếu; mỗi trang có mục <code>ocr_required</code> chặn chunk "
                   "cho tới khi người duyệt xác nhận.</p>")
    rows = "".join(
        f"<tr class='{'' if p.text_layer == 'ok' else 'blocking'}'><td><a href='#p{p.page}'>{p.page}</a></td>"
        f"<td>{p.text_chars}</td><td>{p.bad_char_ratio:.1%}</td><td>{p.bitmap_area_ratio:.0%}</td>"
        f"<td>{p.vector_path_count}</td><td>{p.rotation}</td><td>{_e(p.page_label or '—')}</td>"
        f"<td>{_e(p.text_layer)}</td><td>{'có' if p.ocr_applied else ('cần, chưa chạy' if p.ocr else 'không')}</td></tr>"
        for p in pages)
    out.append("<table class='t'><tr><th>Trang</th><th>Ký tự text layer</th><th>Ký tự lỗi</th><th>Bitmap</th>"
               "<th>Path vector</th><th>Xoay</th><th>Page label</th><th>Text layer</th><th>OCR</th></tr>"
               f"{rows}</table>")
    return "".join(out)


def _v01_badge(result: RunResult, page: int) -> str:
    s0_page = _s0_page(result, page)
    if s0_page is not None and s0_page.ocr_applied:
        return "<span class='badge cand'>OCR · V-01 không có nguồn độc lập</span>"
    check = _v01(result).get(page)
    if page not in result.words:
        return "<span class='badge st-not_implemented'>V-01 không chạy: thiếu words.json</span>"
    if check is None or check.passed is None:
        return "<span class='badge st-not_implemented'>V-01 không chạy: trang không có text layer</span>"
    css = "st-implemented" if check.passed else "blocking"
    return f"<span class='badge {css}'>V-01 {'đạt' if check.passed else 'không đạt'} · phủ {check.score:.1%}</span>"


def _validation(result: RunResult) -> str:
    checks = _v01(result)
    rows = []
    for page in result.pages:
        check = checks.get(page)
        if page not in result.words:
            rows.append(f"<tr><td><a href='#p{page}'>{page}</a></td><td colspan='5'>không chạy: thiếu words.json "
                        "(chạy kèm --pdf hoặc raw có p{n}.words.json)</td></tr>")
            continue
        if check is None or check.passed is None:
            reason = ("trang OCR: không có text layer độc lập để đối chiếu" if check is not None
                      and check.detail.get("reason", "").startswith("OCR") else
                      "không có token text layer ngoài furniture (xem S0)")
            rows.append(f"<tr><td><a href='#p{page}'>{page}</a></td><td colspan='5'>không chạy: {reason}</td></tr>")
            continue
        d = check.detail
        rows.append(
            f"<tr class='{'' if check.passed else 'blocking'}'><td><a href='#p{page}'>{page}</a></td>"
            f"<td>{check.score:.1%} (min {check.threshold:.0%})</td>"
            f"<td>{float(d['duplicate_ratio']):.1%} (max {float(d['duplicate_max']):.0%})</td>"
            f"<td>{'đạt' if check.passed else 'không đạt'}</td><td>{d['page_tokens']} / {d['kept_tokens']}</td>"
            f"<td>{_e(', '.join(d['missing_sample']))}{' …' if int(d['missing_count']) > len(d['missing_sample']) else ''}"
            "</td></tr>")
    return ("<h2 id='validation'>V-01 độ phủ text</h2><p class='muted'>So từ của text layer PDF (bỏ vùng "
            "header/footer) với nội dung pipeline giữ lại. Ngưỡng là giá trị tạm (D-12 chưa chốt). Không đạt → "
            "<code>text_coverage_gap</code> chặn chunk của trang.</p><table class='t'><tr><th>Trang</th><th>Độ phủ"
            "</th><th>Trùng</th><th>Kết quả</th><th>Token trang / giữ lại</th><th>Token thiếu (mẫu)</th></tr>"
            f"{''.join(rows)}</table>")


def _elements(result: RunResult) -> str:
    out = ["<h2 id='elements'>Mục lục và phần tử chưa hỗ trợ</h2>"]
    toc = result.elements.toc
    if toc:
        out.append("<h3>Mục lục (T-16)</h3><p class='muted'>Nhãn Docling <code>document_index</code>: giữ nguyên cell, "
                   "không vào bảng logic, không chunk.</p>")
        for item in toc:
            out.append(f"<p>Trang <a href='#p{item.page}'>{item.page}</a> · <code>{_e(item.element_id)}</code> · "
                       f"{len(item.cells)} cell</p><details><summary>Xem cell</summary>"
                       f"{_raw_grid(result, item.element_id)}</details>")
    else:
        out.append("<p class='muted'>Không có mục lục trong các trang đã chạy.</p>")
    unsupported = result.elements.unsupported
    if unsupported:
        rows = "".join(f"<tr class='blocking'><td><a href='#p{i.page}'>{i.page}</a></td><td><code>{_e(i.element_id)}"
                       f"</code></td><td>{_e(i.label)}</td><td>{_e(i.text[:120] or f'{len(i.cells)} cell')}</td></tr>"
                       for i in unsupported)
        out.append("<h3>Phần tử chưa hỗ trợ</h3><p class='muted'>Nhãn chưa có bộ chuẩn hóa; có mục review "
                   "<code>unsupported_element</code> chặn chunk của phần tử, không bị bỏ im lặng.</p>"
                   f"<table class='t'><tr><th>Trang</th><th>Phần tử</th><th>Nhãn</th><th>Nội dung</th></tr>{rows}</table>")
    else:
        out.append("<p class='muted'>Không có phần tử nhãn chưa hỗ trợ.</p>")
    return "".join(out)


_FLAG_TEXT = {
    "furniture_repeated": "furniture: lặp nhiều trang", "furniture_composed": "furniture: ghép từ chuỗi lặp",
    "furniture_pattern": "furniture: khớp furniture_patterns", "furniture_promoted": "Docling gắn body",
    "furniture_unconfirmed": "furniture theo Docling, không lặp — chờ duyệt",
    "furniture_demoted": "heading trả về từ header/footer — chờ duyệt",
    "section_parent_missing": "thiếu section cha", "heading_spacing": "số dính chữ (OCR)",
    "figure_text_attached": "nhãn sát hình, gắn vào hình (T-18)", "caption_relinked": "caption gắn lại (T-11)",
    "watermark_candidate": "ứng viên watermark (T-10), không xóa",
}
_SOURCE_TEXT = {"docling": "bbox Docling", "bitmap": "bitmap nhúng", "vector": "nét vector", "label": "nhãn của hình"}


def _figures(result: RunResult) -> str:
    elements = result.normalized or []
    by_id = {e.element_id: e for e in elements}
    images = [e for e in elements if e.image is not None]
    out = [f"<h2 id='figures'>Hình (T-09, T-10, T-11, T-14, T-18) · {len(images)}</h2>",
           "<p class='muted'>Ảnh crop là nội dung có thẩm quyền của hình. Chữ OCR trong hình và nhãn sát hình (T-18) "
           "chỉ là từ khóa để tìm hình: không vào nội dung chunk, không thành fact (kích thước đọc từ bản vẽ không "
           "biết đo cạnh nào). Tất cả <b>chưa duyệt</b>; duyệt unit hình (BL-18…BL-21) chưa có.</p>"]
    if not images:
        out.append("<p class='muted'>Không có hình.</p>")
        return "".join(out)
    if not any(e.image.original_path for e in images if e.image):
        out.append("<p class='warn'>Không có ảnh crop (chạy không kèm PDF); chỉ có vùng crop.</p>")
    children: dict[str, list[NormalizedElement]] = {}
    for e in elements:
        if e.normalized_type == "figure_text" and e.parent_element_id:
            children.setdefault(e.parent_element_id, []).append(e)
    cards = []
    for e in images:
        assert e.image is not None
        caption = by_id.get(e.caption_element_id or "")
        link = ""
        if e.caption_link is not None:
            link = " (T-11 gắn lại)" if e.caption_link.source == "rule" else " (Docling)"
        inner = children.get(e.element_id, [])
        attached = [c for c in inner if "figure_text_attached" in c.flags]
        img = (f"<img src='../{_e(e.image.preview_path)}' alt='{_e(e.element_id)}' loading='lazy'>"
               if e.image.preview_path else "")
        sources = ", ".join(_SOURCE_TEXT.get(s, s) for s in e.image.crop_sources)
        c = e.image.crop_bbox
        cards.append(
            f"<div class='fig'>{img}<div><b>{_e(e.normalized_type)}</b> · <a href='#p{e.pdf_page_index}'>trang "
            f"{e.pdf_page_index}</a> · <span class='muted'>{_e(e.element_id)}</span></div>"
            f"<div>{_e(caption.text if caption else 'không có caption')}<span class='muted'>{link}</span></div>"
            f"<div class='path'>{_e(' › '.join(e.section_path))}</div>"
            f"<div class='muted'>crop ({c.x0:.0f},{c.y0:.0f})–({c.x1:.0f},{c.y1:.0f}): {_e(sources)}</div>"
            f"<div class='muted'>{len(inner)} chữ OCR trong hình"
            + (f"; nhãn sát hình (T-18): {_e(', '.join(a.text or '' for a in attached))}" if attached else "")
            + "</div></div>")
    out.append(f"<div class='figs'>{''.join(cards)}</div>")
    issues = [r for r in result.tables.review if r.code in ("caption_ambiguous", "watermark_conflict", "empty_table")]
    if issues:
        out.append(f"<h3>Cần xem</h3><table class='t'>{_REVIEW_HEAD}{_review_rows(issues)}</table>")
    return "".join(out)


def _furniture(result: RunResult) -> str:
    th = result.profile.thresholds
    out = ["<h2 id='furniture'>Header/footer (T-17) và trang in (T-06)</h2>",
           f"<p class='muted'>Tự động theo luật chung: chuỗi lặp ≥ {th.furniture_min_pages} trang ở dải trên/dưới "
           f"{th.furniture_band:.0%} chiều cao trang (chữ số coi như nhau), dòng ghép từ các chuỗi đó, hoặc "
           "<code>furniture_patterns</code> của profile. Người duyệt chỉ xem ngoại lệ bên dưới. Không xóa gì: "
           "phần tử furniture vẫn có trong <code>elements.jsonl</code>.</p>"]
    keys = result.furniture_keys or []
    if keys:
        rows = "".join(f"<tr><td>{_e(k.band)}</td><td>{_e(k.example)}</td><td><code>{_e(k.key)}</code></td>"
                       f"<td>{len(k.pages)}: {_e(', '.join(map(str, k.pages)))}</td></tr>" for k in keys)
        out.append("<h3>Chuỗi lặp được xác nhận</h3><table class='t'><tr><th>Dải</th><th>Ví dụ</th><th>Khóa</th>"
                   f"<th>Trang</th></tr>{rows}</table>")
    else:
        out.append(f"<p class='muted'>Không có chuỗi lặp (cần ≥ {th.furniture_min_pages} trang được chọn).</p>")
    exceptions = [r for r in result.tables.review if r.code in ("furniture_reclassified", "furniture_unconfirmed")]
    if exceptions:
        out.append("<h3>Ngoại lệ cần xem</h3><p class='muted'><code>furniture_reclassified</code>: Docling gắn "
                   "header/footer nhưng là heading đánh số xuất hiện một lần → trả về nội dung. "
                   "<code>furniture_unconfirmed</code>: không lặp, không phải heading → vẫn bỏ khỏi nội dung, chờ "
                   f"xác nhận.</p><table class='t'>{_REVIEW_HEAD}{_review_rows(exceptions)}</table>")
    printed = result.printed or {}
    if printed:
        cells = "".join(f"<tr><td><a href='#p{p}'>{p}</a></td><td>{_e(v.value or '—')}</td>"
                        f"<td>{_e(v.source or 'không có nguồn')}</td></tr>" for p, v in sorted(printed.items()))
        out.append("<h3>Trang in</h3><p class='muted'>Nguồn: /PageLabels, hoặc số trong footer tăng đều theo trang "
                   f"PDF trên ≥ {th.furniture_min_pages} trang. Không suy từ offset: trang không đọc được số để trống."
                   f"</p><table class='t'><tr><th>Trang PDF</th><th>Trang in</th><th>Nguồn</th></tr>{cells}</table>")
    return "".join(out)


def _page_elements(result: RunResult, page: int) -> str:
    elements = [e for e in result.normalized or [] if e.pdf_page_index == page]
    if not elements:
        return ""
    children: dict[str, list[NormalizedElement]] = {}
    for e in elements:
        if e.normalized_type == "figure_text" and e.parent_element_id:
            children.setdefault(e.parent_element_id, []).append(e)
    rows = []
    for e in elements:
        if e.normalized_type == "figure_text":
            continue
        text = _e((e.text or "")[:140])
        inner = children.get(e.element_id, [])
        if inner:
            text += (f"<details><summary>{len(inner)} chữ OCR trong hình · chưa duyệt · không vào nội dung chunk"
                     "</summary>" + "<br>".join(_e(c.text or "") for c in inner) + "</details>")
        note = ", ".join(_FLAG_TEXT.get(f, f) for f in e.flags)
        rows.append(f"<tr class='{'muted' if e.content_layer == 'furniture' else ''}'><td>{e.reading_order}</td>"
                    f"<td>{_e(e.normalized_type)}</td><td>{text}</td><td class='path'>{_e(' › '.join(e.section_path))}"
                    f"</td><td>{_e(note)}</td></tr>")
    return (f"<details><summary>Phần tử chuẩn hóa ({len(elements)})</summary><table class='t'><tr><th>#</th>"
            f"<th>loại</th><th>nội dung</th><th>section path (T-07)</th><th>cờ</th></tr>{''.join(rows)}</table>"
            "</details>")


def _pages(result: RunResult, images: dict[int, str]) -> str:
    legend = "".join(f"<span style='color:{c}'>■ {_e(label)}</span>" for label, c in LABEL_COLORS.items())
    out = ["<h2 id='pages'>Theo trang</h2>",
           f"<p class='legend muted'>{legend}<span style='color:#2ca02c'>┆ biên cột T-01</span>"
           "<span>┄ furniture</span><span style='color:#d62728'>┄ heading trả về từ header/footer (T-17)</span>"
           "<span style='color:#9aa0a6'>□ chữ trong hình</span>"
           "<span style='color:#ff7f0e'>┄ vùng crop hình (T-14)</span></p>"]
    if not images:
        out.append("<p class='warn'>Không có ảnh trang (chạy từ Docling JSON không kèm PDF); chỉ vẽ khung phần tử.</p>")
    elements = _elements_by_id(result)
    for doc in result.docs:
        page = doc_page(doc)
        size = doc["pages"][str(page)]["size"]
        printed = (result.printed or {}).get(page)
        label = f" · trang in {_e(printed.value)}" if printed and printed.value else ""
        out.append(f"<div class='page'><h3 id='p{page}'>Trang {page}{label} {_v01_badge(result, page)}</h3>"
                   f"{_page_svg(page, size, result.items, result.tables.tables, images.get(page), elements)}"
                   f"{_page_elements(result, page)}</div>")
    return "".join(out)


# ---------------------------------------------------------------------- theo bảng

def _raw_grid(result: RunResult, element_id: str) -> str:
    item = next(i for i in result.items if i.element_id == element_id)
    rows: dict[int, dict[int, tuple[str, bool]]] = {}
    for cell in item.cells:
        rows.setdefault(cell.row, {})[cell.col] = (cell.text, cell.header)
    body = []
    for r in sorted(rows):
        tds = []
        for c in range(item.num_cols):
            text, header = rows[r].get(c, ("", False))
            tds.append(f"<td class='{'hdr' if header else ''}'>{_e(text)}</td>")
        body.append(f"<tr><td class='muted'>{r}</td>{''.join(tds)}</tr>")
    head = "".join(f"<th>{c}</th>" for c in range(item.num_cols))
    return (f"<div><div class='muted'>Docling thô · {item.self_ref} · cột theo chỉ số Docling</div>"
            f"<table class='t'><tr><th>dòng</th>{head}</tr>{''.join(body)}</table></div>")


def _candidates(row: Row, review: Sequence[ReviewItem], target: str) -> str:
    if not row.applicability_candidates:
        return ""
    items = [r for r in review if r.target == target and r.code.startswith("applicability")]
    refs = ", ".join(r.item_id for r in items)
    badges = []
    for cand in row.applicability_candidates:
        scope = ", ".join(cand.models + cand.interfaces) or "không khớp registry"
        badges.append(f"<span class='badge cand' title='{_e(cand.note)}'>ứng viên T-13 · {_e(cand.status)} · "
                      f"{_e(scope)} · “{_e(cand.condition_text)}” · chưa phải fact · chờ duyệt</span>")
    return "".join(badges) + (f" <span class='muted'>({_e(refs)})</span>" if refs else "")


def _logical_grid(table: LogicalTable, segment_index: int, review: Sequence[ReviewItem]) -> str:
    demoted = {f.split(":", 1)[1] for f in table.flags if f.startswith("header_flag_demoted:")}
    head = "".join(f"<th>{_e(c.header_text or '—')}</th>" for c in table.columns)
    body = []
    for row in (r for r in table.rows if r.segment == segment_index):
        target = f"{table.logical_table_id}:{row.row_id}"
        tds = []
        for cell in row.cells:
            classes, title = [], []
            if row.is_header:
                classes.append("rep" if row.repeated_header else "hdr")
            if cell.assigned_by == "empty_fill":
                classes.append("empty")
                title.append("T-02: ô trống ghi tường minh")
            elif cell.docling_col != cell.col:
                classes.append("moved")
                title.append(f"T-01: cột Docling {cell.docling_col} → cột {cell.col}")
            if row.row_id in demoted:
                classes.append("demoted")
                title.append("T-05: cờ header Docling bị hạ thành dữ liệu")
            if cell.merged_cell_refs:
                title.append("T-15: gộp " + ", ".join(cell.merged_cell_refs))
            tds.append(f"<td class='{' '.join(classes)}' title='{_e('; '.join(title))}'>"
                       f"{_e(cell.text) if cell.text else '∅'}</td>")
        ref = row.param_ref
        param = f"{ref.kind}: {ref.codes[0]}…{ref.codes[-1]} ({len(ref.codes)})" if ref and len(ref.codes) > 3 else (
            f"{ref.kind}: {', '.join(map(str, ref.codes))}" if ref else "")
        tag = " · lặp header" if row.repeated_header else " · header" if row.is_header else ""
        merged = f" · gộp {', '.join(row.merged_row_ids)}" if row.merged_row_ids else ""
        body.append(f"<tr class='{'merged' if row.merged_row_ids else ''}'><td class='muted'>{_e(row.row_id)}{tag}"
                    f"{merged}</td>{''.join(tds)}<td class='muted'>{_e(param)}</td>"
                    f"<td>{_candidates(row, review, target)}</td></tr>")
    return (f"<div><div class='muted'>Bảng logic · cột gán theo bbox</div><table class='t'><tr><th>row</th>{head}"
            f"<th>param_ref (T-12)</th><th>Ứng viên applicability (T-13)</th></tr>{''.join(body)}</table></div>")


def _review_rows(items: Sequence[ReviewItem]) -> str:
    return "".join(
        f"<tr class='{'blocking' if r.blocking else ''}'><td>{_e(r.item_id)}</td><td>{_e(r.code)}</td>"
        f"<td>{'blocking → ' + _e(r.blocks) if r.blocking else 'không chặn'}</td><td>{_e(r.target or r.element_id)}</td>"
        f"<td>{_e(r.detail)}</td><td>{_e(r.suggested_action or '')}</td></tr>" for r in items)


def _log_rows(entries: Sequence[LogEntry]) -> str:
    return "".join(
        f"<tr><td>{_e(e.rule_id)}</td><td>{_e(e.target or e.element_id)}</td><td>{_e(e.before)}</td>"
        f"<td>{_e(e.after)}</td><td>{_e(e.reason)}</td></tr>" for e in entries)


_REVIEW_HEAD = "<tr><th>id</th><th>code</th><th>chặn</th><th>đích</th><th>chi tiết</th><th>gợi ý</th></tr>"
_LOG_HEAD = "<tr><th>luật</th><th>đích</th><th>trước</th><th>sau</th><th>lý do</th></tr>"


def _tables(result: RunResult, report: RunReport) -> str:
    run = result.tables
    out = ["<h2 id='tables'>Theo bảng logic</h2>",
           "<p class='legend muted'><span class='badge' style='background:#e8f0fe'>header</span>"
           "<span class='badge' style='background:#fff3c4'>T-01 cột được sửa</span>"
           "<span class='badge' style='background:#f1f3f4'>T-02 ô trống</span>"
           "<span class='badge' style='outline:2px solid #e37400'>T-05 header bị hạ</span>"
           "<span class='badge' style='box-shadow:inset 3px 0 0 #188038'>T-15 dòng gộp</span>"
           "<span class='badge cand'>ứng viên T-13 (chưa phải fact)</span></p>"]
    for table in run.tables:
        tid = table.logical_table_id
        out.append(f"<h3 id='{_anchor(tid)}'>{_e(tid)} <span class='muted'>· content hash "
                   f"{_e(report.table_content_hashes[tid][:12])}</span></h3>")
        for reason in report.page_range_boundary.get(tid, []):
            out.append(f"<p class='warn'>Có thể bị cắt bởi phạm vi trang: {_e(reason)}. Chỉ là thông tin hiển thị; "
                       "chạy kèm trang liền kề để có bảng đầy đủ.</p>")
        cols = "".join(f"<tr><td>{c.index}</td><td>{_e(c.header_text or '—')}</td><td>{c.x_min:.1f}–{c.x_max:.1f}</td>"
                       f"<td>{_e(c.header_source)}</td></tr>" for c in table.columns)
        out.append(f"<table class='t'><tr><th>cột</th><th>header</th><th>x (pt)</th><th>nguồn header</th></tr>{cols}"
                   "</table>")
        out.append(f"<p class='muted'>Cờ: {_e(', '.join(table.flags) or 'không có')}</p>")
        for index, segment in enumerate(table.segments):
            out.append(f"<p><b>Segment {index}</b> · trang <a href='#p{segment.pdf_page_index}'>"
                       f"{segment.pdf_page_index}</a> · {segment.num_cols_docling} cột Docling · "
                       f"<code>{_e(segment.element_id)}</code></p>"
                       f"<div class='pair'>{_raw_grid(result, segment.element_id)}"
                       f"{_logical_grid(table, index, run.review)}</div>")
        if table.unassigned_cells:
            cells = "".join(f"<tr><td>{_e(c.row_id)}</td><td>{_e(c.text)}</td><td>{_e(c.reason)}</td></tr>"
                            for c in table.unassigned_cells)
            out.append(f"<p><b>Cell không gán được cột</b></p><table class='t'>{cells}</table>")
        out.append("<p class='muted'>Fact (parameter, applicability của fact): chưa triển khai (BL-17).</p>")
        review = _table_review(run.review, table)
        if review:
            out.append(f"<details open><summary>Review của bảng ({len(review)})</summary>"
                       f"<table class='t'>{_REVIEW_HEAD}{_review_rows(review)}</table></details>")
        log = _table_log(run.log, table)
        if log:
            out.append(f"<details><summary>Log biến đổi của bảng ({len(log)})</summary>"
                       f"<table class='t'>{_LOG_HEAD}{_log_rows(log)}</table></details>")
    return "".join(out)


def render_report(result: RunResult, report: RunReport, page_images: dict[int, str]) -> str:
    run = result.tables
    body = (
        f"<main><h1>Báo cáo chạy doc_ingest · {_e(report.doc_id)}</h1>"
        "<nav><a href='#overview'>Tổng quan</a><a href='#s0'>S0</a><a href='#validation'>V-01</a><a href='#elements'>Mục lục, nhãn lạ</a>"
        "<a href='#furniture'>Header/footer, trang in</a><a href='#figures'>Hình</a>"
        "<a href='#pages'>Theo trang</a><a href='#tables'>Theo bảng</a>"
        "<a href='#review'>Review queue</a><a href='#log'>Log</a></nav>"
        f"{_overview(report, result)}{_s0(result)}{_validation(result)}{_elements(result)}{_furniture(result)}"
        f"{_figures(result)}"
        f"{_pages(result, page_images)}"
        f"{_tables(result, report)}"
        f"<h2 id='review'>Review queue ({len(run.review)})</h2>"
        f"<table class='t'>{_REVIEW_HEAD}{_review_rows(run.review)}</table>"
        f"<h2 id='log'>Normalization log ({len(run.log)})</h2>"
        f"<table class='t'>{_LOG_HEAD}{_log_rows(run.log)}</table></main>"
    )
    return (f"<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>doc_ingest {_e(report.doc_id)} {_e(report.run_id)}</title><style>{_STYLE}</style></head>"
            f"<body>{body}</body></html>")

