"""Kết quả tìm model theo tiêu chí bằng dữ liệu sản phẩm có cấu trúc (bảng capabilities)."""

from typing import Literal

from pydantic import Field

from ..default import NonEmptyStr, SystemModel

# Backend quyết định bước kế tiếp hợp lệ; agent quyết định gọi tool nào để làm bước đó.
# report_no_match    : dữ liệu xác nhận không model nào thỏa, không tra tiếp.
# lookup_each        : 1..MAX_AUTO_LOOKUP_MODELS model, tra tiếp từng model.
# ask_selection      : nhiều model hơn ngưỡng, hỏi nhân viên chọn trước khi tra tiếp.
# verify_with_sources: còn điều kiện ngoài bảng; chỉ chọn model nguồn tài liệu nói rõ.
CatalogNextAction = Literal["report_no_match", "lookup_each", "ask_selection", "verify_with_sources"]


class CatalogConditions(SystemModel):
    """Điều kiện đã áp dụng lên bảng capabilities."""

    control_interface: list[NonEmptyStr] = Field(default_factory=list)
    excluded_control_interface: list[NonEmptyStr] = Field(default_factory=list)
    match: Literal["all", "any"] = "all"


class CatalogModel(SystemModel):
    code: NonEmptyStr                    # mã dùng khi gọi lại tool
    name: NonEmptyStr                    # tên hiển thị cho nhân viên
    has_technical_docs: bool             # có tài liệu kỹ thuật chi tiết (lắp đặt, vận hành...)
    documented_interfaces: list[NonEmptyStr] = Field(default_factory=list)


class CatalogMatch(SystemModel):
    sub_query_id: NonEmptyStr
    applied: CatalogConditions
    unmapped_conditions: list[NonEmptyStr] = Field(default_factory=list)
    # Ứng viên theo thứ tự registry. Với verify_with_sources đây chưa phải kết quả cuối.
    models: list[CatalogModel] = Field(default_factory=list)
    next_action: CatalogNextAction
