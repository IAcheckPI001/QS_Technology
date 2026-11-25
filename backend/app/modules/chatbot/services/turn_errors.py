"""Mã lỗi của một lượt `status=error`, lưu vào `retrieval_snapshot.error` (WU-17 đợt 2).

Chỉ ghi định danh (bước, mã nghiệp vụ, mã nhà cung cấp, HTTP status), không ghi message của exception vì có thể
chứa nội dung. Cho phép màn Chi tiết hội thoại nói nguyên nhân lỗi cả khi lượt không có trace
(`CHAT_TRACE_PERSIST` tắt). Hàm thuần, không import các lớp lỗi để tránh vòng import: nhận dạng theo tên lớp.
"""

from __future__ import annotations

import re

from app.core.tracing import provider_error_attributes

# Tên lớp lỗi → bước của pipeline (khớp tên stage trong trace: stage.<bước>).
_STAGE_BY_ERROR = {
    "ContextBudgetError": "context",
    "ContextConfigurationError": "context",
    "AnalysisError": "analysis",
    "ExecutionError": "retrieval",
    "AnswerCompositionError": "compose",
    "AgentError": "agent",
}
_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_MAX_CHAIN = 8


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _chain(error: BaseException):
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen and len(seen) < _MAX_CHAIN:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def turn_error(error: BaseException) -> dict[str, str | int | None]:
    """{stage, code, provider_code, http_status} của lỗi; mã nhà cung cấp lấy từ lỗi gốc trong chuỗi cause."""
    stage = next((_STAGE_BY_ERROR[type(e).__name__] for e in _chain(error) if type(e).__name__ in _STAGE_BY_ERROR),
                 None)
    code = getattr(error, "code", None)
    provider_code: str | None = None
    http_status: int | None = None
    for item in _chain(error):
        if type(item).__name__ in _STAGE_BY_ERROR:   # lỗi nghiệp vụ: `code` là mã của ta, không phải của nhà cung cấp
            continue
        attributes = provider_error_attributes(item)
        provider_code = provider_code or attributes.get("provider_error_code")  # type: ignore[assignment]
        http_status = http_status or attributes.get("http_status")  # type: ignore[assignment]
    return {
        "stage": stage,
        "code": code if isinstance(code, str) and _CODE.match(code) else _snake(type(error).__name__),
        "provider_code": provider_code,
        "http_status": http_status,
    }
