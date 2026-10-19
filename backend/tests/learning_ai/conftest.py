"""Fixture dùng chung cho test learning_ai: registry nhỏ, nguồn đã ẩn danh và factory record."""
from collections.abc import Callable

import pytest

from app.modules.learning_ai.extraction.validators import Role, SourceView
from app.modules.learning_ai.schemas.knowledge_record import KnowledgeRecord
from app.modules.learning_ai.schemas.registry import RegistrySnapshot
from tests.learning_ai.builders import RAW_REGISTRY, REGISTRY_VERSION, SOURCE_ID, param_record, procedure_record


@pytest.fixture
def reg() -> RegistrySnapshot:
    return RegistrySnapshot.from_dict(RAW_REGISTRY, REGISTRY_VERSION)


@pytest.fixture
def sources() -> dict[str, SourceView]:
    return {SOURCE_ID: SourceView(SOURCE_ID, {"m1": Role.CUSTOMER, "m2": Role.STAFF, "p1:b1": Role.DOCUMENT})}


@pytest.fixture
def make_param_record() -> Callable[..., KnowledgeRecord]:
    return param_record


@pytest.fixture
def make_procedure_record() -> Callable[..., KnowledgeRecord]:
    return procedure_record
