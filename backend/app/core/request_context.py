"""Request ID dùng chung cho middleware, router, service và logging."""
import logging
import re
from contextvars import ContextVar
from uuid import uuid4

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Chỉ chấp nhận ID "sạch" (chống log injection / header quá dài).
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def get_request_id() -> str | None:
    return request_id_var.get()


def current_request_id() -> str:
    """ID do middleware chốt; app chạy không có middleware (test) thì sinh mới."""
    return request_id_var.get() or str(uuid4())


def is_valid_request_id(value: str | None) -> bool:
    return value is not None and _REQUEST_ID_RE.fullmatch(value) is not None


class RequestIdFilter(logging.Filter):
    """Gắn record.request_id cho MỌI log record.

    Phải gắn vào *handler* (không phải logger): filter của logger cha không
    chạy với record được propagate lên từ logger con.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True