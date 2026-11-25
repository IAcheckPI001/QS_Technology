"""Xuất câu hỏi thật từ `chat_history` để chọn ứng viên cho bộ vàng (kế hoạch §9, GD0). Chỉ đọc database.

Ẩn thông tin cá nhân bằng quy tắc (email, số điện thoại, URL, dãy số dài); tên người và địa chỉ KHÔNG tự phát hiện được nên
cột `can_ra_soat` = 1 khi có thay thế, và người duyệt phải đọc lại toàn bộ file trước khi đưa câu vào bộ vàng. Bỏ câu trùng
(so theo chữ thường, bỏ khoảng trắng thừa). Không đưa câu trả lời, session hay id gốc ra file.

Chạy từ `backend/`:
    .\\venv\\Scripts\\python.exe scripts\\export_chat_log.py [--channel website] [--since 2026-11-20] [--limit 500]
Kết quả: `data/gold_candidates/chat_log_<ngày>.csv` (UTF-8 có BOM). Thư mục `data/` không được commit.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUTPUT = ROOT.parent / "data" / "gold_candidates"
COLUMNS = ["ma", "ngay", "kenh", "cau_hoi", "cau_chuan_hoa", "model", "co_chunk", "so_tu", "can_ra_soat", "chon", "ghi_chu"]

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)[\s.-]?\d(?:[\s.-]?\d){7,9}(?!\d)")
_LONG_NUMBER = re.compile(r"(?<![\w#.])\d{9,}(?![\w])")


def anonymize(text: str) -> tuple[str, bool]:
    """(văn bản đã ẩn, có thay thế không). Thứ tự quan trọng: email/URL trước, rồi số điện thoại, rồi dãy số dài."""
    original = text or ""
    out = _EMAIL.sub("<email>", original)
    out = _URL.sub("<url>", out)
    out = _PHONE.sub("<sdt>", out)
    out = _LONG_NUMBER.sub("<so>", out)
    return out, out != original


def dedupe_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def make_rows(records: list[dict]) -> list[dict]:
    """`records`: query_origin, normalized_query, created_at, channel, product_models, has_chunks, id (nhiều bản ghi
    cùng câu → giữ bản đầu theo thứ tự đưa vào). Mã `ma` băm từ id nên không lộ id gốc."""
    seen: set[str] = set()
    rows = []
    for rec in records:
        key = dedupe_key(rec["query_origin"])
        if not key or key in seen:
            continue
        seen.add(key)
        question, changed_q = anonymize(rec["query_origin"].strip())
        normalized, changed_n = anonymize((rec.get("normalized_query") or "").strip())
        rows.append({
            "ma": hashlib.sha256(str(rec["id"]).encode()).hexdigest()[:10], "ngay": rec["created_at"].strftime("%Y-%m-%d"),
            "kenh": rec["channel"], "cau_hoi": question, "cau_chuan_hoa": normalized,
            "model": ",".join(rec.get("product_models") or []), "co_chunk": int(bool(rec.get("has_chunks"))),
            "so_tu": len(question.split()), "can_ra_soat": int(changed_q or changed_n), "chon": "", "ghi_chu": ""})
    return rows


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


async def fetch(channel: str, since: str | None, limit: int) -> list[dict]:
    from sqlalchemy import text

    from app.db.engine import engine
    from app.db.session import AsyncSessionFactory

    where, params = ["channel = :channel", "status = 'completed'"], {"channel": channel, "limit": limit}
    if since:
        where.append("created_at >= :since")
        params["since"] = datetime.fromisoformat(since)
    sql = ("select id, created_at, channel, query_origin, normalized_query, product_models, "
           "coalesce(jsonb_array_length(retrieval_snapshot->'chunks'), 0) > 0 as has_chunks "
           f"from chat_history where {' and '.join(where)} order by created_at desc limit :limit")
    try:
        async with AsyncSessionFactory() as session:
            return [dict(r) for r in (await session.execute(text(sql), params)).mappings()]
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Xuất câu hỏi thật (ẩn danh) làm ứng viên bộ vàng")
    parser.add_argument("--channel", default="website")
    parser.add_argument("--since", default=None, help="chỉ lấy từ ngày này (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args(argv)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    rows = make_rows(asyncio.run(fetch(args.channel, args.since, args.limit)))
    path = OUTPUT / f"chat_log_{datetime.now():%Y%m%d}.csv"
    write_rows(path, rows)
    print(f"{len(rows)} câu duy nhất, {sum(r['can_ra_soat'] for r in rows)} câu có thay thế cần rà soát: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
