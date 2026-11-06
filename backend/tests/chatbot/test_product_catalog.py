import copy

import pytest

from app.modules.chatbot.extraction.product_catalog import RegistryProductCatalog
from app.modules.chatbot.extraction.registry import REGISTRY, RegistryError
from app.modules.chatbot.extraction.validate_registry import (
    models_in_text,
    models_with_interfaces,
    resolve_models,
    resolve_sub_query,
    validate_registry,
)
from tests.chatbot.agent_fakes import sub_query

ETHERCAT = ["F86", "F86E", "F10T", "6AH", "6AHE", "6AV", "6AVE", "10iV", "10iVE"]
ASTRO_MECHATROLINK = ["6AH", "6AHE", "6AV", "6AVE", "10iV", "10iVE"]


@pytest.mark.parametrize(("required", "excluded", "match", "expected"), [
    (["ethercat"], [], "all", ETHERCAT),
    (["ethercat", "mechatrolink"], [], "all", ASTRO_MECHATROLINK),
    (["ethercat", "mechatrolink"], [], "any", ETHERCAT),
    (["pulse_train"], [], "all", REGISTRY["product_models"]),
    (["ethercat"], ["mechatrolink"], "all", ["F86", "F86E", "F10T"]),
    (["mechatrolink"], ["ethercat"], "all", []),
    ([], ["ethercat"], "all", ["F54"]),
])
def test_models_with_interfaces(required, excluded, match, expected):
    assert models_with_interfaces(required, excluded, match) == expected


def test_catalog_models_carry_names_and_documentation_coverage():
    models = {model.code: model for model in RegistryProductCatalog().find_by_interfaces(
        ["ethercat"], [], "all",
    )}

    assert list(models) == ETHERCAT
    assert models["F86"].name == "F86" and models["F86"].has_technical_docs
    assert models["F86"].documented_interfaces == ["pulse_train", "ethercat"]
    assert models["6AV"].name == "Astro 6AV"
    assert models["6AVE"].name == "6AVE"           # chưa có alias chính thức: hiển thị bằng mã
    assert not models["6AV"].has_technical_docs
    assert models["6AV"].documented_interfaces == []


@pytest.mark.parametrize(("text", "expected"), [
    ("F86 hỗ trợ EtherCAT, Astro 6AV có Mechatrolink", ["F86", "6AV"]),
    ("dòng 10iV và 10iVE", ["10iV", "10iVE"]),
    ("F86E khác gì 6AHE", ["F86E", "6AHE"]),   # mã ngắn không khớp bên trong mã dài
    ("mã cũ ASTRO_6AH", ["6AH"]),
    ("Astro 6A có 6 trục", []),          # alias mơ hồ không chỉ ra model nào
    ("dòng astro-10i và 10S", []),       # 10i mơ hồ, 10S không có trong danh mục
    ("Không nhắc model", []),
])
def test_models_in_text(text, expected):
    assert models_in_text(text) == expected


@pytest.mark.parametrize(("names", "expected"), [
    (["Astro 6AH", "ASTRO_6AV", "10iv"], (["6AH", "6AV", "10iV"], [], [])),
    (["10i", "Astro 10i"], ([], ["10i", "Astro 10i"], [])),
    (["10S", "ASTRO_10S"], ([], [], ["10S", "ASTRO_10S"])),
])
def test_resolve_models_uses_crm_codes(names, expected):
    assert resolve_models(names) == expected


def _broken_registry(monkeypatch, table):
    capabilities = copy.deepcopy(REGISTRY["capabilities"])
    capabilities["control_interface"] = table
    monkeypatch.setitem(REGISTRY, "capabilities", capabilities)


def test_registry_requires_every_model_in_capabilities(monkeypatch):
    table = dict(REGISTRY["capabilities"]["control_interface"])
    table.pop("F54")
    _broken_registry(monkeypatch, table)

    with pytest.raises(RegistryError, match="đúng mọi model"):
        validate_registry()


def test_registry_rejects_unknown_capability_interface(monkeypatch):
    table = {**REGISTRY["capabilities"]["control_interface"], "F86": ["ethercat", "profinet"]}
    _broken_registry(monkeypatch, table)

    with pytest.raises(RegistryError, match="F86 interface lạ"):
        validate_registry()


def test_resolved_sub_query_keeps_catalog_conditions():
    resolved = resolve_sub_query(sub_query(
        "Model hỗ trợ EtherCAT hoặc Mechatrolink, có 6 trục", "lookup.product_catalog",
        ci=["ethercat", "mechatrolink", "ethercat"], match="any", unmapped=[" 6 trục ", ""],
        dependency="general",
    ))

    entities = resolved["entities"]
    assert entities["control_interface"] == ["ethercat", "mechatrolink"]
    assert entities["interface_match"] == "any"
    assert entities["unmapped_conditions"] == ["6 trục"]
    assert resolved["route"] == "retrieve"


def test_interface_both_required_and_excluded_is_unclear():
    resolved = resolve_sub_query(sub_query(
        "Model hỗ trợ EtherCAT nhưng không hỗ trợ EtherCAT", "lookup.product_catalog",
        ci=["ethercat"], excluded=["ethercat"], dependency="general",
    ))

    assert resolved["route"] == "clarify"
    assert resolved["clarification"]["reason"] == "unclear_query"
    assert resolved["warnings"] == ["conflicting_interface_conditions"]
