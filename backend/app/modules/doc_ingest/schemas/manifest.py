"""Manifest tài liệu cho chunk builder (contract C2 §3): thông tin cấp tài liệu không suy được từ PDF."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.modules.doc_ingest.schemas.base import StrictModel

Scope = Literal["installation", "operation", "configuration", "maintenance"]
SCOPE_ORDER: tuple[Scope, ...] = ("installation", "operation", "configuration", "maintenance")


class ScopeRule(StrictModel):
    """Regex trên `section_path` nối bằng " › "; luật đầu tiên khớp thắng."""

    match: str
    scopes: list[Scope] = Field(min_length=1)


class DocManifest(StrictModel):
    doc_id: str                                  # theo quy ước CSV: {model}_{loại}_{phiên bản}
    run_doc_ids: list[str] = Field(default_factory=list)   # `--doc-id` của các lần chạy ingest ứng với tài liệu này
    doc_type: Literal["user_guide", "installation_manual"]
    doc_title: str
    doc_version: str
    product_models: list[str] = Field(min_length=1)
    lang: str
    default_scopes: list[Scope] = Field(min_length=1)
    scope_rules: list[ScopeRule] = Field(default_factory=list)
    storage_bucket: str
    note: str = ""

    @field_validator("doc_id")
    @classmethod
    def _doc_id_safe(cls, value: str) -> str:
        if not value or any(ch in value for ch in " /\\:"):
            raise ValueError("doc_id không được rỗng hoặc chứa khoảng trắng, '/', '\\', ':'")
        return value
