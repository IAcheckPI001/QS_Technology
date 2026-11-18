"""So bảng tóm tắt `chat_conversations` với kết quả tính lại từ `chat_history` (CHỈ ĐỌC).

Báo phiên thiếu dòng tóm tắt, dòng tóm tắt thừa và từng cột lệch (R2, R3, R5 trong
FRONTEND_REQUIREMENTS 19.11). Có lệch thì sửa bằng `select public.rebuild_chat_conversations();`.
Exit code 1 khi có lệch, để dùng được trong kiểm tra định kỳ.

Dùng `DATABASE_URL` qua Settings (không in giá trị). Chạy từ `backend/`:
    .\\venv\\Scripts\\python.exe scripts\\check_conversation_summary.py [--env-file <đường dẫn .env>] [--show 20]
"""

from __future__ import annotations

import argparse
import asyncio
import selectors
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Tính lại đúng ngữ nghĩa của chat_conversations_apply khi phát lại theo (created_at, id).
EXPECTED_SQL = """
with ordered as (
  select h.*, row_number() over (partition by session_id order by created_at desc, id desc) as rn_desc,
         row_number() over (partition by session_id order by created_at, id) as rn_asc
  from public.chat_history h
),
agg as (
  select session_id,
         count(*)::int as question_count,
         min(created_at) as started_at,
         max(created_at) as last_message_at,
         coalesce(sum(cost_usd), 0)::double precision as cost_usd,
         bool_or(is_handoff) as has_handoff,
         bool_or(has_tool_errors) as has_tool_errors
  from public.chat_history group by session_id
),
expected as (
  select a.*,
         f.channel,
         l.id as last_history_id, l.query_origin as last_query, l.status as last_status,
         coalesce((select o.product_models from ordered o
                   where o.session_id = a.session_id and cardinality(o.product_models) > 0
                   order by o.rn_desc limit 1), '{}') as product_models,
         (select o.ticket_id from ordered o
          where o.session_id = a.session_id and o.ticket_id is not null
          order by o.rn_desc limit 1) as ticket_id
  from agg a
  join ordered l on l.session_id = a.session_id and l.rn_desc = 1
  join ordered f on f.session_id = a.session_id and f.rn_asc = 1
)
select coalesce(e.session_id, c.session_id) as session_id,
       e.session_id is null as extra, c.session_id is null as missing,
       array_remove(array[
         case when e.question_count is distinct from c.question_count then 'question_count' end,
         case when e.started_at is distinct from c.started_at then 'started_at' end,
         case when e.last_message_at is distinct from c.last_message_at then 'last_message_at' end,
         case when abs(coalesce(e.cost_usd, 0) - coalesce(c.cost_usd, 0)) > 1e-6 then 'cost_usd' end,
         case when e.has_handoff is distinct from c.has_handoff then 'has_handoff' end,
         case when e.has_tool_errors is distinct from c.has_tool_errors then 'has_tool_errors' end,
         case when e.channel is distinct from c.channel then 'channel' end,
         case when e.last_history_id is distinct from c.last_history_id then 'last_history_id' end,
         case when e.last_status is distinct from c.last_status then 'last_status' end,
         case when e.product_models is distinct from c.product_models then 'product_models' end,
         case when e.ticket_id is distinct from c.ticket_id then 'ticket_id' end
       ], null) as diff
from expected e
full join public.chat_conversations c on c.session_id = e.session_id
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", help="Nạp biến môi trường từ file này trước khi đọc Settings.")
    parser.add_argument("--show", type=int, default=20, help="Số phiên lệch in ra (mặc định 20).")
    return parser.parse_args()


async def run(show: int) -> int:
    from collections import Counter

    from sqlalchemy import text

    from app.db.engine import AsyncSessionFactory, engine

    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("set transaction read only"))
            rows = (await session.execute(text(EXPECTED_SQL))).all()
    finally:
        await engine.dispose()

    missing = [row for row in rows if row.missing]
    extra = [row for row in rows if row.extra]
    drift = [row for row in rows if not row.missing and not row.extra and row.diff]
    columns = Counter(column for row in drift for column in row.diff)

    print(f"Phiên: {len(rows)}")
    print(f"Thiếu dòng tóm tắt: {len(missing)}")
    print(f"Dòng tóm tắt thừa: {len(extra)}")
    print(f"Phiên lệch cột: {len(drift)}")
    for column, count in columns.most_common():
        print(f"  {column}: {count}")
    for row in (missing + extra + drift)[:show]:
        kind = "thiếu" if row.missing else "thừa" if row.extra else ", ".join(row.diff)
        print(f"  {row.session_id}: {kind}")
    bad = len(missing) + len(extra) + len(drift)
    print("Khớp." if not bad else "Có lệch: chạy select public.rebuild_chat_conversations(); rồi kiểm lại.")
    return 1 if bad else 0


def main() -> None:
    args = _parse_args()
    if args.env_file:
        from dotenv import load_dotenv

        if not load_dotenv(args.env_file, override=False):
            sys.exit(f"Không đọc được env file: {args.env_file}")
    # Windows: psycopg async cần SelectorEventLoop (cùng cách service_keys_cli).
    sys.exit(asyncio.run(run(args.show), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())))


if __name__ == "__main__":
    main()
