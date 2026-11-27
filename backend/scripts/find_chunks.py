"""Tìm chunk trong `doc_chunks_v2` để gắn nhãn bộ vàng (kế hoạch §9, GD1). Chỉ đọc database.

In mỗi chunk: id, tài liệu, đường dẫn mục, trang, độ dài, `content_hash` rút gọn, đoạn nội dung; với `--yaml` in sẵn mục `expected`
để dán vào file câu hỏi (`evals/retrieval_cases/*.yaml`). Chunk khớp theo (`content_hash`, `section_path`), không theo id.

Chạy từ `backend/`:
    .\\venv\\Scripts\\python.exe scripts\\find_chunks.py --kw "home" --doc f54-operation-en --show 300
    .\\venv\\Scripts\\python.exe scripts\\find_chunks.py --id 1553 --show 2000 --yaml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def yaml_entry(row: dict[str, Any], note_chars: int = 70) -> str:
    """Mục `expected` dạng YAML flow cho một chunk (khóa khớp: content_hash + section_path)."""
    path = json.dumps(list(row["section_path"]), ensure_ascii=False)
    note = " ".join((row.get("content") or "").split())[:note_chars].replace('"', "'")
    return (f'      - {{chunk_key: {row["chunk_key"]}, content_hash: {row["content_hash"]}, section_path: {path}, '
            f'note: "{note}"}}')


def format_row(row: dict[str, Any], show: int = 160) -> str:
    pages = f'{row["page_start"]}' if row["page_end"] in (None, row["page_start"]) else f'{row["page_start"]}-{row["page_end"]}'
    head = (f'#{row["id"]} {row["doc_id"]} tr.{pages} [{row["chunk_type"]}/{row["chunk_role"]}] {len(row["content"])} ký tự, '
            f'ảnh {len(row.get("assets") or [])}, hash {row["content_hash"][:8]}\n  {" › ".join(row["section_path"])}')
    body = " ".join((row["content"] or "").split())[:show]
    return head + (f"\n  {body}" if show else "")


async def fetch(args: argparse.Namespace) -> list[dict[str, Any]]:
    from sqlalchemy import text

    from app.db.engine import engine
    from app.db.session import AsyncSessionFactory

    where, params = ["is_active"], {"limit": args.limit}
    if args.id:
        where.append("id = any(cast(:ids as bigint[]))")
        params["ids"] = args.id
    if args.doc:
        where.append("doc_id = :doc")
        params["doc"] = args.doc
    if args.model:
        where.append(":model = any(product_models)")
        params["model"] = args.model
    for i, kw in enumerate(args.kw or []):
        where.append(f"(content ilike :k{i} or section_title ilike :k{i})")
        params[f"k{i}"] = f"%{kw}%"
    if args.min_len:
        where.append("length(content) >= :min_len")
        params["min_len"] = args.min_len
    sql = ("select id, chunk_key, doc_id, chunk_type, chunk_role, section_path, page_start, page_end, content, content_hash, assets "
           f"from doc_chunks_v2 where {' and '.join(where)} order by doc_id, chunk_index limit :limit")
    try:
        async with AsyncSessionFactory() as session:
            rows = [dict(r) for r in (await session.execute(text(sql), params)).mappings()]
    finally:
        await engine.dispose()
    for r in rows:
        if isinstance(r.get("assets"), str):
            r["assets"] = json.loads(r["assets"])
    return rows


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Tìm chunk để gắn nhãn bộ vàng")
    parser.add_argument("--kw", action="append", help="từ khóa (lặp lại = cả hai cùng có), không phân biệt hoa thường")
    parser.add_argument("--doc", help="doc_id, vd f54-operation-en")
    parser.add_argument("--model", help="model, vd F54")
    parser.add_argument("--id", type=int, action="append", help="id chunk (có thể lặp lại)")
    parser.add_argument("--min-len", type=int, default=0, help="độ dài nội dung tối thiểu (loại chunk chỉ có tiêu đề)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--show", type=int, default=160, help="số ký tự nội dung in ra (0 = không in)")
    parser.add_argument("--yaml", action="store_true", help="in mục expected YAML sau mỗi chunk")
    args = parser.parse_args(argv)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    rows = asyncio.run(fetch(args))
    for row in rows:
        print(format_row(row, args.show))
        if args.yaml:
            print(yaml_entry(row))
    print(f"-- {len(rows)} chunk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
