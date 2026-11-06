"""Dataset `tickets`: phiếu hỗ trợ từ CRM `GET /api/v1/support/cases`.

Phạm vi dữ liệu do token (Bearer) quyết định phía CRM; dataset không lọc quyền.
`subject` và `description` không có trong TicketRecord nên bị bỏ ngay khi parse
và không bao giờ tới engine hay LLM.
"""

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator

from app.modules.chatbot.extraction.registry import REGISTRY
from app.modules.chatbot.extraction.validate_registry import resolve_models

from ..catalog import DatasetSpec, FieldSpec, MetricSpec, hours_between

STATUS_LABELS = {
    "new": "mới tạo",
    "pending": "đã gán người xử lý",
    "in_progress": "đang hỗ trợ",
    "resolved": "đã giải quyết",
    "closed": "hoàn thành",
    "rejected": "bị từ chối",
    "cancelled": "đã huỷ",
    "reopened": "mở lại",
}
STATUS_GROUPS = {
    "active": ("new", "pending", "in_progress", "reopened"),
    "closed": ("resolved", "closed"),
    "ended_unresolved": ("rejected", "cancelled"),
}
STATUS_GROUP_LABELS = {
    "active": "chưa đóng (new, pending, in_progress, reopened)",
    "closed": "đã xong (resolved, closed)",
    "ended_unresolved": "kết thúc không xử lý (rejected, cancelled)",
}
ACTIVE = frozenset(STATUS_GROUPS["active"])
DONE = frozenset(STATUS_GROUPS["closed"])
UNKNOWN_MODEL = "unknown"
PRODUCT_MODELS: tuple[str, ...] = (*REGISTRY["product_models"], UNKNOWN_MODEL)
# Go trả zero time (0001-01-01) cho thời điểm chưa có.
_MIN_YEAR = 1971


class TicketRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)

    id: str
    status: str
    priority: str | None = None
    category: str | None = None
    support_mode: str | None = None
    product_name: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    assignee_name: str | None = None
    assigned: bool = False
    has_open_appointment: bool = False
    delete_pending: bool = False
    created_at: AwareDatetime
    closed_at: AwareDatetime | None = None

    @field_validator(
        "priority", "category", "support_mode", "product_name", "customer_id", "customer_name",
        "assignee_name", "closed_at", mode="before",
    )
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("closed_at")
    @classmethod
    def _zero_time_is_none(cls, value: datetime | None) -> datetime | None:
        return None if value is not None and value.year < _MIN_YEAR else value


def _status_group(status: str) -> str | None:
    return next((group for group, values in STATUS_GROUPS.items() if status in values), None)


def _enum_normalizer(labels: dict[str, str]):
    """Nhận mã ("in_progress") hoặc nhãn tiếng Việt ("đang hỗ trợ"), không phân biệt hoa/thường."""
    lookup = {code.casefold(): code for code in labels}
    lookup.update({label.casefold(): code for code, label in labels.items()})

    def normalize(value: str) -> str | None:
        return lookup.get(value.strip().casefold())

    return normalize


def _normalize_model(value: str) -> str | None:
    if value.strip().casefold() == UNKNOWN_MODEL:
        return UNKNOWN_MODEL
    models, _, _ = resolve_models([value])
    return models[0] if len(models) == 1 else None


def _product_model(record: TicketRecord) -> str:
    name = record.product_name
    return name if name in REGISTRY["product_models"] else UNKNOWN_MODEL


def _is_active(record: TicketRecord, now: datetime) -> bool:
    return record.status in ACTIVE


def _is_closed(record: TicketRecord, now: datetime) -> bool:
    return record.status in DONE


def _open_to_close_hours(record: TicketRecord, now: datetime) -> float | None:
    return hours_between(record.created_at, record.closed_at)


def _age_hours(record: TicketRecord, now: datetime) -> float:
    return (now - record.created_at).total_seconds() / 3600


TICKETS = DatasetSpec(
    name="tickets",
    description="Phiếu hỗ trợ (support case) trong phạm vi tài khoản được phép xem.",
    source_path="/api/v1/support/cases",
    record_model=TicketRecord,
    fields={
        "status": FieldSpec(
            "enum", lambda r, now: r.status, "Trạng thái phiếu.",
            values=tuple(STATUS_LABELS), labels=STATUS_LABELS,
            normalize=_enum_normalizer(STATUS_LABELS),
        ),
        "status_group": FieldSpec(
            "enum", lambda r, now: _status_group(r.status), "Nhóm trạng thái.",
            values=tuple(STATUS_GROUPS), labels=STATUS_GROUP_LABELS,
            normalize=_enum_normalizer({code: code for code in STATUS_GROUPS}),
        ),
        "product_model": FieldSpec(
            "enum", lambda r, now: _product_model(r),
            "Model sản phẩm (product_name của CRM); 'unknown' = không thuộc danh mục.",
            values=PRODUCT_MODELS, normalize=_normalize_model,
        ),
        "category": FieldSpec(
            "string", lambda r, now: r.category,
            "Loại yêu cầu, vd installation, configuration, documentation, parameter, alarm, other.",
        ),
        "priority": FieldSpec("string", lambda r, now: r.priority, "Mức ưu tiên, vd normal."),
        "support_mode": FieldSpec(
            "string", lambda r, now: r.support_mode, "Hình thức hỗ trợ, vd video_call.",
        ),
        "assignee": FieldSpec(
            "string", lambda r, now: r.assignee_name, "Nhân viên xử lý (theo tên).",
            missing_label="(chưa gán)",
        ),
        "customer": FieldSpec(
            "string", lambda r, now: r.customer_name, "Khách hàng (nhóm theo mã, hiển thị tên).",
            key=lambda r, now: r.customer_id,
        ),
        "assigned": FieldSpec("bool", lambda r, now: r.assigned, "Đã gán người xử lý."),
        "has_open_appointment": FieldSpec(
            "bool", lambda r, now: r.has_open_appointment, "Có lịch hẹn đang mở.",
        ),
        "age_hours": FieldSpec(
            "number", _age_hours, "Số giờ từ lúc tạo tới hiện tại (lọc tồn đọng, vd > 72).",
            groupable=False,
        ),
    },
    metrics={
        "ticket_count": MetricSpec("count", "Số phiếu."),
        "active_ticket_count": MetricSpec(
            "count", "Số phiếu chưa đóng (new, pending, in_progress, reopened).", where=_is_active,
        ),
        "closed_ticket_count": MetricSpec(
            "count", "Số phiếu đã xong (resolved, closed).", where=_is_closed,
        ),
        "unassigned_ticket_count": MetricSpec(
            "count", "Số phiếu chưa đóng và chưa gán người xử lý.",
            where=lambda r, now: r.status in ACTIVE and not r.assigned,
        ),
        "distinct_customer_count": MetricSpec(
            "count_distinct", "Số khách hàng khác nhau.", value=lambda r, now: r.customer_id,
        ),
        "avg_open_to_close_hours": MetricSpec(
            "avg", "Thời gian trung bình từ tạo tới đóng (giờ), chỉ phiếu resolved/closed.",
            value=_open_to_close_hours, where=_is_closed,
        ),
        "max_open_to_close_hours": MetricSpec(
            "max", "Thời gian dài nhất từ tạo tới đóng (giờ), chỉ phiếu resolved/closed.",
            value=_open_to_close_hours, where=_is_closed,
        ),
        "avg_open_age_hours": MetricSpec(
            "avg", "Tuổi trung bình (giờ, tới hiện tại) của phiếu chưa đóng.",
            value=_age_hours, where=_is_active,
        ),
    },
    date_fields={
        "created_at": lambda r, now: r.created_at,
        "closed_at": lambda r, now: r.closed_at,
    },
    default_date_field="created_at",
    system_filters=(("delete_pending = false", lambda r, now: not r.delete_pending),),
)
