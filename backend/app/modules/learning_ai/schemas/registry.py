"""Snapshot registry dùng chung giữa luồng truy vấn (query extraction) và luồng học tri thức.

Nguyên tắc: KnowledgeRecord chỉ lưu MÃ chuẩn hóa. Alias/từ đồng nghĩa nằm ở registry và chỉ
được dùng khi sinh dữ liệu dẫn xuất (embedding_text, keyword expansion).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

# field trong KnowledgeRecord  ->  key trong registry R
FIELD_TO_REGISTRY_KEY: dict[str, str] = {
    # tái sử dụng từ registry hiện tại
    "intents": "intents",
    "product_models": "product_models",
    "excluded_models": "product_models",
    "control_interface": "control_interface",
    "spec_attributes": "spec_attributes",
    # bổ sung mới
    "topic": "topics",
    "connector_ids": "connectors",
    "parameter_ids": "parameters",
    "parameter_id": "parameters",
    "from_connector": "connectors",
    "alarm_codes": "alarm_codes",
}


@dataclass(frozen=True)
class RegistrySnapshot:
    version: str
    codes: Mapping[str, frozenset[str]]
    aliases: Mapping[str, Mapping[str, tuple[str, ...]]] = field(default_factory=dict)
    model_families: Mapping[str, frozenset[str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Mapping, version: str) -> "RegistrySnapshot":
        """raw: {"intents": [...], "product_models": [...], ...,
                 "_aliases": {"parameters": {"P01": ["Pr.01", "tham số 01"]}},
                 "_model_families": {"F-series": ["F86", "F54"]}}"""
        codes = {k: frozenset(v) for k, v in raw.items() if not k.startswith("_")}
        aliases = {k: {c: tuple(a) for c, a in m.items()} for k, m in raw.get("_aliases", {}).items()}
        families = {k: frozenset(v) for k, v in raw.get("_model_families", {}).items()}
        return cls(version=version, codes=codes, aliases=aliases, model_families=families)

    def allowed(self, record_field: str) -> frozenset[str]:
        return self.codes.get(FIELD_TO_REGISTRY_KEY[record_field], frozenset())

    def unknown(self, record_field: str, values: Iterable[str]) -> list[str]:
        allowed = self.allowed(record_field)
        return [v for v in values if v not in allowed]

    def aliases_of(self, record_field: str, code: str) -> tuple[str, ...]:
        return self.aliases.get(FIELD_TO_REGISTRY_KEY[record_field], {}).get(code, ())

    def models_of_family(self, family: str) -> frozenset[str]:
        return self.model_families.get(family, frozenset())
