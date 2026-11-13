"""Audit query do LLM dựng cho `crm_query`: ghi cả giá trị, sau cờ `CRM_QUERY_AUDIT_LOG`.

Ngoại lệ có kiểm soát của quy tắc "trace/log chỉ metadata" (quyết định 2026-11-11): để
đánh giá query đúng hay sai cần thấy giá trị filter và body thật gửi CRM, mà giá trị có thể
là PII (tên khách, số điện thoại). Vì vậy:
- mặc định tắt; khi tắt `record` không làm gì;
- ghi vào logger riêng `app.crm_query.audit` (một dòng JSON mỗi lần gọi), tách khỏi log
  thường và span (`chat_traces`) vốn vẫn chỉ có metadata;
- không ghi `rows` (dữ liệu CRM trả về), câu hỏi hay câu trả lời. Câu hỏi tra lại bằng
  `request_id` trong `chat_history`.
"""

import logging
from typing import Any, Literal

from pydantic import Field

from app.core.tracing import current_trace
from app.modules.chatbot.schemas.default import SystemModel

AUDIT_LOGGER = "app.crm_query.audit"
MAX_RAW_ARGUMENTS_CHARS = 4000

AuditPhase = Literal["invalid_args", "rejected", "sent"]
# empty: CRM trả 0 dòng (query hợp lệ nhưng có thể lọc sai cột/dấu): tín hiệu chính cần xem lại.
QueryOutcome = Literal["ok", "empty", "invalid_args", "rejected", "crm_invalid", "crm_error"]

CRM_INVALID_CODE = "crm_query_invalid"


class QueryAuditRecord(SystemModel):
    """Một lần gọi crm_query. `arguments`/`body` có kiểu dict vì là payload JSON tự do của
    LLM và của CRM Reporting API; đây là bản ghi để đọc lại, không phải contract đầu vào."""

    trace_id: str | None
    request_id: str
    tool_call_id: str
    attempt: int = Field(ge=1)
    phase: AuditPhase
    outcome: QueryOutcome
    arguments: dict[str, Any] | None = None     # argument đã validate (RawQuery)
    arguments_raw: str | None = None            # chỉ khi validate thất bại
    body: dict[str, Any] | None = None          # query gửi CRM
    count_body: dict[str, Any] | None = None    # query đếm tổng (mode=list)
    ignored: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    returned: int | None = None
    total: int | None = None
    latency_ms: int | None = None


def outcome_of_error(code: str) -> QueryOutcome:
    if code == "tool_invalid_args":
        return "invalid_args"
    return "crm_invalid" if code == CRM_INVALID_CODE else "crm_error"


class QueryAudit:
    def __init__(self, enabled: bool, logger: logging.Logger | None = None) -> None:
        self.enabled = enabled
        self._logger = logger or logging.getLogger(AUDIT_LOGGER)
        if enabled and self._logger.level == logging.NOTSET:
            # Vẫn ghi khi LOG_LEVEL cao hơn INFO: bật cờ là muốn có audit.
            self._logger.setLevel(logging.INFO)

    def record(self, **fields: Any) -> None:
        """Ghi một bản ghi; lỗi khi ghi audit không được làm hỏng lượt chat."""
        if not self.enabled:
            return
        try:
            trace = current_trace()
            raw = fields.get("arguments_raw")
            if isinstance(raw, str):
                fields["arguments_raw"] = raw[:MAX_RAW_ARGUMENTS_CHARS]
            item = QueryAuditRecord(trace_id=trace.trace_id if trace else None, **fields)
            self._logger.info(item.model_dump_json(exclude_none=True))
        except Exception:
            logging.getLogger(__name__).exception("crm_query audit record failed")


__all__ = [
    "AUDIT_LOGGER",
    "QueryAudit",
    "QueryAuditRecord",
    "QueryOutcome",
    "outcome_of_error",
]
