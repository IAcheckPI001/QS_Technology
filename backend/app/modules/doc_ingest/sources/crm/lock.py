"""Sổ nguồn `crm_sources.lock.json`: tài liệu CRM nào đã được đưa vào kho tri thức, tới phiên bản nào.

Commit cùng repo (chung cho team). Không chứa URL đã ký. Ghi có thứ tự ổn định để diff git dễ đọc.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

State = Literal["fetched", "processed", "loaded_draft", "approved", "removed"]


class LockEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crm_id: str
    doc_id: str
    name: str
    branch: str
    mode: Literal["build", "run_only"]
    model: str | None = None
    document_type: str | None = None
    language: str | None = None
    connection_types: list[str] = Field(default_factory=list)
    version: str
    file_id: str
    file_size: int | None = None
    sha256: str
    state: State
    pdf_path: str                       # tương đối với gốc repo
    manifest: str | None = None         # tương đối với gốc repo; run_only: None
    synced_at: str                      # YYYY-MM-DD


class SourceLock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    documents: list[LockEntry] = Field(default_factory=list)

    def by_crm_id(self) -> dict[str, LockEntry]:
        return {e.crm_id: e for e in self.documents}

    def upsert(self, entry: LockEntry) -> None:
        self.documents = [e for e in self.documents if e.crm_id != entry.crm_id] + [entry]
        self.documents.sort(key=lambda e: e.doc_id)


def load_lock(path: Path, source: str) -> SourceLock:
    if not path.is_file():
        return SourceLock(source=source)
    return SourceLock.model_validate_json(path.read_text(encoding="utf-8"))


def save_lock(lock: SourceLock, path: Path) -> None:
    payload = lock.model_dump(mode="json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
