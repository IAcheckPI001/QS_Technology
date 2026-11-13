"""Nạp `build/doc_chunks_v2.jsonl` của luồng chunking vào bảng `doc_chunks_v2` (D-009).

Đầu vào do adapter `doc_ingest/export/doc_chunks_v2.py` sinh (không import `doc_ingest`: ranh giới import của tool
offline). Loader:
- kiểm dòng trước khi ghi: cột bắt buộc, vai trò, `parent_key` trỏ tới chunk cha trong bộ, khóa không trùng, một
  tài liệu + một phiên bản mỗi file, **model ⊆ registry** của dịch vụ chat (bảng không check danh sách model);
- embed `embed_text` **trước** (chunk lá; chunk cha chỉ khi `--embed-parents`, dùng khi đo biến thể "tìm cả cha");
- trong **một transaction**: xóa bản cũ cùng (`doc_id`, `doc_version`), insert chunk cha lấy `id`, gán `parent_id`
  cho chunk con (sửa E-01), insert phần còn lại. Lỗi giữa chừng → rollback, bảng giữ nguyên.

Chạy từ `backend/` (venv chính):
    .\\venv\\Scripts\\python.exe -m app.modules.chunking_loader.load_ingest_run --rows <run>/build/doc_chunks_v2.jsonl --dry-run
    ... --rows <file> --apply [--embed-parents]
    ... --delete --doc-id <doc_id> [--doc-version <v>]
    ... --copy-v1      (chép chunk viết tay của bảng cũ doc_chunks sang v2, source=manual)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

TABLE = "public.doc_chunks_v2"
ROLES = ("parent", "child", "standalone")
STATUSES = ("draft", "approved")
DOMAINS = ("technical_docs", "company_info", "product_catalog")
SCOPES = ("installation", "operation", "configuration", "maintenance")
REQUIRED = ("doc_id", "doc_version", "doc_title", "doc_type", "chunk_key", "chunk_type", "section_title", "content",
            "embed_text", "content_hash")
ARRAY_COLUMNS = ("scopes", "product_models", "applies_to_models", "control_interface", "spec_attributes",
                 "section_path", "keywords", "codes")
JSON_COLUMNS = ("assets", "metadata")
# Cột lấy nguyên từ dòng (thứ tự = thứ tự INSERT); parent_id, embedding, embedding_model do loader thêm.
COLUMNS = ("doc_id", "doc_version", "doc_title", "doc_type", "lang", "chunk_key", "chunk_index", "chunk_role",
           "chunk_type", "domain", "scopes", "product_models", "applies_to_models", "control_interface",
           "spec_attributes", "section_id", "section_path", "section_title", "page_start", "page_end",
           "printed_page_start", "printed_page_end", "content", "summary_vi", "keywords", "codes", "embed_text",
           "token_count", "content_hash", "assets", "metadata", "source", "review_status", "is_active", "source_run")
EMBED_BATCH = 100
EMBED_USD_PER_M = 0.02   # text-embedding-3-small

Embedder = Callable[[list[str]], Awaitable[list[list[float]]]]


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def registry_models() -> list[str]:
    from app.modules.chatbot.extraction.registry import REGISTRY

    return list(REGISTRY["product_models"])


def validate_rows(rows: Sequence[dict[str, Any]], models: Sequence[str]) -> list[str]:
    errors: list[str] = []
    if not rows:
        return ["file không có dòng nào"]
    docs = {(r.get("doc_id"), r.get("doc_version")) for r in rows}
    if len(docs) != 1:
        errors.append(f"một file phải là một tài liệu + một phiên bản, gặp {sorted(map(str, docs))}")
    for r in rows:
        key = r.get("chunk_key") or f"#{r.get('chunk_index')}"
        missing = [c for c in COLUMNS if c not in r]
        if missing:
            errors.append(f"{key}: thiếu cột {missing}")
            continue
        errors += [f"{key}: {c} rỗng" for c in REQUIRED if not r.get(c)]
        if r["chunk_role"] not in ROLES:
            errors.append(f"{key}: chunk_role lạ {r['chunk_role']}")
        if r["review_status"] not in STATUSES:
            errors.append(f"{key}: review_status lạ {r['review_status']}")
        if r["domain"] not in DOMAINS:
            errors.append(f"{key}: domain lạ {r['domain']}")
        if not set(r["scopes"]) <= set(SCOPES):
            errors.append(f"{key}: scopes ngoài {SCOPES}")
        if (r["domain"] == "technical_docs") != bool(r["scopes"]):
            errors.append(f"{key}: technical_docs phải có scopes (và chỉ technical_docs)")
        if r["domain"] == "technical_docs" and not r["product_models"]:
            errors.append(f"{key}: technical_docs phải có product_models")
        unknown = sorted((set(r["product_models"]) | set(r["applies_to_models"])) - set(models))
        if unknown:
            errors.append(f"{key}: model ngoài registry {unknown}")
        if r["chunk_role"] == "child" and not r.get("parent_key"):
            errors.append(f"{key}: chunk con không có parent_key")
    for column in ("chunk_key", "chunk_index"):
        dup = [v for v, n in Counter(r.get(column) for r in rows).items() if n > 1]
        if dup:
            errors.append(f"{column} trùng: {dup[:5]}")
    parents = {r.get("chunk_key") for r in rows if r.get("chunk_role") == "parent"}
    errors += [f"{r['chunk_key']}: parent_key {r['parent_key']} không phải chunk cha trong file"
               for r in rows if r.get("parent_key") and r["parent_key"] not in parents]
    return errors


def to_embed(rows: Sequence[dict[str, Any]], embed_parents: bool) -> list[int]:
    """Chỉ số dòng cần embedding: mọi chunk lá; chunk cha chỉ khi `embed_parents` (D-008: cha không cần)."""
    return [i for i, r in enumerate(rows) if r["chunk_role"] != "parent" or embed_parents]


def token_estimate(rows: Sequence[dict[str, Any]], indexes: Sequence[int]) -> int:
    return sum(rows[i].get("token_count") or len(rows[i]["embed_text"]) // 4 for i in indexes)


async def embed(rows: Sequence[dict[str, Any]], indexes: Sequence[int], embedder: Embedder,
                dimensions: int, batch: int = EMBED_BATCH) -> dict[int, list[float]]:
    vectors: dict[int, list[float]] = {}
    for start in range(0, len(indexes), batch):
        part = list(indexes[start:start + batch])
        result = await embedder([rows[i]["embed_text"] for i in part])
        if len(result) != len(part):
            raise RuntimeError(f"embedding trả {len(result)} vector cho {len(part)} văn bản")
        for i, vector in zip(part, result):
            if len(vector) != dimensions:
                raise RuntimeError(f"vector {len(vector)} chiều, bảng cần {dimensions}")
            vectors[i] = vector
    return vectors


def insert_order(rows: Sequence[dict[str, Any]]) -> tuple[list[int], list[int]]:
    """(chunk cha, phần còn lại) theo `chunk_index`: cha phải có `id` trước khi gán `parent_id` cho con."""
    order = sorted(range(len(rows)), key=lambda i: rows[i]["chunk_index"])
    return ([i for i in order if rows[i]["chunk_role"] == "parent"],
            [i for i in order if rows[i]["chunk_role"] != "parent"])


def _vector_literal(vector: list[float] | None) -> str | None:
    return None if vector is None else "[" + ",".join(repr(float(x)) for x in vector) + "]"


def row_params(row: dict[str, Any], parent_id: int | None, vector: list[float] | None,
               embedding_model: str) -> dict[str, Any]:
    params = {c: row[c] for c in COLUMNS}
    for c in JSON_COLUMNS:
        params[c] = json.dumps(row[c], ensure_ascii=False)
    params["parent_id"] = parent_id
    params["embedding"] = _vector_literal(vector)
    params["embedding_model"] = embedding_model if vector is not None else None
    return params


def insert_sql() -> str:
    def value(c: str) -> str:
        if c in ARRAY_COLUMNS:
            return f"cast(:{c} as text[])"
        if c in JSON_COLUMNS:
            return f"cast(:{c} as jsonb)"
        return f":{c}"
    columns = [*COLUMNS, "parent_id", "embedding", "embedding_model"]
    values = [*(value(c) for c in COLUMNS), ":parent_id", "cast(:embedding as vector)", ":embedding_model"]
    return f"insert into {TABLE} ({', '.join(columns)}) values ({', '.join(values)}) returning id"


async def apply_rows(session: Any, rows: Sequence[dict[str, Any]], vectors: dict[int, list[float]],
                     embedding_model: str) -> dict[str, int]:
    """Ghi trong transaction của `session` (người gọi commit/rollback). Trả số dòng xóa và insert."""
    from sqlalchemy import text

    doc_id, doc_version = rows[0]["doc_id"], rows[0]["doc_version"]
    deleted = await session.execute(
        text(f"delete from {TABLE} where doc_id = :d and doc_version = :v"), {"d": doc_id, "v": doc_version})
    parents, others = insert_order(rows)
    sql = text(insert_sql())
    ids: dict[str, int] = {}
    for i in parents:
        result = await session.execute(sql, row_params(rows[i], None, vectors.get(i), embedding_model))
        ids[rows[i]["chunk_key"]] = result.scalar_one()
    for i in others:
        parent = rows[i].get("parent_key")
        await session.execute(sql, row_params(rows[i], ids[parent] if parent else None, vectors.get(i),
                                              embedding_model))
    return {"deleted": deleted.rowcount or 0, "inserted": len(parents) + len(others)}


def summary(rows: Sequence[dict[str, Any]], indexes: Sequence[int]) -> list[str]:
    tokens = token_estimate(rows, indexes)
    first = rows[0]
    return [
        f"Tài liệu: {first['doc_id']} · phiên bản {first['doc_version']} · run {first.get('source_run')}",
        f"Dòng: {len(rows)} — vai trò {dict(sorted(Counter(r['chunk_role'] for r in rows).items()))}, "
        f"review_status {dict(sorted(Counter(r['review_status'] for r in rows).items()))}",
        f"Loại: {dict(Counter(r['chunk_type'] for r in rows).most_common())}",
        f"Có codes: {sum(1 for r in rows if r['codes'])}; có parent_key: {sum(1 for r in rows if r.get('parent_key'))}",
        f"Embed: {len(indexes)} dòng, ~{tokens:,} token ≈ {tokens * EMBED_USD_PER_M / 1e6:.4f} USD",
    ]


async def _with_session(work: Callable[[Any], Awaitable[Any]]) -> Any:
    from app.db.engine import AsyncSessionFactory, engine

    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                return await work(session)
    finally:
        await engine.dispose()


async def _count(session: Any, doc_id: str, doc_version: str | None) -> list[tuple]:
    from sqlalchemy import text

    result = await session.execute(text(
        f"select chunk_role, review_status, count(*), count(embedding), count(parent_id) from {TABLE} "
        "where doc_id = :d and (cast(:v as text) is null or doc_version = :v) group by 1, 2 order by 1, 2"),
        {"d": doc_id, "v": doc_version})
    return [tuple(r) for r in result.fetchall()]


async def run_apply(rows: list[dict[str, Any]], embed_parents: bool) -> None:
    from app.core.config import get_settings
    from app.modules.chatbot.providers.openai import OpenAIProvider

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("thiếu OPENAI_API_KEY")
    provider = OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model,
                              embedding_model=settings.embedding_model)
    indexes = to_embed(rows, embed_parents)
    vectors = await embed(rows, indexes, provider.embed, settings.embedding_dimensions)
    print(f"Đã embed {len(vectors)} dòng ({settings.embedding_model})", flush=True)

    async def work(session: Any) -> None:
        counts = await apply_rows(session, rows, vectors, settings.embedding_model)
        print(f"Xóa bản cũ: {counts['deleted']} dòng; insert: {counts['inserted']} dòng", flush=True)

    await _with_session(work)
    after = await _with_session(lambda s: _count(s, rows[0]["doc_id"], rows[0]["doc_version"]))
    print("Sau khi nạp (vai trò, trạng thái, dòng, có embedding, có parent_id):")
    for line in after:
        print(f"  {line}")


V1_VERSION = "v1-manual"
# Chép dòng của bảng cũ `doc_chunks` (chunk viết tay) sang v2: chunk độc lập, `source = manual`, giữ embedding
# (cùng text-embedding-3-small), `doc_version` = V1_VERSION, khóa `<doc_id>:M<chunk_index>`. Chạy lại không trùng.
COPY_V1_SQL = f"""
insert into {TABLE} (doc_id, doc_version, doc_title, doc_type, lang, chunk_key, chunk_index, chunk_role, chunk_type,
    domain, scopes, product_models, applies_to_models, control_interface, spec_attributes, section_id, section_path,
    section_title, page_start, page_end, content, summary_vi, keywords, codes, embed_text, embedding,
    embedding_model, token_count, content_hash, assets, metadata, source, review_status, is_active, source_run)
select c.doc_id, '{V1_VERSION}', coalesce(c.metadata->>'doc_title', c.section_title), c.doc_type, c.lang,
    c.doc_id || ':' || 'M' || lpad(c.chunk_index::text, 4, '0'), c.chunk_index, 'standalone', c.chunk_type,
    c.domain, c.scopes, c.product_models, '{{}}', c.control_interface, c.spec_attributes, c.section_id,
    c.section_path, c.section_title, c.page_start, c.page_end, c.content, c.summary_vi, c.keywords, '{{}}',
    c.embed_text, c.embedding, case when c.embedding is null then null else :embedding_model end, c.token_count,
    c.content_hash, c.assets, c.metadata || jsonb_build_object('copied_from', 'doc_chunks', 'v1_id', c.id),
    'manual', 'draft', c.is_active, 'doc_chunks(v1)'
from public.doc_chunks c
where c.embedding is not null
  and not exists (select 1 from {TABLE} v where v.doc_id = c.doc_id and v.doc_version = '{V1_VERSION}'
                  and v.chunk_index = c.chunk_index)
"""


async def run_copy_v1(embedding_model: str) -> None:
    from sqlalchemy import text

    async def work(session: Any) -> int:
        result = await session.execute(text(COPY_V1_SQL), {"embedding_model": embedding_model})
        return result.rowcount or 0

    print(f"Đã chép {await _with_session(work)} dòng từ doc_chunks sang doc_chunks_v2 (doc_version={V1_VERSION})")


async def run_delete(doc_id: str, doc_version: str | None) -> None:
    from sqlalchemy import text

    async def work(session: Any) -> int:
        result = await session.execute(text(
            f"delete from {TABLE} where doc_id = :d and (cast(:v as text) is null or doc_version = :v)"),
            {"d": doc_id, "v": doc_version})
        return result.rowcount or 0

    print(f"Đã xóa {await _with_session(work)} dòng của {doc_id}{f' / {doc_version}' if doc_version else ''}")


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="Nạp doc_chunks_v2.jsonl vào bảng doc_chunks_v2")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="chỉ kiểm và thống kê, không gọi API, không ghi DB")
    mode.add_argument("--apply", action="store_true", help="embed rồi ghi (thay bản cùng doc_id + doc_version)")
    mode.add_argument("--delete", action="store_true", help="xóa theo --doc-id [--doc-version]")
    mode.add_argument("--copy-v1", action="store_true",
                      help=f"chép chunk viết tay của bảng doc_chunks cũ sang v2 (source=manual, {V1_VERSION})")
    parser.add_argument("--rows", type=Path)
    parser.add_argument("--embed-parents", action="store_true", help="embed cả chunk cha (đo biến thể tìm cả cha)")
    parser.add_argument("--doc-id")
    parser.add_argument("--doc-version")
    args = parser.parse_args(argv)
    if sys.platform == "win32":   # psycopg async không chạy trên ProactorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if args.delete:
        if not args.doc_id:
            parser.error("--delete cần --doc-id")
        asyncio.run(run_delete(args.doc_id, args.doc_version))
        return 0
    if args.copy_v1:
        from app.core.config import get_settings

        asyncio.run(run_copy_v1(get_settings().embedding_model))
        return 0
    if args.rows is None:
        parser.error("--dry-run/--apply cần --rows")
    rows = read_rows(args.rows)
    errors = validate_rows(rows, registry_models())
    if errors:
        print(f"LỖI ({len(errors)}):")
        for e in errors[:30]:
            print(f"  - {e}")
        return 1
    print("\n".join(summary(rows, to_embed(rows, args.embed_parents))))
    if args.apply:
        asyncio.run(run_apply(rows, args.embed_parents))
    else:
        print("dry-run: không gọi API, không ghi DB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
