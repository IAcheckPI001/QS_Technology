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


class CrmSource(StrictModel):
    """Nguồn tài liệu trên CRM (2026-11-19, crm-sync): khóa `crm_id` là `id` của tài liệu trong cây
    `company-docs/website-tree`; `file_id` là mã file trong `file_url` (đổi khi upload file mới).
    Không chứa URL đã ký (`exp`, `sig` hết hạn theo ngày)."""

    system: Literal["crm"] = "crm"
    crm_id: str
    version: str
    file_id: str
    sha256: str
    synced_at: str                               # YYYY-MM-DD


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
    # Đối tượng xem (2026-11-21): `public` = đã công bố cho khách ở website (chat website và CRM đều tìm được);
    # `internal` = chỉ kênh CRM. Mặc định `internal` để tài liệu mới không lộ ra website khi quên gán.
    audience: Literal["public", "internal"] = "internal"
    # Loại khỏi chunk (2026-11-13): trang (`pdf_page_index`) hoặc mục (tiền tố tiêu đề một cấp trong `section_path`)
    # không có nội dung kỹ thuật (bìa, lời cảm ơn, lịch sử phiên bản…). Phần tử bị loại tính vào độ phủ với lý do
    # `manifest_excluded`; `exclude_reason` ghi vì sao (người duyệt đọc).
    exclude_pages: list[int] = Field(default_factory=list)
    exclude_sections: list[str] = Field(default_factory=list)
    exclude_reason: str = ""
    note: str = ""
    source: CrmSource | None = None              # None = PDF đưa vào tay (manifest cũ)

    @field_validator("doc_id")
    @classmethod
    def _doc_id_safe(cls, value: str) -> str:
        if not value or any(ch in value for ch in " /\\:"):
            raise ValueError("doc_id không được rỗng hoặc chứa khoảng trắng, '/', '\\', ':'")
        return value
