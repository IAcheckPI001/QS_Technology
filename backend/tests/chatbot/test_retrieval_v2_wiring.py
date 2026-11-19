"""D-009 bước 6: chat tra cứu trên doc_chunks_v2; coverage technical_docs nạp từ DB lúc khởi động. Không cần DB."""
from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any

import pytest

from app import main
from app.core.config import Settings
from app.modules.chatbot.extraction import validate_registry
from app.modules.chatbot.extraction.registry import REGISTRY, extend_technical_coverage
from app.modules.chatbot.repositories.doc_chunk_v2_repository import DocChunkV2Repository, MatchV2Options


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> list[dict[str, Any]]:
        return self._rows


class _Session:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows, self.calls = rows, []

    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def execute(self, sql: Any, params: dict[str, Any]) -> _Result:
        self.calls.append((str(sql), params))
        return _Result(self.rows)


@pytest.fixture
def coverage():
    """Khôi phục coverage của registry sau mỗi test (registry là biến module dùng chung)."""
    saved = copy.deepcopy(REGISTRY["coverage"])
    yield REGISTRY["coverage"]
    REGISTRY["coverage"].clear()
    REGISTRY["coverage"].update(saved)


def test_technical_docs_models_follows_approved_only() -> None:
    session = _Session([{"model": "F54"}, {"model": "F86"}])
    repo = DocChunkV2Repository(MatchV2Options(approved_only=True), session_factory=lambda: session)
    assert asyncio.run(repo.technical_docs_models()) == ["F54", "F86"]
    sql, params = session.calls[0]
    assert "from doc_chunks_v2" in sql and "domain = 'technical_docs'" in sql and "review_status" in sql
    assert params == {"approved_only": True}
    draft = DocChunkV2Repository(MatchV2Options(approved_only=False), session_factory=lambda: session)
    asyncio.run(draft.technical_docs_models())
    assert session.calls[1][1] == {"approved_only": False}


def test_extend_technical_coverage_adds_only_new_known_models(coverage) -> None:
    before_f86 = list(coverage["technical_docs"]["F86"])
    assert validate_registry._supported(["F54"], [{"domain": "technical_docs"}]) == ([], ["F54"])

    added = extend_technical_coverage(["F54", "F86", "XYZ"])

    assert added == ["F54"]                                              # model lạ bị bỏ, F86 đã có
    assert coverage["technical_docs"]["F54"] == REGISTRY["capabilities"]["control_interface"]["F54"]
    assert coverage["technical_docs"]["F86"] == before_f86               # không sửa model đã khai báo
    # Câu hướng dẫn F54 giờ được tra cứu thay vì `no_docs`.
    assert validate_registry._supported(["F54"], [{"domain": "technical_docs"}]) == (["F54"], [])
    assert extend_technical_coverage(["F54"]) == []                      # chạy lại không đổi gì


def test_build_doc_repository_uses_settings(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "retrieval_approved_only", False)
    repo = main.build_doc_repository()
    assert isinstance(repo, DocChunkV2Repository)
    assert repo.options == MatchV2Options(approved_only=False)          # các option khác: mặc định production
    monkeypatch.setattr(main.settings, "retrieval_approved_only", True)
    assert main.build_doc_repository().options.approved_only is True


def test_load_technical_coverage_extends_registry(coverage) -> None:
    session = _Session([{"model": "F54"}])
    repo = DocChunkV2Repository(MatchV2Options(approved_only=False), session_factory=lambda: session)
    assert asyncio.run(main.load_technical_coverage(repo)) == ["F54"]
    assert "F54" in coverage["technical_docs"]


def test_load_technical_coverage_db_error_keeps_static_registry(coverage, caplog) -> None:
    class _Broken:
        options = MatchV2Options()

        async def technical_docs_models(self) -> list[str]:
            raise OSError("db down")

    before = copy.deepcopy(coverage["technical_docs"])
    with caplog.at_level(logging.WARNING, logger="app.main"):
        assert asyncio.run(main.load_technical_coverage(_Broken())) == []    # type: ignore[arg-type]
    assert coverage["technical_docs"] == before
    assert "registry tĩnh" in caplog.text


def test_settings_retrieval_approved_only(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host/db")
    monkeypatch.delenv("RETRIEVAL_APPROVED_ONLY", raising=False)
    assert Settings(_env_file=None).retrieval_approved_only is True
    monkeypatch.setenv("RETRIEVAL_APPROVED_ONLY", "false")
    assert Settings(_env_file=None).retrieval_approved_only is False
