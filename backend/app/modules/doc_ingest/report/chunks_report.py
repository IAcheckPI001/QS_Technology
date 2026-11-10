"""`report/chunks.html`: trang duyệt tay chunk nháp (Bước 2b, contract C2 §10).

Một file tự chứa; script inline duy nhất là bộ lọc thẻ theo loại/vai trò/cờ/trang. Nhận xét duyệt ghi vào
`build/chunk_review.json` (`verdict` ok/fix + `note`), rồi chạy lại `build` để tổng hợp.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from app.modules.doc_ingest.schemas.chunk import ChunkQuality, DraftChunk

if TYPE_CHECKING:
    from app.modules.doc_ingest.build.builder import BuildResult

_STYLE = """
:root{--fg:#1d1d1f;--muted:#5f6368;--line:#d0d4d9;--bg:#fff;--soft:#f5f6f8}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;color:var(--fg);background:var(--bg)}
main{max-width:1400px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:8px 0}h2{font-size:18px;margin:28px 0 8px;border-bottom:2px solid var(--line)}
nav a{margin-right:12px}
table.t{border-collapse:collapse;margin:6px 0;font-size:13px}
table.t th,table.t td{border:1px solid var(--line);padding:3px 6px;vertical-align:top;text-align:left}
table.t th{background:var(--soft)}
.muted{color:var(--muted);font-size:12px}
.badge{display:inline-block;padding:0 6px;border-radius:9px;font-size:12px;border:1px solid var(--line);margin:1px}
.ok{background:#e6f4ea}.bad{background:#fce8e6}.na{background:#f1f3f4;color:var(--muted)}
.warn{background:#fef7e0;border-left:4px solid #f9ab00;padding:4px 8px;margin:6px 0}
.card{border:1px solid var(--line);border-radius:6px;padding:8px 10px;margin:8px 0;min-width:0}
.card.parent{background:var(--soft)}.card.child{margin-left:28px}
.card pre{white-space:pre-wrap;word-break:break-word;background:#fff;border:1px solid var(--line);padding:6px;
  font:12.5px/1.4 ui-monospace,Consolas,monospace;margin:6px 0;max-height:420px;overflow:auto}
.thumbs{display:flex;gap:8px;flex-wrap:wrap}.thumbs img{max-height:160px;max-width:260px;border:1px solid var(--line)}
.filters select,.filters input{margin-right:8px}
"""

_SCRIPT = """
function f(){const t=document.getElementById('ft').value,r=document.getElementById('fr').value,
g=document.getElementById('fg').value,p=parseInt(document.getElementById('fp').value||'0');let n=0;
document.querySelectorAll('.card').forEach(c=>{const ok=(!t||c.dataset.type===t)&&(!r||c.dataset.role===r)
&&(!g||(' '+c.dataset.flags+' ').includes(' '+g+' '))&&(!p||(+c.dataset.ps<=p&&p<=+c.dataset.pe));
c.style.display=ok?'':'none';if(ok)n++;});document.getElementById('fn').textContent=n+' chunk';}
"""

ROLE_TEXT = {"parent": "cha", "child": "con", "standalone": "độc lập"}


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _status(passed: bool | None) -> str:
    cls, text = {True: ("ok", "đạt"), False: ("bad", "không đạt"), None: ("na", "chưa có dữ liệu")}[passed]
    return f'<span class="badge {cls}">{text}</span>'


def _gate(q: ChunkQuality) -> str:
    rows = "".join(f"<tr><td>{_e(i.name)}</td><td>{_e(i.value)}</td><td>{_e(i.threshold)}</td>"
                   f"<td>{_status(i.passed)}</td></tr>" for i in q.gate)
    tag = " (tạm: nhãn chưa xác nhận hoặc chưa có chunk được duyệt)" if q.provisional else ""
    return (f"<h2 id='gate'>Cổng 2b → Bước 3: {_status(q.gate_passed)}{_e(tag)}</h2>"
            f"<table class='t'><tr><th>Điều kiện</th><th>Giá trị</th><th>Ngưỡng</th><th>Kết quả</th></tr>{rows}</table>")


def _overview(q: ChunkQuality) -> str:
    cells = [("Tổng chunk", q.chunks), ("Theo vai trò", ", ".join(f"{ROLE_TEXT.get(k, k)} {v}" for k, v in q.by_role.items())),
             ("Theo loại", ", ".join(f"{k} {v}" for k, v in q.by_type.items())),
             ("Độ dài content chunk lá (ký tự)", ", ".join(f"{k} {v}" for k, v in q.content_chars.items())),
             ("Đếm token", "tiktoken cl100k" if q.token_count_method == "tiktoken"
              else "không có tiktoken ở venv này (token_count = null)"),
             ("Cờ", ", ".join(f"{k} {v}" for k, v in q.flags.items()) or "—"),
             ("Chunk lá có review chặn (không được xuất bản)",
              ", ".join(f"{k} {v}" for k, v in q.blocked_chunks.items()) or "không"),
             ("Lỗi ràng buộc bảng doc_chunks (adapter v1)", len(q.export_errors))]
    return "<table class='t'>" + "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in cells) + "</table>"


def _checks(q: ChunkQuality) -> str:
    rows = []
    for c in q.checks:
        fails = "".join(f"<li>{_e(x)}</li>" for x in c.failures)
        detail = f"<details><summary>{len(c.failures)} lỗi</summary><ul>{fails}</ul></details>" if c.failures else ""
        rows.append(f"<tr><td>{_e(c.check_id)}</td><td>{_e(c.title)}</td><td>{c.checked}</td>"
                    f"<td>{_status(c.passed)}</td><td>{detail}<span class='muted'>{_e(c.note)}</span></td></tr>")
    return ("<h2 id='checks'>Kiểm cấu trúc (CQ)</h2><table class='t'><tr><th>ID</th><th>Khẳng định</th>"
            f"<th>Đã kiểm</th><th>Kết quả</th><th>Chi tiết</th></tr>{''.join(rows)}</table>")


def _coverage(q: ChunkQuality, texts: dict[str, str]) -> str:
    cov = q.coverage
    if cov is None:
        return ""
    excluded = ", ".join(f"{k} {v}" for k, v in cov.excluded.items())
    missing = "".join(f"<li>{_e(e)}: {_e(texts.get(e, '')[:120])}</li>" for e in cov.missing[:100])
    dup = "".join(f"<li>{_e(e)}: {_e(texts.get(e, '')[:120])}</li>" for e in cov.duplicated[:100])
    return (f"<h2 id='coverage'>Độ phủ nội dung</h2><p>{cov.covered}/{cov.required} phần tử cần chunk nằm trong chunk lá; "
            f"ký tự giữ lại {cov.chars_kept}/{cov.chars_total} ({_e(cov.char_ratio)}).</p>"
            f"<p class='muted'>Không cần chunk: {_e(excluded)}. Bảng kiểm theo dòng ở CQ-02.</p>"
            + (f"<div class='warn'>Bỏ sót {len(cov.missing)}:<ul>{missing}</ul></div>" if cov.missing else "")
            + (f"<div class='warn'>Lặp {len(cov.duplicated)}:<ul>{dup}</ul></div>" if cov.duplicated else ""))


def _boundaries(q: ChunkQuality) -> str:
    b = q.boundaries
    if b is None:
        return "<h2 id='bound'>Ranh giới theo nhãn mẫu</h2><p class='muted'>Không có nhãn `expected_chunks`.</p>"
    rows = "".join(
        f"<tr><td>{d.page}</td><td>{_e(d.chunk_type)}</td><td>{_e(d.start[:50])} … {_e(d.end[-40:])}</td>"
        f"<td>{_e(d.matched_key or '—')}</td><td>{_e(d.matched_type or '')}</td></tr>" for d in b.details)
    verified = "" if b.labels_verified else " — nhãn chưa xác nhận (tạm)"
    return (f"<h2 id='bound'>Ranh giới theo nhãn mẫu{_e(verified)}</h2>"
            f"<p>Trang {', '.join(map(str, b.pages))}: precision {_e(b.precision)} ({b.chunks_matched}/{b.chunks_on_pages} chunk), "
            f"recall {_e(b.recall)} ({b.matched}/{b.expected} đơn vị), đúng loại {_e(b.type_accuracy)}.</p>"
            f"<table class='t'><tr><th>Trang</th><th>Loại mong đợi</th><th>Đơn vị</th><th>Chunk khớp</th>"
            f"<th>Loại builder</th></tr>{rows}</table>"
            + (f"<p class='muted'>Chunk trên trang nhãn không khớp riêng đơn vị nào: {_e(', '.join(b.unmatched_chunks))}</p>"
               if b.unmatched_chunks else ""))


def _manual(q: ChunkQuality) -> str:
    m = q.manual
    if m is None:
        return ""
    rows = "".join(
        f"<tr><td>{x.manual_index}</td><td>{_e(x.manual_type)}</td><td>{_e(x.manual_title)}</td><td>{_e(x.manual_page)}</td>"
        f"<td>{x.manual_chars}</td><td>{_e(x.best_key or '—')}</td><td>{_e(x.best_type or '')}</td>"
        f"<td class='{'ok' if x.containment >= m.threshold else 'bad'}'>{x.containment}</td><td>{x.union_containment}</td></tr>"
        for x in m.matches)
    return (f"<h2 id='manual'>So với chunk viết tay (CSV) — báo cáo, không làm cổng</h2>"
            f"<p>{m.covered}/{m.manual_chunks} chunk tay có ≥ {m.threshold:.0%} token nằm trong một chunk builder. "
            f"Loại tay: {_e(m.manual_types)}; loại builder: {_e(m.builder_types)}.</p>"
            "<p class='muted'>Độ chứa = tỷ lệ token của chunk tay có trong chunk builder khớp nhất; cùng trang = trong "
            "mọi chunk builder phủ trang đó. Chunk tay có mô tả hình do người viết nên độ chứa thấp là bình thường "
            "với chunk hình chỉ có caption.</p>"
            f"<table class='t'><tr><th>#</th><th>Loại tay</th><th>Tiêu đề</th><th>Trang</th><th>Ký tự</th>"
            f"<th>Chunk builder</th><th>Loại</th><th>Độ chứa</th><th>Cùng trang</th></tr>{rows}</table>"
            f"<p class='muted'>Chunk builder không là khớp nhất của chunk tay nào: {len(m.builder_unmatched)}</p>")


def _review(q: ChunkQuality) -> str:
    r = q.review
    return (f"<h2 id='review'>Duyệt tay</h2><p>ok {r.ok}, fix {r.fix}, chờ {r.pending}, cũ (nội dung đổi) {r.stale}.</p>"
            "<p class='muted'>Ghi nhận xét vào <code>build/chunk_review.json</code>: với mỗi chunk đặt "
            "<code>verdict</code> = <code>ok</code> hoặc <code>fix</code>, <code>note</code>, <code>reviewer</code>; "
            "giữ nguyên <code>content_hash</code>. Chạy lại <code>build</code> để tổng hợp; nhận xét của chunk có "
            "nội dung đổi được tính là cũ.</p>"
            + (f"<div class='warn'>fix còn mở: {_e(', '.join(r.open_fix))}</div>" if r.open_fix else ""))


def _card(c: DraftChunk) -> str:
    role = c.chunk_role
    badges = "".join(f"<span class='badge'>{_e(x)}</span>" for x in
                     [c.chunk_type, ROLE_TEXT[role], *c.scopes, *c.control_interface, *c.spec_attributes])
    flags = "".join(f"<span class='badge bad'>{_e(x)}</span>" for x in c.flags + c.review_blockers)
    thumbs = "".join(f"<figure><img loading='lazy' src='../{_e(a.local_path)}' alt='{_e(a.element_id)}'>"
                     f"<figcaption class='muted'>{_e(a.element_id)}</figcaption></figure>"
                     for a in c.assets if a.local_path)
    meta = [f"trang PDF {c.page_start}–{c.page_end}", f"trang in {c.printed_page_start or '—'}",
            f"{len(c.content)} ký tự", f"token {c.token_count if c.token_count is not None else '—'}",
            f"hash {c.content_hash[:10]}"]
    if c.parent_key:
        meta.append(f"cha {c.parent_key.split(':')[-1]}")
    if c.related_chunk_keys:
        meta.append("liên quan " + ", ".join(k.split(":")[-1] for k in c.related_chunk_keys))
    body = f"<pre>{_e(c.content)}</pre>"
    if role == "parent":
        body = f"<details><summary>Content cha (nối các con)</summary>{body}</details>"
    extra = (f"<details><summary>embed_text, nhãn hình, element</summary><pre>{_e(c.embed_text)}</pre>"
             f"<p class='muted'>Nhãn hình: {_e(', '.join(f'{x.text} ({x.source})' for x in c.figure_labels) or '—')}</p>"
             f"<p class='muted'>element_ids: {_e(', '.join(c.element_ids))}</p></details>")
    return (f"<div class='card {role}' id='{_e(c.chunk_key.split(':')[-1])}' data-type='{_e(c.chunk_type)}' "
            f"data-role='{role}' data-flags='{_e(' '.join(c.flags + c.review_blockers))}' data-ps='{c.page_start}' "
            f"data-pe='{c.page_end}'><b>{_e(c.chunk_key.split(':')[-1])}</b> {badges}{flags}"
            f"<div>{_e(c.section_title)}</div><div class='muted'>{_e(' · '.join(meta))}</div>"
            f"<div class='muted'>Từ khóa: {_e(', '.join(c.keywords))}</div>{body}"
            f"<div class='thumbs'>{thumbs}</div>{extra}</div>")


def _cards(chunks: list[DraftChunk], q: ChunkQuality) -> str:
    options = lambda values: "".join(f"<option>{_e(v)}</option>" for v in values)  # noqa: E731
    flags = sorted({f for c in chunks for f in c.flags + c.review_blockers})
    filters = (f"<div class='filters'>Loại <select id='ft' onchange='f()'><option value=''>tất cả</option>"
               f"{options(sorted(q.by_type))}</select>Vai trò <select id='fr' onchange='f()'><option value=''>tất cả"
               f"</option><option value='parent'>cha</option><option value='child'>con</option><option value='standalone'>"
               f"độc lập</option></select>Cờ <select id='fg' onchange='f()'><option value=''>tất cả</option>"
               f"{options(flags)}</select>Trang <input id='fp' type='number' min='0' style='width:70px' oninput='f()'>"
               f"<span id='fn' class='muted'>{len(chunks)} chunk</span></div>")
    return "<h2 id='cards'>Chunk</h2>" + filters + "".join(_card(c) for c in chunks)


def render_chunks(result: BuildResult) -> str:
    q = result.quality
    texts = {e.element_id: e.text or e.normalized_type for e in result.run.elements}
    nav = ("<nav><a href='index.html'>Báo cáo chuẩn hóa</a><a href='#gate'>Cổng</a><a href='#checks'>CQ</a>"
           "<a href='#coverage'>Độ phủ</a><a href='#bound'>Ranh giới</a><a href='#manual'>So với chunk tay</a>"
           "<a href='#review'>Duyệt</a><a href='#cards'>Chunk</a></nav>")
    m = result.manifest
    head = (f"<h1>Chunk nháp — {_e(m.doc_id)}</h1><p class='muted'>{_e(m.doc_title)} · phiên bản {_e(m.doc_version)} · "
            f"model {_e(', '.join(m.product_models))} · run {_e(result.run.report.run_id)} · profile "
            f"{_e(result.run.report.profile_name)}. Bản nháp: chưa ghi DB, chưa có phần tiếng Việt (Bước 3).</p>")
    return ("<!doctype html><html lang='vi'><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>Chunk nháp</title>"
            f"<style>{_STYLE}</style><script>{_SCRIPT}</script></head><body><main>{head}{nav}"
            f"{_overview(q)}{_gate(q)}{_checks(q)}{_coverage(q, texts)}{_boundaries(q)}{_manual(q)}{_review(q)}"
            f"{_cards(result.chunks, q)}</main></body></html>")
