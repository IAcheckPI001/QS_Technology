"""SourceDocument: hội thoại nguồn dưới dạng danh sách message có locator ổn định.

Locator `m1..mN` do hệ thống gán theo thứ tự lượt (created_at, id), customer trước staff
trong cùng một lượt; message rỗng bị bỏ. Validator dùng locator này để bắt LLM bịa
vị trí trích dẫn. Chỉ render cho LLM sau khi document đã qua bước privacy.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable
from typing import Protocol
from uuid import UUID, uuid5

from ..extraction.validators import Role, SourceView
from ..schemas.common import StrictModel

SOURCE_NAMESPACE = uuid5(UUID(int=0), "qs-technology:learning_ai:source_document")


class SupportChatRow(Protocol):
    message_no: int
    sender_role: str
    message_text: str


class SourceUnit(StrictModel):
    locator: str
    role: Role
    text: str


class SourceDocument(StrictModel):
    source_id: str
    session_id: UUID
    units: list[SourceUnit]
    content_hash: str

    def to_source_view(self, segment_locators: frozenset[str] = frozenset()) -> SourceView:
        return SourceView(source_id=self.source_id, units={u.locator: u.role for u in self.units},
                          segment_locators=segment_locators)

    def render_for_llm(self) -> str:
        return "\n".join(f"[{u.locator}][{u.role.value}] {u.text}" for u in self.units)

    def with_texts(self, texts: dict[str, str]) -> SourceDocument:
        """Bản sao với text đã thay theo locator (dùng cho redaction); identity giữ nguyên."""
        units = [u.model_copy(update={"text": texts.get(u.locator, u.text)}) for u in self.units]
        return self.model_copy(update={"units": units})


def _normalize(text: str | None) -> str:
    return unicodedata.normalize("NFC", text or "").strip()


def build_source_document(session_id: UUID, rows: Iterable[SupportChatRow]) -> SourceDocument:
    pairs: list[tuple[Role, str]] = []
    for row in rows:
        if hasattr(row, "message_text"):
            role = Role.CUSTOMER if row.sender_role == "user" else Role.STAFF
            messages = ((role, row.message_text),)
        else:
            messages = (
                (Role.CUSTOMER, getattr(row, "user_message", None)),
                (Role.STAFF, getattr(row, "staff_message", None)),
            )
        for role, text in messages:
            normalized = _normalize(text)
            if normalized:
                pairs.append((role, normalized))

    units = [SourceUnit(locator=f"m{i}", role=role, text=text) for i, (role, text) in enumerate(pairs, start=1)]
    raw = json.dumps([[r.value, t] for r, t in pairs], ensure_ascii=False, separators=(",", ":"))
    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return SourceDocument(
        source_id=str(uuid5(SOURCE_NAMESPACE, f"{session_id}:{content_hash}")),
        session_id=session_id,
        units=units,
        content_hash=content_hash,
    )
