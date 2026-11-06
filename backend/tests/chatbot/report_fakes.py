"""Dữ liệu và helper dùng chung cho test báo cáo CRM (dataset tickets)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.chatbot.reporting.datasets import DATASETS
from app.modules.chatbot.reporting.validate import validate_query
from app.modules.chatbot.schemas.system.report import ReportQuery

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
# Thứ Hai 02/11/2026, 10:00 giờ Việt Nam.
NOW = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)
TICKETS = DATASETS["tickets"]


def case(
    case_id: str,
    created_at: str,
    *,
    status: str = "closed",
    product: str = "F86",
    hours_to_close: float | None = None,
    customer: tuple[str, str] = ("c1", "Công ty A"),
    assignee: str | None = "Nhân viên A",
    category: str = "installation",
    delete_pending: bool = False,
) -> dict:
    """Một item giống response của GET /api/v1/support/cases."""
    created = datetime.fromisoformat(created_at)
    closed = (
        (created + timedelta(hours=hours_to_close)).isoformat().replace("+00:00", "Z")
        if hours_to_close is not None
        else "0001-01-01T00:00:00Z"            # Go zero time: chưa đóng
    )
    return {
        "id": case_id,
        "case_number": f"SC-{case_id}",
        "product_item_id": "pi-1",
        "created_by": "u-1",
        "category": category,
        "priority": "normal",
        "status": status,
        "support_mode": "video_call",
        "customer_id": customer[0],
        "customer_name": customer[1],
        "assignee_name": assignee,
        "creator_name": "Người tạo",
        "product_name": product,
        "chat_at": None,
        "has_open_appointment": False,
        "subject": f"SECRET-SUBJECT-{case_id}",
        "description": f"SECRET-DESCRIPTION-{case_id}",
        "assigned": assignee is not None,
        "named_assignee": assignee is not None,
        "delete_pending": delete_pending,
        "closed_at": closed,
        "period_started_at": created_at,
        "session_started_at": None,
        "created_at": created_at.replace("+00:00", "Z"),
        "updated_at": created_at.replace("+00:00", "Z"),
    }


def sample_cases() -> list[dict]:
    return [
        case("1", "2026-09-05T02:00:00+00:00", hours_to_close=2),
        case("2", "2026-10-10T02:00:00+00:00", hours_to_close=4),
        case("3", "2026-10-20T02:00:00+00:00", status="new", assignee=None,
             customer=("c2", "Công ty B")),
        case("4", "2026-10-25T02:00:00+00:00", status="in_progress", product="6AH",
             assignee="Nhân viên B", customer=("c3", "Công ty C"), category="alarm"),
        # 20:00 UTC 30/09 = 03:00 ngày 01/10 giờ Việt Nam: thuộc tháng 10.
        case("5", "2026-09-30T20:00:00+00:00", status="cancelled", product="F54",
             assignee="Nhân viên B", customer=("c2", "Công ty B")),
        case("6", "2026-08-15T02:00:00+00:00", hours_to_close=10, product="XYZ",
             customer=("c4", "Công ty A")),        # trùng tên với c1, khác mã
        case("7", "2026-10-05T02:00:00+00:00", hours_to_close=1, delete_pending=True),
    ]


def records(items=None):
    parsed, skipped = TICKETS.parse(sample_cases() if items is None else items)
    assert skipped == 0
    return parsed


def report_query(**fields) -> ReportQuery:
    return ReportQuery.model_validate({"dataset": "tickets", "metrics": ["ticket_count"], **fields})


def normalized(**fields):
    return validate_query(report_query(**fields), DATASETS, now=NOW, tz=TZ)
