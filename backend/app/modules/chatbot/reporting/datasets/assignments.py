"""Dataset `support_assignments`: các lần giao phiếu hỗ trợ cho người xử lý (CRM Reporting API).

Cần quyền CRM `auth.manage_roles`. Mỗi dòng là một lần giao; một phiếu có thể được giao
nhiều lần (`is_current=false` là lần cũ). Khách của phiếu suy ra qua thiết bị gắn với phiếu
(`support_cases.product_item_id → product_items.customer_id`) vì `support_cases` không có cột
khách: đây là định nghĩa cố định của catalog, LLM không tự chọn đường join.
"""

from ..catalog import ColumnSpec, DatasetSpec, FieldSpec, MetricSpec, ReportApiSource
from .tickets import STATUS_LABELS, enum_normalizer

PRODUCT_NAME = "case_id.product_item_id.product_id.name"

ASSIGNMENTS = DatasetSpec(
    name="support_assignments",
    description=(
        "Các lần giao phiếu hỗ trợ cho người xử lý: ai hỗ trợ bao nhiêu phiếu/khách "
        "(cần quyền auth.manage_roles)."
    ),
    fields={
        "assignee": FieldSpec(
            "string", None,
            "Người được giao (username đăng nhập CRM); lọc phải đúng username.",
            api_path="assigned_to", api_label_path="assigned_to.username",
            api_filter_path="assigned_to.username", casefold=False,
            missing_label="(giao cho tổ chức)",
        ),
        "is_current": FieldSpec(
            "bool", None, "Lần giao đang hiệu lực (false: phiếu đã chuyển cho người khác).",
            api_path="is_current",
        ),
        "case_status": FieldSpec(
            "enum", None, "Trạng thái hiện tại của phiếu.", values=tuple(STATUS_LABELS),
            labels=STATUS_LABELS, normalize=enum_normalizer(STATUS_LABELS), api_path="case_id.status",
        ),
        "case_category": FieldSpec(
            "string", None, "Loại yêu cầu của phiếu, vd installation, alarm.",
            api_path="case_id.category", casefold=False,
        ),
        "product_name": FieldSpec(
            "string", None, "Tên sản phẩm của thiết bị gắn với phiếu.",
            api_path=PRODUCT_NAME, casefold=False, missing_label="(không gắn thiết bị)",
        ),
    },
    metrics={
        "assignment_count": MetricSpec("count", "Số lần giao phiếu.", api_metric="count"),
        "assigned_case_count": MetricSpec(
            "count_distinct", "Số phiếu khác nhau được giao.", api_metric="count_distinct:case_id",
        ),
        "distinct_customer_count": MetricSpec(
            "count_distinct", "Số khách khác nhau (qua thiết bị của phiếu).",
            api_metric="count_distinct:case_id.product_item_id.customer_id",
        ),
        "current_assignment_count": MetricSpec(
            "count", "Số lần giao đang hiệu lực (người đang phụ trách phiếu).", api_metric="count",
            api_filters=({"field": "is_current", "op": "eq", "value": "true"},),
        ),
    },
    date_fields={"assigned_at": None, "case_created_at": None},
    default_date_field="assigned_at",
    report=ReportApiSource(
        table="support_assignments",
        date_paths={"assigned_at": "created_at", "case_created_at": "case_id.created_at"},
        required_permission="auth.manage_roles",
    ),
    list_columns={
        "case_number": ColumnSpec("Mã phiếu.", api_path="case_id.case_number"),
        "case_status": ColumnSpec("Trạng thái phiếu.", api_path="case_id.status"),
        "case_category": ColumnSpec("Loại yêu cầu.", api_path="case_id.category"),
        "product_name": ColumnSpec("Tên sản phẩm.", api_path=PRODUCT_NAME),
        "customer": ColumnSpec(
            "Tên khách (qua thiết bị của phiếu).", api_path="case_id.product_item_id.customer_id.full_name",
        ),
        "assignee": ColumnSpec("Người được giao (username).", api_path="assigned_to.username"),
        "is_current": ColumnSpec("Lần giao đang hiệu lực.", api_path="is_current"),
        "assigned_at": ColumnSpec("Thời điểm giao.", api_path="created_at"),
    },
    definitions=(
        "Mỗi dòng là một lần giao phiếu; một phiếu có thể được giao nhiều lần, kể cả lần đã chuyển "
        "cho người khác (is_current=false).",
        "Khách của phiếu suy ra từ thiết bị gắn với phiếu; phiếu không gắn thiết bị không tính khách.",
        "Người xử lý hiển thị theo username đăng nhập CRM.",
        "Ngày lọc theo giờ lưu trong CRM (giả định giờ Việt Nam).",
    ),
)
