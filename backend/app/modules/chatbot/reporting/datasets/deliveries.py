"""Dataset `device_deliveries`: thiết bị giao cho khách (CRM `product_ownerships`, Reporting API).

Cần quyền CRM `auth.manage_roles`. Hệ thống không có bảng đơn bán hàng: "bán được" được
định nghĩa là quyền sở hữu thiết bị được tạo cho khách, không tính các lần chuyển nhượng
(`transferred_from_ownership_id` khác null).
"""

from ..catalog import ColumnSpec, DatasetSpec, FieldSpec, MetricSpec, ReportApiSource
from .tickets import enum_normalizer

PRODUCT_CATEGORY_LABELS = {
    "catalogue": "catalogue",
    "controller": "bộ điều khiển",
    "servo": "servo",
    "inverter": "biến tần",
    "software": "phần mềm",
}

DELIVERIES = DatasetSpec(
    name="device_deliveries",
    description=(
        "Thiết bị được giao cho khách (dùng cho câu hỏi 'bán được bao nhiêu'; "
        "cần quyền auth.manage_roles)."
    ),
    fields={
        "product_name": FieldSpec(
            "string", None, "Tên sản phẩm.", api_path="product_item_id.product_id.name", casefold=False,
        ),
        "product_category": FieldSpec(
            "enum", None, "Nhóm sản phẩm.", values=tuple(PRODUCT_CATEGORY_LABELS),
            labels=PRODUCT_CATEGORY_LABELS, normalize=enum_normalizer(PRODUCT_CATEGORY_LABELS),
            api_path="product_item_id.product_id.category",
        ),
        "customer": FieldSpec(
            "string", None, "Khách nhận thiết bị (nhóm theo mã, hiển thị tên; lọc đúng tên).",
            api_path="owner_customer_id", api_label_path="owner_customer_id.full_name",
            api_filter_path="owner_customer_id.full_name", casefold=False,
        ),
        "is_current": FieldSpec(
            "bool", None, "Khách hiện vẫn sở hữu thiết bị.", api_path="is_current",
        ),
    },
    metrics={
        "delivery_count": MetricSpec("count", "Số lần giao thiết bị.", api_metric="count"),
        "distinct_device_count": MetricSpec(
            "count_distinct", "Số thiết bị khác nhau.", api_metric="count_distinct:product_item_id",
        ),
        "distinct_customer_count": MetricSpec(
            "count_distinct", "Số khách khác nhau.", api_metric="count_distinct:owner_customer_id",
        ),
    },
    date_fields={"delivered_at": None},
    default_date_field="delivered_at",
    report=ReportApiSource(
        table="product_ownerships",
        date_paths={"delivered_at": "created_at"},
        system_filters=(
            (
                "không tính chuyển nhượng (transferred_from_ownership_id is null)",
                {"field": "transferred_from_ownership_id", "op": "is_null"},
            ),
        ),
        required_permission="auth.manage_roles",
    ),
    list_columns={
        "delivered_at": ColumnSpec("Thời điểm giao.", api_path="created_at"),
        "device_code": ColumnSpec("Mã thiết bị.", api_path="product_item_id.code"),
        "product_name": ColumnSpec("Tên sản phẩm.", api_path="product_item_id.product_id.name"),
        "customer": ColumnSpec("Tên khách.", api_path="owner_customer_id.full_name"),
        "is_current": ColumnSpec("Khách hiện vẫn sở hữu.", api_path="is_current"),
    },
    definitions=(
        "'Bán được' hiểu là thiết bị được giao cho khách (ngày tạo quyền sở hữu); hệ thống không có "
        "bảng đơn bán hàng.",
        "Không tính các lần chuyển nhượng thiết bị giữa khách.",
        "Ngày lọc theo giờ lưu trong CRM (giả định giờ Việt Nam).",
    ),
)
