"""Điền cờ B2 (`has_tool_errors`, `is_handoff`, `product_models`, `ticket_id`) cho các dòng
`chat_history` cũ, tính bằng đúng hàm Python mà luồng ghi lượt dùng (`turn_flags`).

Mặc định chỉ đếm số dòng lệch (dry-run, transaction READ ONLY); `--apply` mới UPDATE. Không đổi
`updated_date`. UPDATE không kích hoạt trigger tóm tắt (trigger chỉ chạy khi INSERT), nên sau
`--apply` phải chạy `select public.rebuild_chat_conversations();` (FRONTEND_REQUIREMENTS 19.11).
Chạy lại nhiều lần vẫn an toàn: dòng đã đúng không bị ghi lại.

Dùng `DATABASE_URL` qua Settings (không in giá trị). Chạy từ `backend/`:
    .\\venv\\Scripts\\python.exe scripts\\backfill_history_flags.py [--env-file <đường dẫn .env>] [--apply]
"""

from __future__ import annotations

import argparse
import asyncio
import selectors
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FLAG_FIELDS = ("has_tool_errors", "is_handoff", "product_models", "ticket_id")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", help="Nạp biến môi trường từ file này trước khi đọc Settings.")
    parser.add_argument("--apply", action="store_true", help="Ghi thay đổi (mặc định chỉ đếm).")
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


async def run(apply: bool, batch_size: int) -> None:
    from sqlalchemy import select, text, tuple_, update

    from app.db.engine import AsyncSessionFactory, engine
    from app.db.models.history import ChatHistory
    from app.modules.chatbot.services.turn_sources import turn_flags

    scanned = 0
    changed: Counter[str] = Counter()
    rows_changed = 0
    cursor = None
    try:
        async with AsyncSessionFactory() as session:
            if not apply:
                await session.execute(text("set transaction read only"))
            while True:
                query = (
                    select(
                        ChatHistory.id,
                        ChatHistory.created_at,
                        ChatHistory.retrieval_snapshot,
                        ChatHistory.conversation_state,
                        *(getattr(ChatHistory, field) for field in FLAG_FIELDS),
                    )
                    .order_by(ChatHistory.created_at, ChatHistory.id)
                    .limit(batch_size)
                )
                if cursor is not None:
                    query = query.where(tuple_(ChatHistory.created_at, ChatHistory.id) > cursor)
                batch = (await session.execute(query)).all()
                if not batch:
                    break
                for row in batch:
                    scanned += 1
                    flags = turn_flags(row.retrieval_snapshot, row.conversation_state)
                    diff = {
                        field: value
                        for field, value in flags.items()
                        if (list(getattr(row, field) or []) if field == "product_models" else getattr(row, field)) != value
                    }
                    if not diff:
                        continue
                    rows_changed += 1
                    changed.update(diff.keys())  # đếm theo tên cột, không cộng giá trị
                    if apply:
                        await session.execute(
                            update(ChatHistory)
                            .where(ChatHistory.id == row.id)
                            # Giữ nguyên updated_date (cột có onupdate=now()).
                            .values(**diff, updated_date=ChatHistory.updated_date)
                        )
                cursor = (batch[-1].created_at, batch[-1].id)
                if apply:
                    await session.commit()
    finally:
        await engine.dispose()

    print(f"Đã quét: {scanned} lượt")
    print(f"Lượt lệch cờ: {rows_changed}")
    for field in FLAG_FIELDS:
        print(f"  {field}: {changed.get(field, 0)}")
    if apply:
        print("Đã ghi. Bước tiếp: select public.rebuild_chat_conversations();")
    elif rows_changed:
        print("Dry-run, chưa ghi. Chạy lại với --apply để ghi.")


def main() -> None:
    args = _parse_args()
    if args.env_file:
        from dotenv import load_dotenv

        if not load_dotenv(args.env_file, override=False):
            sys.exit(f"Không đọc được env file: {args.env_file}")
    # Windows: psycopg async cần SelectorEventLoop (cùng cách service_keys_cli).
    asyncio.run(run(args.apply, args.batch_size), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))


if __name__ == "__main__":
    main()
