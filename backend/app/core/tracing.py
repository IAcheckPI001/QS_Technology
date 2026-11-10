"""Tracing trong tiến trình (giai đoạn 0): cây span cho một request, không dùng thư viện ngoài.

Mỗi request chat có một `Trace` gồm các `Span` (tên, loại, thời điểm bắt đầu tính từ
lúc request đến, thời lượng, trạng thái, thuộc tính). Span cha được giữ trong
contextvars: `asyncio.TaskGroup` sao chép context cho task con, nên tool chạy song
song vẫn nằm dưới đúng span cha và không làm lệch span hiện tại của task cha.

Chỉ ghi metadata (id, đếm, độ trễ, mã trạng thái, token). Không bao giờ ghi nội dung
tin nhắn, argument hay output của tool, prompt, câu trả lời hoặc token bí mật:
`Span.set` cắt chuỗi ngắn để giới hạn thiệt hại khi lỡ truyền giá trị dài.

Không có trace đang chạy (test, đường code ngoài chat) thì `span()` trả span rời,
không ghi vào đâu: code nghiệp vụ không phải kiểm tra trace có tồn tại hay không.
"""

import asyncio
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal
from uuid import uuid4

TRACE_FORMAT_VERSION = 1
DEFAULT_MAX_SPANS = 500
MAX_ATTR_STR = 120
MAX_ATTR_LIST = 20
MAX_DETAIL_ITEMS = 5
# Giá trị trong nháy đơn/kép của thông báo lỗi (vd. `unknown value 'Nguyễn Văn A'`).
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")

SpanKind = Literal["server", "internal", "stage", "llm", "embedding", "tool", "db", "http"]
AttrValue = str | int | float | bool | None | list[str]

# Trạng thái span: "ok", "error" (exception), "cancelled" (client ngắt) hoặc mã nghiệp vụ.
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"
# Trạng thái không tính là lỗi trong summary (call gộp trùng dùng lại kết quả thành công).
NON_ERROR_STATUSES = frozenset({STATUS_OK, "deduplicated"})


def redact_quoted(text: str) -> str:
    """Che giá trị trong nháy: thông báo lỗi có thể lặp lại giá trị LLM/người dùng điền."""
    return _QUOTED.sub("'…'", text)


def error_detail_items(detail: str | None) -> list[str]:
    """Lý do lỗi (do code viết) thành list ngắn để ghi vào span: tách theo '; ', che giá trị."""
    if not detail:
        return []
    parts = [part.strip() for part in detail.split("; ") if part.strip()]
    return [redact_quoted(part)[:MAX_ATTR_STR] for part in parts[:MAX_DETAIL_ITEMS]]


def _clean(value: object) -> AttrValue:
    if value is None or isinstance(value, bool | int | float):
        return value  # type: ignore[return-value]
    if isinstance(value, list | tuple | set | frozenset):
        return [str(item)[:MAX_ATTR_STR] for item in list(value)[:MAX_ATTR_LIST]]
    return str(value)[:MAX_ATTR_STR]


@dataclass
class Span:
    span_id: str
    parent_id: str | None
    name: str
    kind: SpanKind
    start_ms: float
    duration_ms: float | None = None
    status: str = STATUS_OK
    attributes: dict[str, AttrValue] = field(default_factory=dict)
    opened_at: float = field(default_factory=perf_counter, repr=False)

    def elapsed_ms(self) -> float:
        """Thời gian từ lúc mở span tới hiện tại (vd. token đầu tiên của stream)."""
        return (perf_counter() - self.opened_at) * 1000

    def set(self, **attributes: object) -> None:
        for key, value in attributes.items():
            self.attributes[key] = _clean(value)

    def add(self, key: str, amount: int | float) -> None:
        """Cộng dồn số (vd. token của nhiều lần gọi trong cùng span)."""
        current = self.attributes.get(key)
        base = current if isinstance(current, int | float) and not isinstance(current, bool) else 0
        self.attributes[key] = base + amount

    def fail(self, status: str) -> None:
        self.status = status

    def to_dict(self) -> dict[str, object]:
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "kind": self.kind,
            "start_ms": round(self.start_ms, 1),
            "duration_ms": round(self.duration_ms, 1) if self.duration_ms is not None else None,
            "status": self.status,
            "attributes": dict(self.attributes),
        }


def _detached(name: str, kind: SpanKind) -> Span:
    """Span không thuộc trace nào: nhận set()/fail() nhưng không được lưu."""
    return Span(span_id="", parent_id=None, name=name, kind=kind, start_ms=0.0)


class Trace:
    """Cây span của một request. Chỉ dùng trong một event loop (không cần khóa)."""

    def __init__(
        self,
        request_id: str,
        *,
        root_name: str = "request",
        started_at: float | None = None,
        max_spans: int = DEFAULT_MAX_SPANS,
    ) -> None:
        self.trace_id = uuid4().hex
        self.request_id = request_id
        # perf_counter lúc request đến (middleware) để start_ms khớp với duration HTTP.
        self.started_at = started_at if started_at is not None else perf_counter()
        self.max_spans = max_spans
        self.dropped_spans = 0
        self._next_id = 0
        self.spans: list[Span] = []
        self.root = self._new_span(root_name, "server", None)
        self.root.start_ms = 0.0

    def _offset_ms(self) -> float:
        return (perf_counter() - self.started_at) * 1000

    def _new_span(self, name: str, kind: SpanKind, parent_id: str | None) -> Span:
        self._next_id += 1
        span = Span(
            span_id=f"{self._next_id:04x}",
            parent_id=parent_id,
            name=name,
            kind=kind,
            start_ms=self._offset_ms(),
        )
        self.spans.append(span)
        return span

    def start_span(self, name: str, kind: SpanKind, parent: Span | None) -> Span | None:
        if len(self.spans) >= self.max_spans:
            self.dropped_spans += 1
            return None
        return self._new_span(name, kind, (parent or self.root).span_id)

    def end_span(self, span: Span) -> None:
        if span.duration_ms is None:
            span.duration_ms = max(self._offset_ms() - span.start_ms, 0.0)

    def finish(self, status: str = STATUS_OK) -> None:
        """Đóng root (một lần); span con còn mở bị đánh dấu chưa kết thúc."""
        if self.root.duration_ms is not None:
            return
        for span in self.spans:
            if span.duration_ms is None and span is not self.root:
                span.status = span.status if span.status != STATUS_OK else "unfinished"
                self.end_span(span)
        self.root.status = status
        self.end_span(self.root)

    @property
    def duration_ms(self) -> float:
        return self.root.duration_ms if self.root.duration_ms is not None else self._offset_ms()

    def summary(self) -> dict[str, int]:
        def total(kind: str, key: str) -> int:
            return int(sum(
                value
                for span in self.spans
                if span.kind == kind
                for value in [span.attributes.get(key)]
                if isinstance(value, int | float) and not isinstance(value, bool)
            ))

        failed = [
            span for span in self.spans
            if span.status not in NON_ERROR_STATUSES and span is not self.root
        ]
        failed_parents = {span.parent_id for span in failed}
        return {
            "span_count": len(self.spans),
            "dropped_spans": self.dropped_spans,
            "llm_calls": sum(1 for span in self.spans if span.kind == "llm"),
            "tool_calls": sum(1 for span in self.spans if span.kind == "tool"),
            # Mọi span lỗi, kể cả span cha nhận lỗi lan lên từ span con.
            "error_spans": len(failed),
            # Nơi lỗi phát sinh: span lỗi không có span con nào lỗi.
            "root_error_spans": sum(
                1 for span in failed if span.span_id not in failed_parents
            ),
            "failed_tool_calls": sum(1 for span in failed if span.kind == "tool"),
            "input_tokens": total("llm", "input_tokens"),
            "output_tokens": total("llm", "output_tokens"),
            "embedding_tokens": total("embedding", "input_tokens"),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "version": TRACE_FORMAT_VERSION,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "duration_ms": round(self.duration_ms, 1),
            "summary": self.summary(),
            "spans": [span.to_dict() for span in self.spans],
        }


_trace_var: ContextVar[Trace | None] = ContextVar("trace", default=None)
_span_var: ContextVar[Span | None] = ContextVar("trace_span", default=None)


def current_trace() -> Trace | None:
    return _trace_var.get()


def current_span() -> Span:
    """Span đang mở của task hiện tại; span rời nếu không có trace."""
    span = _span_var.get()
    if span is not None:
        return span
    trace = _trace_var.get()
    return trace.root if trace is not None else _detached("detached", "internal")


def set_root(**attributes: object) -> None:
    """Gắn thuộc tính cho root span của trace hiện tại (không có trace thì bỏ qua)."""
    trace = _trace_var.get()
    if trace is not None:
        trace.root.set(**attributes)


@contextmanager
def activate(trace: Trace | None) -> Iterator[Trace | None]:
    """Đặt trace làm trace hiện tại (span cha mặc định = root).

    Khôi phục bằng set() giá trị cũ thay vì reset(token): an toàn khi khối này nằm
    trong async generator được đóng ở context khác.
    """
    previous_trace, previous_span = _trace_var.get(), _span_var.get()
    _trace_var.set(trace)
    _span_var.set(trace.root if trace is not None else None)
    try:
        yield trace
    finally:
        _trace_var.set(previous_trace)
        _span_var.set(previous_span)


@contextmanager
def span(name: str, kind: SpanKind = "internal", **attributes: object) -> Iterator[Span]:
    """Mở span con của span hiện tại; exception đánh dấu span rồi được ném tiếp."""
    trace = _trace_var.get()
    parent = _span_var.get()
    opened = trace.start_span(name, kind, parent) if trace is not None else None
    current = opened or _detached(name, kind)
    current.set(**attributes)
    if opened is not None:
        _span_var.set(opened)
    try:
        yield current
    except (asyncio.CancelledError, GeneratorExit):
        current.status = STATUS_CANCELLED
        raise
    except BaseException as error:
        if current.status == STATUS_OK:
            current.status = STATUS_ERROR
        current.attributes["error_type"] = type(error).__name__
        raise
    finally:
        if opened is not None and trace is not None:
            trace.end_span(opened)
            _span_var.set(parent)
