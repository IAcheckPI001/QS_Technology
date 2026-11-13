"""Loader `chunking_loader/load_ingest_run.py` (D-009): kiểm dòng, chọn dòng embed, thứ tự insert, gán `parent_id`,
tham số SQL. Session và embedder giả — không cần DB hay API."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.modules.chunking_loader import load_ingest_run as L

MODELS = ["F54", "F86"]


def _row(key: str, index: int, role: str, parent: str | None = None, **over: Any) -> dict[str, Any]:
    row = {
        "parent_key": parent, "doc_id": "d", "doc_version": "v1", "doc_title": "Doc", "doc_type": "user_guide",
        "lang": "en", "chunk_key": key, "chunk_index": index, "chunk_role": role, "chunk_type": "procedure",
        "domain": "technical_docs", "scopes": ["operation"], "product_models": ["F54"], "applies_to_models": [],
        "control_interface": [], "spec_attributes": [], "section_id": None, "section_path": ["1 A"],
        "section_title": "A", "page_start": 1, "page_end": 1, "printed_page_start": 1, "printed_page_end": 1,
        "content": f"content {key}", "summary_vi": None, "keywords": [], "codes": ["X41"],
        "embed_text": f"embed {key}", "token_count": 10, "content_hash": f"h{index}", "assets": [],
        "metadata": {"faq_vi": ["câu hỏi?"]}, "source": "builder", "review_status": "draft", "is_active": True,
        "source_run": "d/eval-a",
    }
    row.update(over)
    return row


def _rows() -> list[dict[str, Any]]:
    return [_row("d:B0002", 2, "child", "d:B0000"), _row("d:B0000", 0, "parent"),
            _row("d:B0001", 1, "child", "d:B0000"), _row("d:B0003", 3, "standalone")]


def test_validate_ok_and_errors() -> None:
    assert L.validate_rows(_rows(), MODELS) == []
    bad = _rows()
    bad[0] = dict(bad[0], parent_key="d:B0404")                       # cha không có trong file
    bad[2] = dict(bad[2], parent_key=None)                            # con không có cha
    bad[3] = dict(bad[3], product_models=["ASTRO_6AH"], review_status="ok")
    bad.append(_row("d:B0003", 9, "standalone", doc_version="v2"))    # khóa trùng + 2 phiên bản
    errors = L.validate_rows(bad, MODELS)
    text = "\n".join(errors)
    for expected in ("không phải chunk cha", "chunk con không có parent_key", "model ngoài registry ['ASTRO_6AH']",
                     "review_status lạ", "chunk_key trùng", "một tài liệu + một phiên bản"):
        assert expected in text, expected
    assert L.validate_rows([], MODELS) == ["file không có dòng nào"]
    missing = {k: v for k, v in _row("d:B9", 9, "standalone").items() if k != "codes"}
    assert any("thiếu cột ['codes']" in e for e in L.validate_rows([missing], MODELS))


def test_to_embed_skips_parents_unless_flag() -> None:
    rows = _rows()
    assert L.to_embed(rows, False) == [0, 2, 3]
    assert L.to_embed(rows, True) == [0, 1, 2, 3]


def test_embed_batches_and_checks_dimensions() -> None:
    rows = _rows()
    calls: list[list[str]] = []

    async def embedder(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return [[0.5, 0.5] for _ in texts]

    vectors = asyncio.run(L.embed(rows, [0, 2, 3], embedder, dimensions=2, batch=2))
    assert [len(c) for c in calls] == [2, 1] and calls[0] == ["embed d:B0002", "embed d:B0001"]
    assert set(vectors) == {0, 2, 3}

    async def wrong_dims(texts: list[str]) -> list[list[float]]:
        return [[0.1] for _ in texts]

    try:
        asyncio.run(L.embed(rows, [0], wrong_dims, dimensions=2))
    except RuntimeError as exc:
        assert "1 chiều" in str(exc)
    else:
        raise AssertionError("phải báo sai số chiều")


class _Result:
    def __init__(self, value: int | None = None, rowcount: int = 0) -> None:
        self._value, self.rowcount = value, rowcount

    def scalar_one(self) -> int:
        assert self._value is not None
        return self._value


class _Session:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.next_id = 100

    async def execute(self, sql: Any, params: dict[str, Any]) -> _Result:
        self.calls.append((str(sql), params))
        if str(sql).startswith("delete"):
            return _Result(rowcount=7)
        self.next_id += 1
        return _Result(self.next_id)


def test_apply_rows_inserts_parents_first_and_links_children() -> None:
    rows = _rows()
    session = _Session()
    vectors = {0: [0.1, 0.2], 2: [0.3, 0.4], 3: [0.5, 0.6]}
    counts = asyncio.run(L.apply_rows(session, rows, vectors, "text-embedding-3-small"))
    assert counts == {"deleted": 7, "inserted": 4}
    sql0, params0 = session.calls[0]
    assert sql0.startswith("delete from public.doc_chunks_v2") and params0 == {"d": "d", "v": "v1"}
    inserted = [p for _, p in session.calls[1:]]
    assert [p["chunk_key"] for p in inserted] == ["d:B0000", "d:B0001", "d:B0002", "d:B0003"]
    parent, child1, child2, alone = inserted
    assert parent["parent_id"] is None and parent["embedding"] is None and parent["embedding_model"] is None
    assert child1["parent_id"] == 101 and child2["parent_id"] == 101 and alone["parent_id"] is None
    assert child1["embedding"] == "[0.3,0.4]" and child1["embedding_model"] == "text-embedding-3-small"
    assert json.loads(child1["metadata"]) == {"faq_vi": ["câu hỏi?"]} and child1["assets"] == "[]"
    assert child1["codes"] == ["X41"]


def test_insert_sql_casts_columns() -> None:
    sql = L.insert_sql()
    assert "cast(:codes as text[])" in sql and "cast(:metadata as jsonb)" in sql
    assert "cast(:embedding as vector)" in sql and sql.endswith("returning id")
    assert sql.count(":") == len(L.COLUMNS) + 3


def test_copy_v1_sql_is_idempotent_and_manual() -> None:
    sql = L.COPY_V1_SQL
    assert "from public.doc_chunks c" in sql and "insert into public.doc_chunks_v2" in sql
    assert "'manual', 'draft'" in sql and "'standalone'" in sql and "not exists" in sql
    assert f"'{L.V1_VERSION}'" in sql and ":embedding_model" in sql and "'{}'" in sql


def test_main_dry_run_does_not_touch_db(tmp_path: Path, capsys) -> None:
    path = tmp_path / "doc_chunks_v2.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in _rows()), encoding="utf-8")
    assert L.main(["--dry-run", "--rows", str(path)]) == 0
    out = capsys.readouterr().out
    assert "Dòng: 4" in out and "Embed: 3 dòng" in out and "dry-run" in out
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps(_row("d:B0", 0, "child")) + "\n", encoding="utf-8")
    assert L.main(["--dry-run", "--rows", str(bad)]) == 1
