"""Phiên bản prompt phân tích: khung prompt (`PROMPT_VERSION`) và mô tả intent (`INTENT_DESC_VERSION`).

Dấu nội dung của từng phiên bản được ghim ở đây. Test đỏ nghĩa là nội dung đã đổi mà chưa tăng phiên bản:
- sửa câu chữ khung prompt, ví dụ mẫu, hoặc bảng gợi ý thực thể (control_interface, spec_attributes, handoff_reasons)
  → thêm khung mới vào `_FRAMES`, tăng `PROMPT_VERSION`, thêm dấu vào `FRAME_SHA`;
- sửa `desc` của intent → tăng `INTENT_DESC_VERSION` (bản thử nghiệm: `INTENT_DESC_VARIANTS`), thêm dấu vào
  `INTENT_DESC_SHA`.
Danh sách model của registry không thuộc phiên bản nào (không làm đổi hai dấu này).
"""

import hashlib

import pytest

from app.modules.chatbot.analysis.analyzer import QueryAnalyzer
from app.modules.chatbot.analysis.prompt import prompt_builder
from app.modules.chatbot.analysis.prompt.prompt_builder import (
    PROMPT_VERSION, analysis_prompt_info, build_analysis_prompt,
)
from app.modules.chatbot.analysis.prompt.registry_render import _render_intents
from app.modules.chatbot.extraction import registry
from app.modules.chatbot.extraction.registry import (
    INTENT_DESC_VERSION, REGISTRY, RegistryError, intent_descriptions,
)

FRAME_SHA = {"v1": "9b0f93a482f1"}
INTENT_DESC_SHA = {"v1": "3520bd6b00ae"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def test_every_frame_version_is_pinned():
    assert PROMPT_VERSION in prompt_builder._FRAMES
    assert set(prompt_builder._FRAMES) == set(FRAME_SHA)
    for version, frame in prompt_builder._FRAMES.items():
        assert _sha(frame(None, "{intents}", "{models}")) == FRAME_SHA[version], (
            f"khung prompt {version} đã đổi nội dung: tăng PROMPT_VERSION thay vì sửa tại chỗ")


def test_every_intent_desc_version_is_pinned():
    versions = {INTENT_DESC_VERSION, *registry.INTENT_DESC_VARIANTS}
    assert versions == set(INTENT_DESC_SHA)
    for version in versions:
        assert _sha(_render_intents(version)) == INTENT_DESC_SHA[version], (
            f"mô tả intent {version} đã đổi nội dung: tăng INTENT_DESC_VERSION thay vì sửa tại chỗ")


def test_default_prompt_uses_production_versions():
    assert build_analysis_prompt(4) == build_analysis_prompt(
        4, version=PROMPT_VERSION, intent_desc_version=INTENT_DESC_VERSION)
    info = analysis_prompt_info(4)
    assert info == {"prompt_version": PROMPT_VERSION, "intent_desc_version": INTENT_DESC_VERSION, "n_examples": 4,
                    "sha256": _sha(build_analysis_prompt(4))}
    assert QueryAnalyzer(provider=None, n_examples=4).prompt_info == info


def test_intent_desc_variant_overrides_only_listed_intents(monkeypatch):
    monkeypatch.setitem(registry.INTENT_DESC_VARIANTS, "thu", {"guide.configuration": "MÔ TẢ THỬ NGHIỆM"})
    base, variant = intent_descriptions(), intent_descriptions("thu")
    assert variant["guide.configuration"] == "MÔ TẢ THỬ NGHIỆM"
    assert {k: v for k, v in variant.items() if k != "guide.configuration"} == {
        k: v for k, v in base.items() if k != "guide.configuration"}
    assert list(variant) == list(REGISTRY["intents"])

    prompt = build_analysis_prompt(4, intent_desc_version="thu")
    assert "- guide.configuration: MÔ TẢ THỬ NGHIỆM" in prompt
    assert REGISTRY["intents"]["guide.configuration"]["desc"] not in prompt
    info = QueryAnalyzer(provider=None, n_examples=4, intent_desc_version="thu").prompt_info
    assert info["intent_desc_version"] == "thu" and info["sha256"] != analysis_prompt_info(4)["sha256"]


def test_unknown_versions_are_rejected(monkeypatch):
    with pytest.raises(ValueError):
        build_analysis_prompt(4, version="v999")
    with pytest.raises(RegistryError):
        build_analysis_prompt(4, intent_desc_version="v999")
    monkeypatch.setitem(registry.INTENT_DESC_VARIANTS, "sai", {"guide.khong_co": "x"})
    with pytest.raises(RegistryError):
        intent_descriptions("sai")
