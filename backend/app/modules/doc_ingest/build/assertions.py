"""Kiểm cấu trúc chunk CQ-01…CQ-10 (BL-15; golden tests §4, contract C2 §10). Chỉ đọc, không sửa chunk."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.modules.doc_ingest.build.render import data_rows, header_line, parse_markdown_row, row_line
from app.modules.doc_ingest.schemas.chunk import VISUAL_TYPES, CheckResult, DraftChunk
from app.modules.doc_ingest.schemas.normalized import LogicalTable, NormalizedElement

MAX_FAILURES = 50


def _result(check_id: str, title: str, checked: int, failures: list[str], note: str = "") -> CheckResult:
    return CheckResult(check_id=check_id, title=title, checked=checked,
                       passed=None if checked == 0 else not failures,
                       failures=failures[:MAX_FAILURES],
                       note=note + (f" ({len(failures)} lỗi, hiện {MAX_FAILURES})" if len(failures) > MAX_FAILURES else ""))


def _leaves(chunks: Sequence[DraftChunk]) -> list[DraftChunk]:
    return [c for c in chunks if c.chunk_role != "parent"]


def cq01_table_header(chunks: Sequence[DraftChunk], tables: dict[str, LogicalTable]) -> CheckResult:
    failures, checked = [], 0
    for c in chunks:
        if c.logical_table_id is None or c.chunk_role == "parent":
            continue
        table = tables.get(c.logical_table_id)
        if table is None:
            failures.append(f"{c.chunk_key}: không tìm thấy bảng {c.logical_table_id}")
            continue
        checked += 1
        n = len(table.columns)
        header = header_line(table)
        table_lines = [line for line in c.content.split("\n") if line.startswith("|") and not line.startswith("|---")]
        if header is not None and (not table_lines or table_lines[0] != header):
            failures.append(f"{c.chunk_key}: thiếu dòng header khớp columns")
        for line in table_lines:
            if len(parse_markdown_row(line)) != n:
                failures.append(f"{c.chunk_key}: dòng có {len(parse_markdown_row(line))} ô ≠ {n} cột: {line[:60]}")
                break
    return _result("CQ-01", "Header bảng khớp columns, mọi dòng đủ số ô", checked, failures)


def cq02_rows_whole(chunks: Sequence[DraftChunk], tables: dict[str, LogicalTable]) -> CheckResult:
    failures, checked = [], 0
    seen: Counter[tuple[str, str]] = Counter()
    for c in _leaves(chunks):
        if c.logical_table_id is None:
            continue
        table = tables.get(c.logical_table_id)
        if table is None:
            continue
        by_id = {r.row_id: r for r in table.rows}
        for rid in c.row_ids:
            seen[(c.logical_table_id, rid)] += 1
            row = by_id.get(rid)
            if row is not None and row_line(table, row) not in c.content.split("\n"):
                failures.append(f"{c.chunk_key}: dòng {rid} không nằm trọn trên một dòng")
    for tid in {c.logical_table_id for c in chunks if c.logical_table_id}:
        table = tables.get(tid)
        if table is None:
            continue
        rows = data_rows(table) if header_line(table) else [r for r in table.rows if not r.repeated_header]
        for row in rows:
            checked += 1
            count = seen[(tid, row.row_id)]
            if count != 1:
                failures.append(f"{tid}:{row.row_id}: nằm trong {count} chunk (phải đúng 1)")
    return _result("CQ-02", "Không cắt giữa một dòng bảng; mỗi dòng nằm trong đúng một chunk", checked, failures)


def cq03_length(chunks: Sequence[DraftChunk], tables: dict[str, LogicalTable], limit: int) -> CheckResult:
    failures = [f"{c.chunk_key}: {len(c.content)} ký tự" for c in chunks if len(c.content) > limit]
    for c in _leaves(chunks):
        if c.logical_table_id and "table_part" in c.flags:
            table = tables.get(c.logical_table_id)
            header = header_line(table) if table is not None else None
            if header is not None and header not in c.content.split("\n"):
                failures.append(f"{c.chunk_key}: phần bảng không lặp header")
    return _result("CQ-03", f"content ≤ {limit} ký tự; phần bảng lặp header", len(chunks), failures)


def cq04_warning_links(chunks: Sequence[DraftChunk], by_id: dict[str, NormalizedElement]) -> CheckResult:
    keys = {c.chunk_key: c for c in chunks}
    failures, checked = [], 0
    alarms_unlinked = 0
    for c in _leaves(chunks):
        has_warning = any(by_id[e].normalized_type == "warning" for e in c.element_ids if e in by_id)
        if not has_warning and c.chunk_type != "alarm":
            continue
        if not c.related_chunk_keys:
            if has_warning:
                checked += 1
                failures.append(f"{c.chunk_key}: chunk warning không có related_chunk_keys")
            else:
                alarms_unlinked += 1
            continue
        checked += 1
        for key in c.related_chunk_keys:
            other = keys.get(key)
            if other is None or other.section_path != c.section_path:
                failures.append(f"{c.chunk_key}: related {key} không tồn tại hoặc khác section_path")
    note = f"{alarms_unlinked} chunk alarm không đi sau thủ tục (không bắt buộc liên kết)" if alarms_unlinked else ""
    return _result("CQ-04", "Chunk warning/alarm liên kết tới chunk tồn tại cùng mục", checked, failures, note)


def cq05_provenance(chunks: Sequence[DraftChunk]) -> CheckResult:
    failures = []
    printed_missing = 0
    for c in chunks:
        if not c.doc_id or c.page_start is None or c.page_end is None or not c.element_ids:
            failures.append(f"{c.chunk_key}: thiếu doc_id/trang/element_ids")
        if c.page_start is not None and c.page_end is not None and c.page_start > c.page_end:
            failures.append(f"{c.chunk_key}: page_start > page_end")
        if c.printed_page_start is None:
            printed_missing += 1
    note = f"{printed_missing} chunk không có trang in (T-06 không có nguồn; không tính lỗi)" if printed_missing else ""
    return _result("CQ-05", "Provenance: doc_id, trang PDF, element_ids", len(chunks), failures, note)


def cq06_assets(chunks: Sequence[DraftChunk], by_id: dict[str, NormalizedElement]) -> CheckResult:
    failures, checked, missing = [], 0, 0
    for c in chunks:
        for asset in c.assets:
            checked += 1
            element = by_id.get(asset.element_id)
            if element is None or element.normalized_type not in ("picture", "screenshot"):
                failures.append(f"{c.chunk_key}: asset {asset.element_id} không phải picture/screenshot")
            if asset.local_path is None:
                missing += 1
        # loại wiring/pinout/dimension cũng gán cho đoạn văn/bảng theo tiêu đề mục: chỉ `figure` bắt buộc có ảnh
        if c.chunk_role != "parent" and (c.chunk_type == "figure" or (c.assets and c.chunk_type in VISUAL_TYPES)):
            checked += 1
            if not c.assets:
                failures.append(f"{c.chunk_key}: chunk hình không có asset")
            if not c.content.strip():
                failures.append(f"{c.chunk_key}: chunk hình không có caption/tiêu đề")
    note = f"{missing} asset chưa có ảnh render (chạy không kèm PDF)" if missing else ""
    return _result("CQ-06", "Asset resolve được, không phải watermark; chunk hình có caption/tiêu đề", checked,
                   failures, note)


def cq07_not_available(chunks: Sequence[DraftChunk]) -> CheckResult:
    failures, checked = [], 0
    for c in chunks:
        for cand in c.applicability:
            if cand.status != "not_available":
                continue
            checked += 1
            if cand.note not in c.content:
                failures.append(f"{c.chunk_key}: ghi chú '{cand.note[:40]}' không còn nguyên văn trong content")
    return _result("CQ-07", "Ghi chú not_available giữ nguyên văn (không render thành câu khẳng định)", checked,
                   failures)


def cq08_parents(chunks: Sequence[DraftChunk]) -> CheckResult:
    keys = {c.chunk_key: c for c in chunks}
    failures = []
    for c in chunks:
        if c.parent_key is None:
            if c.chunk_role == "child":
                failures.append(f"{c.chunk_key}: role child nhưng không có parent_key")
            continue
        parent = keys.get(c.parent_key)
        if parent is None:
            failures.append(f"{c.chunk_key}: parent_key {c.parent_key} không tồn tại")
        elif parent.parent_key is not None or parent.chunk_role != "parent" or c.chunk_key == c.parent_key:
            failures.append(f"{c.chunk_key}: cha {c.parent_key} không phải chunk cha cấp một")
    for c in chunks:
        if c.chunk_role == "parent" and not any(x.parent_key == c.chunk_key for x in chunks):
            failures.append(f"{c.chunk_key}: chunk cha không có con")
    return _result("CQ-08", "parent_key resolve được, một cấp, không chu trình", len(chunks), failures)


def cq09_child_in_parent(chunks: Sequence[DraftChunk]) -> CheckResult:
    keys = {c.chunk_key: c for c in chunks}
    failures, checked = [], 0
    for c in chunks:
        parent = keys.get(c.parent_key) if c.parent_key else None
        if parent is None:
            continue
        checked += 1
        if c.content not in parent.content:
            failures.append(f"{c.chunk_key}: content không nằm trong content cha {parent.chunk_key}")
        missing = {a.element_id for a in c.assets} - {a.element_id for a in parent.assets}
        if missing:
            failures.append(f"{c.chunk_key}: asset {sorted(missing)} không có ở cha")
    return _result("CQ-09", "content con ⊂ content cha; assets con ⊆ assets cha", checked, failures)


def cq10_no_split(chunks: Sequence[DraftChunk], by_id: dict[str, NormalizedElement]) -> CheckResult:
    """Không tách parameter khỏi giá trị của nó, caption khỏi hình; bước/dòng bảng xem CQ-02 và độ phủ."""
    home: dict[str, set[str]] = {}
    for c in _leaves(chunks):
        for e in c.element_ids:
            home.setdefault(e, set()).add(c.chunk_key)
    failures, checked = [], 0
    for e in by_id.values():
        if e.element_id not in home:
            continue
        if e.list_info is not None and e.list_info.parent_element_id and any(r.role == "value_option"
                                                                             for r in e.param_refs):
            checked += 1
            parent_home = home.get(e.list_info.parent_element_id, set())
            if parent_home and not (home[e.element_id] & parent_home):
                failures.append(f"{e.element_id}: giá trị parameter khác chunk với định nghĩa "
                                f"{e.list_info.parent_element_id}")
        if e.normalized_type in ("picture", "screenshot") and e.caption_element_id in home:
            checked += 1
            if not (home[e.element_id] & home[e.caption_element_id]):
                failures.append(f"{e.element_id}: caption {e.caption_element_id} khác chunk với hình")
    return _result("CQ-10", "Không tách định nghĩa parameter khỏi giá trị, caption khỏi hình", checked, failures)


def cq11_table_embed(chunks: Sequence[DraftChunk]) -> CheckResult:
    """Chunk bảng phải vào trọn `embed_text` (I-38): dòng bị cắt khỏi embedding thì mã ở đó không tìm được.
    Ngoại lệ: phần chỉ có một dòng mà vẫn vượt giới hạn (không cắt trong dòng) — ghi chú để người duyệt xem."""
    failures, checked, single = [], 0, 0
    for c in _leaves(chunks):
        if c.logical_table_id is None:
            continue
        checked += 1
        if "embed_truncated" not in c.flags:
            continue
        if len(c.row_ids) <= 1:
            single += 1
        else:
            failures.append(f"{c.chunk_key}: {len(c.row_ids)} dòng nhưng embed_text bị cắt (embed_truncated)")
    note = f"{single} phần một dòng vượt giới hạn embed_text (không cắt trong dòng)" if single else ""
    return _result("CQ-11", "Chunk bảng nằm trọn trong embed_text", checked, failures, note)


def cq12_embed_budget(chunks: Sequence[DraftChunk]) -> CheckResult:
    """Chunk lá có `embed_text` ≤ `embed_max_tokens` − `embed_enrich_reserve` (I-43, D-008: chỉ chunk lá được embed
    và tìm; chỗ dự trữ dành cho tóm tắt + câu hỏi của Bước 3). Builder gắn cờ `embed_over_budget`.
    Phần bảng nhiều dòng vượt → không đạt (luật chia bảng I-38 bảo đảm); lá khác vượt (khối nguyên vẹn không cắt,
    hoặc phần bảng một dòng) → ghi chú để người duyệt xem. Chunk cha không tính."""
    failures, checked, noted = [], 0, []
    for c in _leaves(chunks):
        checked += 1
        if "embed_over_budget" not in c.flags:
            continue
        if c.logical_table_id is not None and len(c.row_ids) > 1:
            failures.append(f"{c.chunk_key}: phần bảng {len(c.row_ids)} dòng vượt ngân sách embed ({c.token_count} token)")
        else:
            noted.append(f"{c.chunk_key} ({c.token_count})")
    note = f"{len(noted)} chunk lá vượt ngân sách embed: {', '.join(noted)}" if noted else ""
    return _result("CQ-12", "Chunk lá nằm trong ngân sách embed_text (chừa chỗ Bước 3)", checked, failures, note)


def review_blockers_carried(chunks: Sequence[DraftChunk], blocking: dict[str, set[str]],
                            blocking_pages: dict[int, set[str]]) -> CheckResult:
    """Chunk chứa phần tử (hoặc nằm trên trang) có review chặn chunk phải mang `review_blockers`."""
    failures, checked = [], 0
    for c in _leaves(chunks):
        codes = set().union(*(blocking.get(e, set()) for e in c.element_ids), *(
            blocking_pages.get(p, set()) for p in range(c.page_start, c.page_end + 1)))
        if not codes:
            continue
        checked += 1
        if not codes <= set(c.review_blockers):
            failures.append(f"{c.chunk_key}: thiếu review_blockers {sorted(codes - set(c.review_blockers))}")
    return _result("CQ-RB", "Chunk từ phần tử có review chặn chunk mang review_blockers", checked, failures)


def run_checks(chunks: Sequence[DraftChunk], tables: dict[str, LogicalTable],
               elements: Sequence[NormalizedElement], blocking: dict[str, set[str]], limit: int,
               blocking_pages: dict[int, set[str]] | None = None) -> list[CheckResult]:
    by_id = {e.element_id: e for e in elements}
    return [
        cq01_table_header(chunks, tables), cq02_rows_whole(chunks, tables), cq03_length(chunks, tables, limit),
        cq04_warning_links(chunks, by_id), cq05_provenance(chunks), cq06_assets(chunks, by_id),
        cq07_not_available(chunks), cq08_parents(chunks), cq09_child_in_parent(chunks),
        cq10_no_split(chunks, by_id), cq11_table_embed(chunks), cq12_embed_budget(chunks), review_blockers_carried(chunks, blocking, blocking_pages or {}),
    ]
