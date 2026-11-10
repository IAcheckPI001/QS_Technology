"""Trang HTML kết quả chấm điểm (`report/eval.html`)."""

from __future__ import annotations

import html

from app.modules.doc_ingest.eval.labels import EvalReport, GroupScore
from app.modules.doc_ingest.report.html_report import _STYLE

_GROUP_TEXT = {"text_layer": "Trang có text layer (áp cổng)", "ocr": "Trang OCR (chỉ báo cáo)"}


def _e(value: object) -> str:
    return html.escape("—" if value is None else str(value))


def _group(name: str, g: GroupScore) -> str:
    rows = [
        ("Trang", ", ".join(map(str, g.pages)) or "—"),
        ("T-12 mã: TP / FP / FN", f"{g.t12.tp} / {g.t12.fp} / {g.t12.fn}"),
        ("T-12 precision / recall", f"{_e(g.t12.precision)} / {_e(g.t12.recall)}"),
        ("T-12 vai trò đúng", _e(g.t12_role_accuracy)),
        ("T-08 cha đúng / sai / thiếu", f"{g.t08_correct} / {g.t08_wrong} / {g.t08_missing}"),
        ("T-13 TP / FP / FN", f"{g.t13.tp} / {g.t13.fp} / {g.t13.fn}"),
        ("Nội dung thân giữ lại", f"{g.content_found} / {g.content_total}"),
    ]
    body = "".join(f"<tr><th>{_e(k)}</th><td>{v}</td></tr>" for k, v in rows)
    return f"<h2>{_e(_GROUP_TEXT.get(name, name))}</h2><table class='t'>{body}</table>"


def render_eval(report: EvalReport) -> str:
    verdict = {True: "ĐẠT", False: "KHÔNG ĐẠT", None: "không đủ dữ liệu"}[report.gate_passed]
    warn = ("<p class='warn'>Nhãn chưa được team xác nhận (<code>verified: false</code>): kết quả là <b>tạm</b>.</p>"
            if report.provisional else "")
    gate = "".join(
        f"<tr><td>{_e(c.name)}</td><td>{_e(c.value)}</td><td>{_e(c.threshold)}</td>"
        f"<td>{ {True: 'đạt', False: 'không đạt', None: '—'}[c.passed] }</td></tr>" for c in report.gate)
    details = "".join(f"<h3>{_e(k)} ({len(v)})</h3><ul>" + "".join(f"<li>{_e(x)}</li>" for x in v) + "</ul>"
                      for k, v in report.details.items())
    body = (f"<main><h1>Chấm điểm theo nhãn mẫu · {_e(report.doc_id)} · {_e(report.run_id)}</h1>{warn}"
            f"<h2>Cổng đánh giá: {verdict}</h2><p class='muted'>Kiểm mã, list, nội dung trên trang có text layer; trang OCR chỉ báo cáo. Tài liệu có hơn 50% trang OCR không đạt cổng.</p><table class='t'><tr><th>kiểm</th><th>giá trị</th>"
            f"<th>ngưỡng</th><th>kết quả</th></tr>{gate}</table>"
            + "".join(_group(k, g) for k, g in report.groups.items())
            + (f"<h2>Chi tiết sai</h2>{details}" if details else "") + "</main>")
    return (f"<!doctype html><html lang='vi'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width, initial-scale=1'><title>eval {_e(report.doc_id)}</title>"
            f"<style>{_STYLE}</style></head><body>{body}</body></html>")
