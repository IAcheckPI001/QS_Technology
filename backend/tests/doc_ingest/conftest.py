"""Test doc_ingest chạy được ở cả venv backend lẫn `.venv-ingest`.

Test cần Docling gắn `@pytest.mark.requires_docling` và tự skip khi venv không có Docling.
"""
import importlib.util

import pytest

HAS_DOCLING = importlib.util.find_spec("docling_core") is not None


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "requires_docling: cần venv ingest có Docling (.venv-ingest)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if HAS_DOCLING:
        return
    skip = pytest.mark.skip(reason="Docling chưa cài; chạy bằng .venv-ingest")
    for item in items:
        if "requires_docling" in item.keywords:
            item.add_marker(skip)
