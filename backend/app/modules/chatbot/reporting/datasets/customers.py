"""Dataset `customers`: khách hàng, qua dataset dựng sẵn `customers` của CRM Reporting API.

Cần quyền CRM `customer.read`; phạm vi dữ liệu do token quyết định phía CRM. CRM tự loại
khách đã xoá, đã gộp và bản ghi "chính tổ chức". Dimension dùng tên logic của dataset dựng
sẵn (`assigned_sales`, `created_day`, `created_month`) hoặc đường dẫn cột thật/join
(`assigned_sales_id.username`); `select`, `filters` và `order_by` dùng tên cột thật của bảng
`customers` (xem `GET /api/v1/reports/tables/customers`). Đã kiểm tra bằng HTTP với token
thật ngày 2026-11-10 (`backend/evals/check_crm_report_contract.py`); chạy lại khi đổi
catalog hoặc CRM đổi schema.

Quyết định 2026-11-10: AI được đọc và lọc mọi cột nghiệp vụ của khách, kể cả liên hệ
(email, phone, address) và ghi chú. Không khai báo `deleted_at`/`merged_into_id` (CRM đã
loại các khách này) và `self_of_organization_id` (khách đại diện tổ chức bị loại).
`contains` của CRM không phân biệt hoa thường nhưng phân biệt dấu tiếng Việt.
"""

from ..catalog import ColumnSpec, DatasetSpec, FieldSpec, MetricSpec, ReportApiSource
from .tickets import enum_normalizer

CUSTOMER_TYPE_LABELS = {
    "lead": "khách tiềm năng",
    "student": "học viên",
    "official": "khách chính thức",
    "spam": "spam",
    "lost": "đã mất",
}
GENDER_LABELS = {"male": "nam", "female": "nữ"}
EXCLUDED_TYPES = ("spam", "lost")


def _text_filter(description: str, api_path: str) -> FieldSpec:
    """Trường văn bản chỉ để lọc (eq hoặc contains), không nhóm."""
    return FieldSpec("string", None, description, api_path=api_path, casefold=False, groupable=False)


CUSTOMERS = DatasetSpec(
    name="customers",
    description="Khách hàng trong phạm vi tài khoản được phép xem (cần quyền customer.read).",
    fields={
        "full_name": _text_filter("Tên khách; tìm theo tên dùng contains.", "full_name"),
        "code": _text_filter("Mã khách.", "code"),
        "company_name": _text_filter("Tên công ty của khách.", "company_name"),
        "phone": _text_filter("Số điện thoại khách.", "phone"),
        "main_phone": _text_filter("Số điện thoại chính.", "main_phone"),
        "email": _text_filter("Email khách.", "email"),
        "main_email": _text_filter("Email chính.", "main_email"),
        "address": _text_filter("Địa chỉ.", "address"),
        "website": _text_filter("Website.", "website"),
        "notes": _text_filter("Ghi chú về khách.", "notes"),
        "customer_type": FieldSpec(
            "enum", None, "Loại khách.", values=tuple(CUSTOMER_TYPE_LABELS),
            labels=CUSTOMER_TYPE_LABELS, normalize=enum_normalizer(CUSTOMER_TYPE_LABELS),
            api_path="customer_type",
        ),
        "status": FieldSpec(
            "string", None, "Trạng thái chăm sóc (tên trạng thái trong CRM, đúng chính tả).",
            api_path="status", casefold=False,
        ),
        "source": FieldSpec(
            "string", None, "Nguồn khách (đúng giá trị trong CRM).", api_path="source", casefold=False,
        ),
        "campaign": FieldSpec(
            "string", None, "Tên chiến dịch đem khách về.", api_path="source_campaign_id.name",
            casefold=False, missing_label="(không có chiến dịch)",
        ),
        "organization": FieldSpec(
            "string", None, "Tên tổ chức/chi nhánh sở hữu khách.", api_path="organization_id.name",
            casefold=False,
        ),
        "region": FieldSpec("string", None, "Vùng, vd VN.", api_path="region", casefold=False),
        "gender": FieldSpec(
            "enum", None, "Giới tính.", values=tuple(GENDER_LABELS), labels=GENDER_LABELS,
            normalize=enum_normalizer(GENDER_LABELS), api_path="gender",
        ),
        "assigned_sales": FieldSpec(
            "string", None, "Sale phụ trách theo mã người dùng (UUID); lọc/nhóm theo tên dùng sales_username.",
            api_path="assigned_sales", casefold=False, missing_label="(chưa có sale)",
        ),
        "sales_username": FieldSpec(
            "string", None, "Username đăng nhập CRM của sale phụ trách.",
            api_path="assigned_sales_id.username", casefold=False, missing_label="(chưa có sale)",
        ),
    },
    metrics={"customer_count": MetricSpec("count", "Số khách hàng.", api_metric="count")},
    date_fields={
        "created_at": None, "last_contact_at": None, "last_inbound_at": None,
        "assigned_at": None, "updated_at": None,
    },
    default_date_field="created_at",
    report=ReportApiSource(
        table="customers",
        date_paths={
            "created_at": "created_at", "last_contact_at": "last_contact_at",
            "last_inbound_at": "last_inbound_at", "assigned_at": "assigned_at", "updated_at": "updated_at",
        },
        default_filters=(
            (
                "customer_type not_in [spam, lost] (mặc định)",
                "customer_type",
                {"field": "customer_type", "op": "not_in", "value": list(EXCLUDED_TYPES)},
            ),
        ),
        required_permission="customer.read",
        period_dimensions={
            ("created_at", "day"): "created_day",
            ("created_at", "month"): "created_month",
        },
    ),
    list_columns={
        "id": ColumnSpec("Mã định danh (UUID) của khách.", api_path="id"),
        "code": ColumnSpec("Mã khách.", api_path="code"),
        "full_name": ColumnSpec("Tên khách.", api_path="full_name"),
        "company_name": ColumnSpec("Công ty.", api_path="company_name"),
        "customer_type": ColumnSpec("Loại khách.", api_path="customer_type"),
        "status": ColumnSpec("Trạng thái chăm sóc.", api_path="status_id.name"),
        "source": ColumnSpec("Nguồn khách.", api_path="source"),
        "campaign": ColumnSpec("Chiến dịch đem khách về.", api_path="source_campaign_id.name"),
        "organization": ColumnSpec("Tổ chức/chi nhánh sở hữu.", api_path="organization_id.name"),
        "sales_username": ColumnSpec("Username sale phụ trách.", api_path="assigned_sales_id.username"),
        "region": ColumnSpec("Vùng.", api_path="region"),
        "gender": ColumnSpec("Giới tính.", api_path="gender"),
        "phone": ColumnSpec("Số điện thoại.", api_path="phone"),
        "main_phone": ColumnSpec("Số điện thoại chính.", api_path="main_phone"),
        "email": ColumnSpec("Email.", api_path="email"),
        "main_email": ColumnSpec("Email chính.", api_path="main_email"),
        "address": ColumnSpec("Địa chỉ.", api_path="address", max_chars=300),
        "website": ColumnSpec("Website.", api_path="website"),
        "notes": ColumnSpec("Ghi chú.", api_path="notes", max_chars=1000),
        "created_by": ColumnSpec("Username người tạo khách.", api_path="created_by.username"),
        "created_at": ColumnSpec("Ngày tạo khách.", api_path="created_at"),
        "updated_at": ColumnSpec("Lần cập nhật gần nhất.", api_path="updated_at"),
        "assigned_at": ColumnSpec("Ngày giao cho sale.", api_path="assigned_at"),
        "last_contact_at": ColumnSpec("Lần liên hệ gần nhất.", api_path="last_contact_at"),
        "last_inbound_at": ColumnSpec("Lần khách chủ động liên hệ gần nhất.", api_path="last_inbound_at"),
    },
    definitions=(
        "Khách đã xoá hoặc đã gộp vào khách khác không được tính (CRM tự loại).",
        "Mặc định không tính khách loại spam và lost, trừ khi lọc hoặc nhóm theo customer_type.",
        "Tìm theo chữ (contains) không phân biệt hoa thường nhưng phân biệt dấu tiếng Việt.",
        "Ngày lọc theo giờ lưu trong CRM (giả định giờ Việt Nam).",
    ),
)
