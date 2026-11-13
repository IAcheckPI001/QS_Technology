"""Kiểm hiện trạng bảng `doc_chunks` và hàm `match_doc_chunks` trên database thật (CHỈ ĐỌC).

Dùng `DATABASE_URL` qua Settings (không in giá trị). Mọi truy vấn chạy trong transaction READ ONLY.
Kết quả dùng cho tài liệu đánh giá schema (`docs/ai/reports/p2_doc_chunks_schema_review.md`).

Chạy từ `backend/`:
    .\\venv\\Scripts\\python.exe scripts\\inspect_doc_chunks.py [--out <file.md>]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.engine import AsyncSessionFactory, engine  # noqa: E402

QUERIES: list[tuple[str, str]] = [
    ("Cột", """
        select column_name, data_type, udt_name, is_nullable, column_default, is_generated, generation_expression
        from information_schema.columns
        where table_schema = 'public' and table_name = :t
        order by ordinal_position"""),
    ("Kiểu đầy đủ (số chiều vector)", """
        select a.attname, format_type(a.atttypid, a.atttypmod) as type
        from pg_attribute a join pg_class r on r.oid = a.attrelid
        where r.relname = :t and a.attname in ('embedding', 'fts') and not a.attisdropped"""),
    ("Ràng buộc", """
        select conname, contype, pg_get_constraintdef(c.oid) as def
        from pg_constraint c join pg_class r on r.oid = c.conrelid
        where r.relname = :t order by conname"""),
    ("Index", """
        select indexname, indexdef from pg_indexes
        where schemaname = 'public' and tablename = :t order by indexname"""),
    ("Hàm match_doc_chunks* (chữ ký)", """
        select p.proname, pg_get_function_identity_arguments(p.oid) as args,
               pg_get_function_result(p.oid) as result
        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public' and p.proname like 'match_doc_chunks%' order by p.proname"""),
    ("Extension đã cài", """
        select e.extname, e.extversion, n.nspname as schema
        from pg_extension e join pg_namespace n on n.oid = e.extnamespace order by e.extname"""),
    ("Hàm hỗ trợ (immutable_unaccent)", """
        select n.nspname as schema, p.proname, pg_get_function_identity_arguments(p.oid) as args, p.provolatile
        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where p.proname in ('immutable_unaccent', 'unaccent') order by 1, 2"""),
    ("Extension có thể cài (liên quan)", """
        select name, default_version, installed_version from pg_available_extensions
        where name in ('vector', 'unaccent', 'pg_trgm') order by name"""),
]

# Truy vấn dữ liệu theo bảng (chỉ chạy khi bảng tồn tại).
DATA_QUERIES: dict[str, list[tuple[str, str]]] = {
    "doc_chunks": [
        ("Số dòng theo doc_id, domain", """
            select doc_id, domain, count(*) as rows, count(*) filter (where is_active) as active,
                   count(embedding) as with_embedding, count(parent_id) as with_parent
            from doc_chunks group by doc_id, domain order by doc_id"""),
        ("Dòng hiện có (tóm tắt)", """
            select id, doc_id, chunk_index, chunk_type, domain, scopes, product_models, control_interface,
                   spec_attributes, is_active, parent_id, left(section_title, 60) as section_title,
                   length(content) as content_len, length(embed_text) as embed_len, token_count,
                   embedding is not null as has_embedding, lang, doc_type
            from doc_chunks order by doc_id, chunk_index limit 50"""),
    ],
    "doc_chunks_v2": [
        ("Số dòng theo tài liệu, vai trò, trạng thái duyệt", """
            select doc_id, doc_version, chunk_role, review_status, count(*) as rows,
                   count(*) filter (where is_active) as active, count(embedding) as with_embedding,
                   count(parent_id) as with_parent, count(*) filter (where cardinality(codes) > 0) as with_codes
            from doc_chunks_v2 group by 1, 2, 3, 4 order by 1, 2, 3, 4"""),
        ("Kiểm liên kết cha (con không có cha hợp lệ)", """
            select count(*) as broken from doc_chunks_v2 c
            where c.chunk_role = 'child'
              and not exists (select 1 from doc_chunks_v2 p where p.id = c.parent_id and p.chunk_role = 'parent')"""),
    ],
}

SETTINGS = ["server_version", "hnsw.ef_search", "hnsw.iterative_scan", "default_text_search_config"]


def _table(rows, keys) -> list[str]:
    if not rows:
        return ["(không có dòng)"]
    out = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    for row in rows:
        cells = [str(v).replace("|", "\\|").replace("\n", " ") if v is not None else "" for v in row]
        out.append("| " + " | ".join(cells) + " |")
    return out


async def main(out: Path | None, table: str) -> None:
    lines = [f"# Hiện trạng `{table}` trên database thật (chỉ đọc)", ""]
    async with AsyncSessionFactory() as session:
        await session.execute(text("set transaction read only"))
        exists = (await session.execute(text("select to_regclass(:q) is not null"), {"q": f"public.{table}"})).scalar()
        lines += [f"Bảng `public.{table}` {'có' if exists else '**chưa có**'}.", ""]
        queries = QUERIES + (DATA_QUERIES.get(table, []) + [("Kích thước bảng", f"""
            select pg_size_pretty(pg_total_relation_size('public.{table}')) as total""")] if exists else [])
        for title, sql in queries:
            result = await session.execute(text(sql), {"t": table})
            lines += [f"## {title}", ""] + _table(result.fetchall(), list(result.keys())) + [""]
        lines += ["## Tham số", ""]
        for name in SETTINGS:
            try:
                async with session.begin_nested():
                    value = (await session.execute(text(f"show {name}"))).scalar()
            except Exception as exc:  # tham số của extension chưa nạp → báo, không dừng
                value = f"(không đọc được: {type(exc).__name__})"
            lines.append(f"- `{name}` = {value}")
        lines.append("")
        defs = await session.execute(text("""
            select p.proname, pg_get_function_identity_arguments(p.oid), pg_get_functiondef(p.oid)
            from pg_proc p join pg_namespace n on n.oid = p.pronamespace
            where n.nspname = 'public' and p.proname like 'match_doc_chunks%' order by p.proname"""))
        for name, args, body in defs.fetchall():
            lines += [f"## Định nghĩa `{name}({args})`", "", "```sql", body.strip(), "```", ""]
        await session.rollback()
    await engine.dispose()
    report = "\n".join(lines)
    if out:
        out.write_text(report, encoding="utf-8")
        print(f"→ {out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--table", choices=sorted(DATA_QUERIES), default="doc_chunks")
    args = parser.parse_args()
    if sys.platform == "win32":   # psycopg async không chạy trên ProactorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(args.out, args.table))
