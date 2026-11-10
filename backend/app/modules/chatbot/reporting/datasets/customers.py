"""Dataset `customers`: khách hàng, qua dataset dựng sẵn `customers` của CRM Reporting API.

Cần quyền CRM `customer.read`; phạm vi dữ liệu do token quyết định phía CRM. CRM tự loại
khách đã xoá, đã gộp và bản ghi "chính tổ chức". Tên dimension (`assigned_sales`,
`created_month`…) là tên logic của dataset dựng sẵn, chưa kiểm tra bằng HTTP với token thật:
xác nhận bằng `backend/evals/check_crm_report_contract.py` trước khi bật cho người dùng.
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

CUSTOMERS = DatasetSpec(
    name="customers",
    description="Khách hàng trong phạm vi tài khoản được phép xem (cần quyền customer.read).",
    fields={
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
        "region": FieldSpec("string", None, "Vùng, vd VN.", api_path="region", casefold=False),
        "gender": FieldSpec(
            "enum", None, "Giới tính.", values=tuple(GENDER_LABELS), labels=GENDER_LABELS,
            normalize=enum_normalizer(GENDER_LABELS), api_path="gender",
        ),
        "assigned_sales": FieldSpec(
            "string", None, "Sale phụ trách: chỉ có mã người dùng (UUID), CRM chưa trả tên.",
            api_path="assigned_sales", casefold=False, missing_label="(chưa có sale)",
        ),
    },
    metrics={"customer_count": MetricSpec("count", "Số khách hàng.", api_metric="count")},
    date_fields={"created_at": None, "last_contact_at": None},
    default_date_field="created_at",
    report=ReportApiSource(
        table="customers",
        date_paths={"created_at": "created_at", "last_contact_at": "last_contact_at"},
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
        "code": ColumnSpec("Mã khách.", api_path="code"),
        "full_name": ColumnSpec("Tên khách.", api_path="full_name"),
        "customer_type": ColumnSpec("Loại khách.", api_path="customer_type"),
        "source": ColumnSpec("Nguồn khách.", api_path="source"),
        "region": ColumnSpec("Vùng.", api_path="region"),
        "created_at": ColumnSpec("Ngày tạo khách.", api_path="created_at"),
        "last_contact_at": ColumnSpec("Lần liên hệ gần nhất.", api_path="last_contact_at"),
    },
    definitions=(
        "Khách đã xoá hoặc đã gộp vào khách khác không được tính (CRM tự loại).",
        "Mặc định không tính khách loại spam và lost, trừ khi lọc hoặc nhóm theo customer_type.",
        "Ngày lọc theo giờ lưu trong CRM (giả định giờ Việt Nam).",
    ),
)
