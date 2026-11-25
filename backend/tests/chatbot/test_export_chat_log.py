"""Ẩn danh và bỏ trùng của `scripts/export_chat_log.py`. Không cần DB."""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("export_chat_log", ROOT / "scripts" / "export_chat_log.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ex = _load()


def test_anonymize_replaces_pii() -> None:
    text, changed = ex.anonymize("Liên hệ a.b+c@gmail.com hoặc 0912 345 678, xem https://x.vn/a?b=1 mã 123456789012")
    assert changed and text == "Liên hệ <email> hoặc <sdt>, xem <url> mã <so>"
    assert ex.anonymize("+84 912345678 gọi giúp")[0] == "<sdt> gọi giúp"


def test_anonymize_keeps_technical_text() -> None:
    for q in ["tham số #12010 bước vít me 10 mm", "F54 kích thước 220x140x30", "đấu 0-10V vào CN1, M1920",
              "bộ 6AH hay 6AV, 4 trục, EtherCAT 1000 Hz"]:
        assert ex.anonymize(q) == (q, False)


def _rec(i: int, q: str, models=None, chunks=True) -> dict:
    return {"id": f"id-{i}", "query_origin": q, "normalized_query": f"nq {q}", "created_at": datetime(2026, 11, 25, 8, i),
            "channel": "website", "product_models": models or [], "has_chunks": chunks}


def test_make_rows_dedupes_and_hides_ids(tmp_path: Path) -> None:
    rows = ex.make_rows([_rec(1, "Kích thước F54?", ["F54"]), _rec(2, "  kích   thước f54? "), _rec(3, "Gọi 0912345678 nhé", chunks=False),
                         _rec(4, "   ")])
    assert [r["cau_hoi"] for r in rows] == ["Kích thước F54?", "Gọi <sdt> nhé"]
    assert rows[0]["model"] == "F54" and rows[0]["co_chunk"] == 1 and rows[0]["can_ra_soat"] == 0
    assert rows[1]["can_ra_soat"] == 1 and rows[1]["co_chunk"] == 0
    assert all("id-" not in str(v) for r in rows for v in r.values())
    path = tmp_path / "o.csv"
    ex.write_rows(path, rows)
    assert path.read_text(encoding="utf-8-sig").splitlines()[0] == ",".join(ex.COLUMNS)
