from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd
import os, sys
import asyncio
import selectors
from sqlalchemy import text

from app.db.engine import AsyncSessionFactory

ALLOWED_DOMAINS = {
    "technical_docs",
    "company_info",
    "product_catalog",
}

ALLOWED_SCOPES = {
    "installation",
    "operation",
    "configuration",
    "maintenance",
}

ALLOWED_MODELS = {
    "F54",
    "F86",
    "F10T",
    "ASTRO_10S",
    "ASTRO_6AH",
    "ASTRO_6AV",
    "ASTRO_10I",
}

REQUIRED_COLUMNS = {
    "domain",
    "scopes",
    "product_models",
    "control_interface",
    "spec_attributes",
    "chunk_type",
    "is_active",
    "doc_id",
    "doc_type",
    "lang",
    "section_id",
    "section_path",
    "section_title",
    "page_start",
    "page_end",
    "chunk_index",
    "assets",
    "metadata",
    "content",
    "summary_vi",
    "keywords",
    "embed_text",
    "content_hash",
}


def parse_pg_array(value: str) -> list[str]:
    """Chuyển chuỗi mảng PostgreSQL, ví dụ {installation}, thành list."""
    value = value.strip()

    if value in {"", "{}"}:
        return []

    if not (value.startswith("{") and value.endswith("}")):
        raise ValueError(f"Giá trị không đúng định dạng mảng: {value!r}")

    inner = value[1:-1]

    if not inner.strip():
        return []

    return next(
        csv.reader(
            [inner],
            delimiter=",",
            quotechar='"',
            escapechar="\\",
            skipinitialspace=True,
        )
    )


def parse_json(value: str, default: Any) -> Any:
    """Đọc JSON; chỉ dùng default khi trường thực sự rỗng."""
    if not value.strip():
        return default

    return json.loads(value)


def parse_optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def parse_bool(value: str) -> bool:
    value = value.strip().lower()

    if value in {"true", "1", "yes"}:
        return True

    if value in {"false", "0", "no"}:
        return False

    raise ValueError(f"Giá trị boolean không hợp lệ: {value!r}")


def validate_chunk(chunk: dict[str, Any], row_number: int) -> None:
    """Kiểm tra các ràng buộc quan trọng trước khi insert."""
    prefix = f"Dòng CSV {row_number}"

    if chunk["domain"] not in ALLOWED_DOMAINS:
        raise ValueError(
            f"{prefix}: domain không hợp lệ: {chunk['domain']!r}"
        )

    if not set(chunk["scopes"]).issubset(ALLOWED_SCOPES):
        raise ValueError(f"{prefix}: scopes không hợp lệ")

    if not set(chunk["product_models"]).issubset(ALLOWED_MODELS):
        raise ValueError(f"{prefix}: product_models không hợp lệ")

    if chunk["domain"] == "technical_docs":
        if not chunk["scopes"]:
            raise ValueError(f"{prefix}: technical_docs thiếu scopes")

        if not chunk["product_models"]:
            raise ValueError(f"{prefix}: technical_docs thiếu product_models")

    for field in (
        "chunk_type",
        "doc_id",
        "doc_type",
        "section_title",
        "content",
        "embed_text",
        "content_hash",
    ):
        if not chunk[field]:
            raise ValueError(f"{prefix}: trường {field} bị rỗng")

    if not isinstance(chunk["assets"], list):
        raise ValueError(f"{prefix}: assets phải là JSON array")

    if not isinstance(chunk["metadata"], dict):
        raise ValueError(f"{prefix}: metadata phải là JSON object")


def load_csv_chunks(file_name: str) -> list[dict[str, Any]]:
    """Load CSV thành danh sách chunk, mỗi phần tử tương ứng một dòng."""
    csv_path = Path(__file__).resolve().parent / file_name

    if not csv_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file: {csv_path}")

    df = pd.read_csv(
        csv_path,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(f"CSV thiếu các cột: {sorted(missing)}")

    chunks: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int]] = set()

    for index, row in df.iterrows():
        row_number = int(index) + 2  # Tính cả dòng header

        try:
            chunk: dict[str, Any] = {
                # Không có trong CSV
                "parent_id": None,

                # Metadata và nội dung
                "domain": row["domain"].strip(),
                "scopes": parse_pg_array(row["scopes"]),
                "product_models": parse_pg_array(row["product_models"]),
                "control_interface": parse_pg_array(
                    row["control_interface"]
                ),
                "spec_attributes": parse_pg_array(
                    row["spec_attributes"]
                ),
                "chunk_type": row["chunk_type"].strip(),
                "is_active": parse_bool(row["is_active"]),
                "doc_id": row["doc_id"].strip(),
                "doc_type": row["doc_type"].strip(),
                "lang": row["lang"].strip() or "en",
                "section_id": row["section_id"].strip() or None,
                "section_path": parse_pg_array(row["section_path"]),
                "section_title": row["section_title"].strip(),
                "page_start": parse_optional_int(row["page_start"]),
                "page_end": parse_optional_int(row["page_end"]),
                "chunk_index": int(row["chunk_index"]),
                "assets": parse_json(row["assets"], []),
                "metadata": parse_json(row["metadata"], {}),
                "content": row["content"],
                "summary_vi": row["summary_vi"].strip() or None,
                "keywords": parse_pg_array(row["keywords"]),
                "embed_text": row["embed_text"],
                "content_hash": row["content_hash"].strip(),

                # Không có trong CSV, nhưng cho phép NULL theo schema
                "token_count": None,
            }

            validate_chunk(chunk, row_number)

            unique_key = (chunk["doc_id"], chunk["chunk_index"])

            if unique_key in seen_keys:
                raise ValueError(
                    f"Trùng doc_id và chunk_index: {unique_key}"
                )

            seen_keys.add(unique_key)
            chunks.append(chunk)

        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Lỗi xử lý {csv_path.name}, dòng {row_number}: {exc}"
            ) from exc

    return chunks


INSERT_CHUNK_SQL = text("""
    INSERT INTO public.doc_chunks (
        parent_id,
        domain,
        scopes,
        product_models,
        control_interface,
        spec_attributes,
        chunk_type,
        is_active,
        doc_id,
        doc_type,
        lang,
        section_id,
        section_path,
        section_title,
        page_start,
        page_end,
        chunk_index,
        assets,
        metadata,
        content,
        summary_vi,
        keywords,
        embed_text,
        content_hash
    )
    VALUES (
        :parent_id,
        :domain,
        CAST(:scopes AS text[]),
        CAST(:product_models AS text[]),
        CAST(:control_interface AS text[]),
        CAST(:spec_attributes AS text[]),
        :chunk_type,
        :is_active,
        :doc_id,
        :doc_type,
        :lang,
        :section_id,
        CAST(:section_path AS text[]),
        :section_title,
        :page_start,
        :page_end,
        :chunk_index,
        CAST(:assets AS jsonb),
        CAST(:metadata AS jsonb),
        :content,
        :summary_vi,
        CAST(:keywords AS text[]),
        :embed_text,
        :content_hash
    )
    ON CONFLICT (doc_id, chunk_index) DO NOTHING
""")


async def insert_chunks(
    chunks: list[dict[str, Any]],
    batch_size: int = 50,
) -> int:
    """Insert các chunk chưa có embedding vào PostgreSQL."""

    total = len(chunks)
    inserted_total = 0

    for start in range(0, total, batch_size):
        batch = chunks[start : start + batch_size]

        payload = []

        for chunk in batch:
            row = chunk.copy()

            # SQL CAST(... AS jsonb) cần JSON dạng chuỗi.
            row["assets"] = json.dumps(
                chunk["assets"], ensure_ascii=False
            )
            row["metadata"] = json.dumps(
                chunk["metadata"], ensure_ascii=False
            )

            payload.append(row)

        # Mỗi batch có transaction riêng.
        async with AsyncSessionFactory() as session:
            async with session.begin():
                result = await session.execute(
                    INSERT_CHUNK_SQL,
                    payload,
                )

                affected = result.rowcount
                if affected is None or affected < 0:
                    raise RuntimeError(
                        "Không xác định được số bản ghi đã insert."
                    )

                inserted_total += affected

        print(
            f"Đã insert {inserted_total} bản ghi mới "
            f"(đã xử lý {min(start + len(batch), total)}/{total})",
            flush=True,
        )

    return inserted_total


async def main() -> None:
    chunks = load_csv_chunks("documents/doc_chunks_f86.csv")

    print(f"Tổng số chunk hợp lệ: {len(chunks)}")

    if not chunks:
        return

    inserted = await insert_chunks(chunks, batch_size=50)

    print(f"Hoàn tất. Số chunk mới được insert: {inserted}")


if __name__ == "__main__":
    try:
        asyncio.run(
            main(),
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector()
            ),
        )
    except Exception as exc:
        print(f"Lỗi ingestion: {exc}")
        sys.exit(1)