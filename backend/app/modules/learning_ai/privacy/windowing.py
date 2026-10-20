"""Chia hội thoại dài thành cửa sổ cho model self-host có context nhỏ.

- Gom message NGUYÊN VẸN tới ngân sách token; chỉ message tự nó vượt ngân sách mới bị tách
  theo câu (mảnh giữ locator gốc và là chuỗi con của message → redactor vẫn kiểm được).
- Mỗi cửa sổ kèm vài message đứng trước làm ngữ cảnh (context_only, không báo cáo finding)
  để model nhận ra thực thể đã được giới thiệu ở trên.
- Token đếm bằng tiktoken × hệ số an toàn vì tokenizer của Qwen/Llama khác tiktoken.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from ..ingestion.source_document import SourceUnit

TOKEN_SAFETY_FACTOR = 1.5
CONTEXT_UNITS = 2
CONTEXT_MAX_CHARS = 400

_SENTENCE_END = re.compile(r"(?<=[.!?\n])\s+")


@dataclass(frozen=True)
class Window:
    targets: tuple[SourceUnit, ...]
    context: tuple[SourceUnit, ...]

    @property
    def target_locators(self) -> frozenset[str]:
        return frozenset(u.locator for u in self.targets)


def _split_oversized(unit: SourceUnit, budget: int, cost: Callable[[str], int]) -> list[SourceUnit]:
    """Tách theo offset để mỗi mảnh luôn là chuỗi con nguyên văn của message."""
    text = unit.text
    bounds = [0, *(m.end() for m in _SENTENCE_END.finditer(text)), len(text)]
    spans: list[tuple[int, int]] = []
    for start, end in zip(bounds, bounds[1:]):
        c = cost(text[start:end])
        if c <= budget:
            spans.append((start, end))
            continue
        size = max(1, (end - start) * budget // c)                 # câu quá dài: cắt theo ký tự
        spans += [(i, min(i + size, end)) for i in range(start, end, size)]

    packed: list[tuple[int, int]] = []
    for start, end in spans:
        if packed and cost(text[packed[-1][0]:end]) <= budget:
            packed[-1] = (packed[-1][0], end)
        else:
            packed.append((start, end))
    return [unit.model_copy(update={"text": text[s:e]}) for s, e in packed if text[s:e].strip()]


def build_windows(units: list[SourceUnit], budget_tokens: int,
                  count_tokens: Callable[[str], int]) -> list[Window]:
    if budget_tokens <= 0:
        raise ValueError("budget_tokens must be positive")

    def cost(text: str) -> int:
        return int(count_tokens(text) * TOKEN_SAFETY_FACTOR) + 1

    pieces: list[tuple[int, SourceUnit]] = []          # (vị trí unit gốc, mảnh)
    for i, unit in enumerate(units):
        parts = [unit] if cost(unit.text) <= budget_tokens else _split_oversized(unit, budget_tokens, cost)
        pieces += [(i, p) for p in parts]

    groups: list[list[tuple[int, SourceUnit]]] = []
    used = 0
    for item in pieces:
        c = cost(item[1].text)
        if groups and used + c <= budget_tokens:
            groups[-1].append(item)
            used += c
        else:
            groups.append([item])
            used = c

    windows = []
    for group in groups:
        first = group[0][0]
        context = tuple(u.model_copy(update={"text": u.text[-CONTEXT_MAX_CHARS:]})
                        for u in units[max(0, first - CONTEXT_UNITS):first])
        windows.append(Window(targets=tuple(p for _, p in group), context=context))
    return windows
