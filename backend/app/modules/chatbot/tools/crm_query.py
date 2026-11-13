"""Tool `crm_query`: query CRM Reporting API do LLM tự dựng (danh sách hoặc thống kê, mọi bảng).

Phương án C (quyết định 2026-11-10): câu hỏi quá đa dạng cho catalog cố định, nên LLM chọn
bảng/cột/join theo `crm_schema` và contract của CRM. Dịch vụ AI kiểm tra hình dạng query, chặn
bảng/cột bí mật, đổi preset ngày ra ngày cụ thể (`reporting/raw/compile.py`); CRM dựng SQL
tham số hoá và giới hạn dữ liệu theo token của nhân viên. 400 của CRM trả lại cho LLM
(`crm_query_invalid`) để sửa. Danh sách chạy thêm một query `count` song song để có tổng.
"""

import json
import logging
from collections.abc import Callable
from datetime import tzinfo
from time import perf_counter
from typing import Any, Literal

from pydantic import Field

from app.core.tracing import current_span, set_root, span
from app.modules.chatbot.providers.crm_api import CrmReportClient
from app.modules.chatbot.reporting.dates import stated_years
from app.modules.chatbot.reporting.raw.audit import QueryAudit, QueryOutcome, outcome_of_error
from app.modules.chatbot.reporting.raw.compile import (
    CompiledRaw,
    RawQueryError,
    compile_raw,
    count_of,
    map_rows,
    map_totals,
)
from app.modules.chatbot.reporting.raw.policy import static_column_type, static_relation
from app.modules.chatbot.reporting.raw.schema import CrmSchemaCache, compact_type
from app.modules.chatbot.schemas.default import SystemModel
from app.modules.chatbot.schemas.system import RunState, ToolTurnState
from app.modules.chatbot.schemas.system.raw_query import RawQuery

from .base import ToolArgumentError, ToolContext, ToolOutput, ToolRejected, ToolSpec
from .crm_report import crm_credential, query_all

CRM_QUERY_TOOL_NAME = "crm_query"

logger = logging.getLogger(__name__)

_TRUNCATION_MARGIN_TOKENS = 32
# Trần mỗi lượt (2026-11-12): 4 lần gửi CRM; lần bị compile/validate chặn không tốn lượt CRM nên
# chỉ chịu trần thử tổng (runner áp qua max_calls_per_turn).
MAX_CRM_QUERIES_PER_TURN = 4
MAX_QUERY_ATTEMPTS_PER_TURN = 6
TOOL_CALL_LIMIT = "tool_call_limit"

CRM_QUERY_DESCRIPTION = (
    "Đọc dữ liệu CRM/ERP (khách hàng, phiếu hỗ trợ, thiết bị, mua hàng, kho, sản xuất, dự án, nhân "
    "viên, ...) trong phạm vi quyền của tài khoản nhân viên, qua Reporting API: danh sách bản ghi "
    "(select) hoặc số liệu (metrics, có thể chia nhóm theo dimensions), filter AND, join fk.cột, "
    "khoảng ngày. Chỉ dùng cột/quan hệ đã thấy trong crm_schema."
)

CRM_QUERY_GUIDE = """Chọn bảng gốc (dataset) theo nghĩa câu hỏi:
- khách hàng, khách mới (created_at), sale phụ trách (assigned_sales_id) → customers; khách tiềm năng từ form → leads; học viên → students.
- phiếu hỗ trợ (đếm, trạng thái, danh sách) → support_cases; ai được giao/đã hỗ trợ bao nhiêu phiếu hoặc khách → support_assignments.
- "bán được", thiết bị giao cho khách → product_ownerships (không có bảng đơn bán hàng); máy cụ thể → product_items; model → products.
- mua hàng → purchase_orders/purchase_requisitions; tồn kho → stock; nhập/xuất kho → goods_receipts/goods_issues/stock_movements.
- nhân viên: họ tên → user_profiles (first_name = tên gọi, last_name = họ và tên đệm); tài khoản (username, email, đang hoạt động) → auth_users. Nhân viên theo vai trò (sales, kho, kế toán...) → user_roles: filter role_id.code, metric count_distinct:user_id; hệ thống tự lọc user_id.is_active (tài khoản còn dùng). auth_users gồm cả tài khoản khách và đại lý: không đếm auth_users để trả lời "bao nhiêu nhân viên".
- lịch sử chăm sóc khách của sale → activities; nhật ký sửa khách → customer_logs.

Quy trình:
- Mỗi lượt gọi crm_schema MỘT lần cho mọi bảng cần (bảng gốc + bảng đích của join), kể cả lượt hỏi tiếp (history không giữ schema), rồi crm_query. Không đoán tên cột/quan hệ.
- mode: con số/thống kê → aggregate; danh sách/liệt kê/tìm → list. Cần cả hai thì gọi hai crm_query trong cùng một bước.
- Join: fk.cột theo relations, chỉ đi từ bảng có khoá ngoại sang bảng đích. Thông tin ở bảng con (referenced_by, vd user_roles) thì lấy bảng con làm dataset. Cần tên người/vật tư/khách trong kết quả: chọn hoặc nhóm thẳng cột tên qua join (vd dimensions [assigned_sales_id.username], select [material_id.name]), không lấy UUID rồi gọi thêm query để tra tên.
- Có username hoặc mã: lọc thẳng qua join trong cùng query (vd assigned_sales_id.username eq "<username>", user_id.username eq ...), không tra id trước. KHÔNG BAO GIỜ đặt tên người, tên khách hay mã vào cột uuid.
- Chỉ có TÊN nhân viên (vd "nhân viên Hiếu"): lượt 1 tra user_profiles (select user_id, user_id.username, user_id.is_active, last_name, first_name; filter first_name contains tên đó); đọc kết quả rồi lượt 2 lọc bảng chính bằng cột trỏ tới auth_users, eq user_id vừa nhận. Không gọi song song, không viết giá trị giữ chỗ. Trùng tên: hỏi hiện tại thì bỏ người is_active false, còn nhiều thì hỏi lại (kèm họ tên, username); 0 người: nói không tìm thấy.
- contains không phân biệt hoa thường nhưng PHÂN BIỆT dấu tiếng Việt: giữ đúng chữ người dùng gõ; 0 kết quả với chữ không dấu thì gợi ý gõ có dấu.
- Giá trị trạng thái/loại/vai trò: lấy từ crm_schema (cột:kiểu=a|b|c, known_values, note), so cả giá trị và nhãn; KHÔNG tự dịch hay đoán mã. Không khớp mục nào thì nói không có (kèm danh sách), không trả lời "0". Chưa biết giá trị: aggregate dimensions=[cột], metrics=[count] để xem.
- Ngày: kỳ thời gian luôn đặt ở date_range. Tương đối: preset (today, this_week, this_month, last_month, this_year...). "tháng N": preset=month, month=N (year=null: tháng N gần nhất tính tới hôm nay; câu hỏi nêu năm thì điền year). "năm YYYY": preset=year, year=YYYY. Khoảng ngày tuỳ ý: preset=custom + from_date/to_date (bao gồm cả hai đầu). CHỈ đặt date_range khi câu hỏi nêu một kỳ (hôm nay, tuần này, tháng 10, năm nay...). "hiện tại", "hiện có", "đang có", "tới giờ" hỏi trạng thái bây giờ, không phải kỳ: date_range = null. Điều kiện ngày thứ hai trên cột ngày khác (vd tạo tháng 10 nhưng đóng tháng 11): filter contains "YYYY-MM" trên cột đó; filter ngày kiểu khác bị từ chối. Nhóm theo kỳ: dimensions cột_day/cột_month/cột_year (customers: created_day/created_month/created_year).
- Xoá mềm: CRM tự loại dòng đã xoá; không thêm filter deleted_at, trừ bảng có crm_schema.deleted_at ghi "KẾT THÚC".
- Giờ: thời điểm trong rows là giờ Việt Nam; date_range và cột_day/_month/_year cắt theo ngày UTC (ranh giới 07:00 giờ Việt Nam): chỉ nói khi hỏi một ngày hay khung giờ cụ thể.
- hidden_columns: khoá/bí mật bị ẩn, không truy vấn được; nói rõ là không được phép xem.
- Lỗi: crm_query_invalid, tool_invalid_args → sửa đúng chỗ detail nêu rồi gọi lại; crm_forbidden → không có quyền, nói thẳng, không thử lại; crm_auth_failed → cần đăng nhập lại; crm_unavailable → thu hẹp điều kiện, thử lại một lần.

Đọc output:
- applied.filters có "(mặc định: ...)": điều kiện hệ thống tự thêm (vd không tính khách spam); nêu trong câu trả lời, không tự đặt lại filter đó; cần tính cả phần bị loại thì include_inactive=true. applied.ignored: phần bị bỏ hoặc sửa; kiểm kết quả vẫn đúng ý câu hỏi.
- Danh sách: nêu total; has_more thì đề nghị xem tiếp (gọi lại với offset = next_offset). Thống kê: totals là tổng toàn bộ.
- rows rỗng: không có dữ liệu thỏa điều kiện; kiểm lại filter (tên vào cột uuid? sai giá trị? thừa date_range?) trước khi kết luận.
- Cuối câu trả lời ghi ngắn: bảng, kỳ đã dùng có tháng/năm (vd "tháng 12/2025"), điều kiện lọc chính và giả định nghiệp vụ (vd "bán được" = thiết bị giao cho khách; "nhân viên sales" = người có vai trò sales, tài khoản còn dùng). Không nói "hiện tại" nếu chưa lọc trạng thái hiện tại.
- Chưa hỗ trợ OR/NOT, so sánh >/<, HAVING, join cha → con: tách nhiều query rồi tổng hợp (vd "khách chưa có máy": danh sách khách, rồi product_items dimensions=[customer_id], so hai danh sách khi cả hai không has_more), hoặc nói rõ chưa làm được.
- Không in JSON query hay tên API trừ khi được hỏi."""

CATALOG_PREFERENCE = (
    "\n- Câu hỏi crm_report/crm_records trả lời được (phiếu hỗ trợ, khách hàng, lần giao phiếu, "
    "thiết bị giao cho khách) ưu tiên hai tool đó; crm_query cho phần còn lại."
)


class AppliedDateRange(SystemModel):
    field: str
    from_date: str
    to_date: str
    timezone: str


class AppliedRawQuery(SystemModel):
    dataset: str
    mode: Literal["list", "aggregate"]
    filters: list[str]
    date_range: AppliedDateRange | None
    order_by: list[str]
    limit: int
    offset: int
    ignored: list[str] = Field(default_factory=list)


class QueryOutput(ToolOutput):
    applied: AppliedRawQuery
    columns: list[str]
    rows: list[dict[str, Any]] = Field(default_factory=list)
    returned: int
    total: int | None           # danh sách: số bản ghi thỏa điều kiện; thống kê: None
    totals: dict[str, Any] | None = None   # thống kê có dimension: tổng toàn bộ
    has_more: bool
    next_offset: int | None

    def to_llm(self, budget_tokens: int, count: Callable[[str], int]) -> dict[str, Any]:
        """Giữ phần mô tả; bỏ dòng cuối tới khi vừa budget."""
        payload = self.model_dump(mode="json")
        rows = payload["rows"]
        budget = budget_tokens - _TRUNCATION_MARGIN_TOKENS
        kept = len(rows)
        while kept and count(_j({**payload, "rows": rows[:kept]})) > budget:
            kept -= 1
        if kept < len(rows):
            payload["rows"] = rows[:kept]
            payload["truncated"] = True
            payload["omitted_rows"] = len(rows) - kept
        return payload


class QueryTurnState(ToolTurnState):
    """Các lần gọi crm_query trong lượt: lần thử thứ mấy, kết quả từng lần (giám sát việc LLM
    phải sửa query hoặc ra rỗng; chỉ metadata, ghi lên root span)."""

    attempts: int = 0
    crm_queries: int = 0        # lần thật sự gửi CRM (không tính lần bị compile/validate chặn)
    outcomes: list[str] = Field(default_factory=list)


def _begin_attempt(context: ToolContext) -> int:
    state = context.turn_state(QueryTurnState)
    state.attempts += 1
    return state.attempts


def _finish_attempt(context: ToolContext, outcome: QueryOutcome) -> None:
    state = context.turn_state(QueryTurnState)
    state.outcomes = [*state.outcomes, outcome]
    current_span().set(outcome=outcome)
    set_root(crm_query_attempts=state.attempts, crm_query_outcomes=state.outcomes)


def _value_count(value: object) -> int:
    if value is None:
        return 0
    return len(value) if isinstance(value, list) else 1


def query_shape(query: RawQuery) -> dict[str, object]:
    """Thuộc tính trace: bảng, cột, toán tử, số giá trị; không có giá trị filter."""
    date_range = query.date_range
    return {
        "dataset": query.dataset,
        "mode": query.mode,
        "select": list(query.select),
        "dimensions": list(query.dimensions),
        "metrics": list(query.metrics),
        "filters": [f"{item.field} {item.op}" for item in query.filters],
        "filter_value_counts": [str(_value_count(item.value)) for item in query.filters],
        "date_field": date_range.field if date_range else None,
        "date_preset": date_range.preset if date_range else None,
        "include_inactive": query.include_inactive,
        "limit": query.limit,
        "offset": query.offset,
    }


def build_crm_query_tool(
    client: CrmReportClient,
    cache: CrmSchemaCache,
    *,
    tz: tzinfo,
    with_catalog: bool = False,
    timeout_s: float = 20.0,
    audit: QueryAudit | None = None,
) -> ToolSpec:
    """audit: ghi cả giá trị query (sau cờ CRM_QUERY_AUDIT_LOG); None = tắt."""
    audit = audit or QueryAudit(enabled=False)

    def relation_target(table: str, column: str) -> str | None:
        """Bảng đích của khoá ngoại: schema sống đã cache (nếu có) trước, rồi index tĩnh."""
        live = cache.cached(table)
        if live is not None and column in live.relations:
            return live.relations[column]
        return static_relation(table, column)

    def column_type(table: str, column: str) -> str | None:
        """Kiểu gọn của cột: schema sống đã cache (nếu có) trước, rồi index tĩnh."""
        live = cache.cached(table)
        if live is not None and column in live.columns:
            return compact_type(live.columns[column])
        return static_column_type(table, column)

    def on_invalid_args(arguments_raw: str, detail: str, context: ToolContext) -> None:
        """Argument LLM gửi không validate được (không tới run): vẫn tính một lần thử."""
        attempt = _begin_attempt(context)
        _finish_attempt(context, "invalid_args")
        logger.info("crm_query invalid args attempt=%d", attempt)
        audit.record(
            request_id=context.parent_state.request_context.request_id,
            tool_call_id=context.tool_call_id, attempt=attempt, phase="invalid_args",
            outcome="invalid_args", arguments_raw=arguments_raw,
            error_code="tool_invalid_args", error_detail=detail,
        )

    async def run(arguments: RawQuery, context: ToolContext) -> QueryOutput:
        state = context.parent_state
        attempt = _begin_attempt(context)
        token, credential = crm_credential(state.principal)
        current_span().set(credential_source=credential, attempt=attempt, **query_shape(arguments))
        if not token:
            logger.warning("crm_query rejected: no acting user")
            _finish_attempt(context, "crm_error")
            raise ToolRejected("crm_user_missing", "no CRM user is attached to this conversation")
        common = {
            "request_id": state.request_context.request_id,
            "tool_call_id": context.tool_call_id,
            "attempt": attempt,
            "arguments": arguments.model_dump(mode="json"),
        }
        try:
            compiled = compile_raw(
                arguments, now=state.request_context.received_at, tz=tz,
                relation_target=relation_target, column_type=column_type,
                stated_years=stated_years(_user_texts(state), state.request_context.received_at, tz),
            )
        except RawQueryError as error:
            _finish_attempt(context, "rejected")
            logger.info(
                "crm_query rejected attempt=%d dataset=%s detail=%s", attempt, arguments.dataset, error,
            )
            audit.record(
                **common, phase="rejected", outcome="rejected",
                error_code="tool_invalid_args", error_detail=str(error),
            )
            raise ToolArgumentError(str(error)) from None
        date_from = compiled.date_range["from"] if compiled.date_range else None
        date_to = compiled.date_range["to"] if compiled.date_range else None
        # Ngày đã đổi ra và phần bị bỏ qua không phải PII: luôn vào span để thấy LLM hiểu sai contract.
        current_span().set(ignored=list(compiled.ignored), date_from=date_from, date_to=date_to)
        sent = {
            **common,
            "phase": "sent",
            "body": compiled.body,
            "count_body": compiled.count_body,
            "ignored": list(compiled.ignored),
            "date_from": date_from,
            "date_to": date_to,
        }
        turn = context.turn_state(QueryTurnState)
        if turn.crm_queries >= MAX_CRM_QUERIES_PER_TURN:
            detail = f"crm_query allows at most {MAX_CRM_QUERIES_PER_TURN} CRM queries per turn"
            _finish_attempt(context, "rejected")
            audit.record(**common, phase="rejected", outcome="rejected",
                         error_code=TOOL_CALL_LIMIT, error_detail=detail)
            raise ToolRejected(TOOL_CALL_LIMIT, detail)
        turn.crm_queries += 1       # tăng trước khi chờ CRM: call song song cùng bước đếm đúng
        bodies = [compiled.body, *([compiled.count_body] if compiled.count_body else [])]
        started_at = perf_counter()
        try:
            with span("query.fetch", "internal", dataset=arguments.dataset, queries=len(bodies)):
                pages = await query_all(client, bodies, token, on_invalid="invalid")
        except ToolRejected as error:
            failed = outcome_of_error(error.code)
            _finish_attempt(context, failed)
            audit.record(
                **sent, outcome=failed, error_code=error.code, error_detail=error.detail,
                latency_ms=_elapsed_ms(started_at),
            )
            raise
        output = _output(compiled, arguments.dataset, tz, pages[0].rows, pages[0].totals,
                         pages[1].rows if len(pages) > 1 else None)
        outcome: QueryOutcome = "ok" if output.returned else "empty"
        _finish_attempt(context, outcome)
        current_span().set(returned=output.returned, total=output.total, has_more=output.has_more)
        logger.info(
            "crm_query done attempt=%d outcome=%s credential=%s dataset=%s mode=%s returned=%d "
            "total=%s has_more=%s ignored=%s",
            attempt, outcome, credential, arguments.dataset, compiled.mode, output.returned,
            output.total, output.has_more, ",".join(compiled.ignored) or "-",
        )
        audit.record(
            **sent, outcome=outcome, returned=output.returned, total=output.total,
            latency_ms=_elapsed_ms(started_at),
        )
        return output

    return ToolSpec(
        name=CRM_QUERY_TOOL_NAME,
        description=CRM_QUERY_DESCRIPTION,
        input_model=RawQuery,
        output_model=QueryOutput,
        run=run,
        guide=CRM_QUERY_GUIDE + (CATALOG_PREFERENCE if with_catalog else ""),
        read_only=True,
        concurrency_safe=True,
        max_calls_per_turn=MAX_QUERY_ATTEMPTS_PER_TURN,
        timeout_s=timeout_s,
        on_invalid_args=on_invalid_args,
    )


def _output(
    compiled: CompiledRaw,
    dataset: str,
    tz: tzinfo,
    rows: list[dict[str, Any]],
    totals: dict[str, Any] | None,
    count_rows: list[dict[str, Any]] | None,
) -> QueryOutput:
    items = map_rows(compiled.columns, rows[:compiled.limit], tz)
    returned = len(items)
    if compiled.mode == "list":
        total = count_of(count_rows or [])
        has_more = total is not None and compiled.offset + returned < total
    else:
        total = None
        has_more = returned >= compiled.limit
    date_range = None
    if compiled.date_range is not None:
        date_range = AppliedDateRange(
            field=compiled.date_range["field"], from_date=compiled.date_range["from"],
            to_date=compiled.date_range["to"], timezone=str(tz),
        )
    order_by = [f"{item['field']} {item['dir']}" for item in compiled.body.get("order_by", [])]
    return QueryOutput(
        applied=AppliedRawQuery(
            dataset=dataset, mode=compiled.mode, filters=list(compiled.filters), date_range=date_range,
            order_by=order_by, limit=compiled.limit, offset=compiled.offset, ignored=list(compiled.ignored),
        ),
        columns=list(compiled.columns),
        rows=items,
        returned=returned,
        total=total,
        totals=map_totals(compiled.columns, totals),
        has_more=has_more,
        next_offset=compiled.offset + returned if has_more else None,
    )


def _user_texts(state: RunState) -> list[str]:
    """Câu hỏi hiện tại và các lượt người dùng trước (năm có thể nêu ở lượt trước: "trong số đó...")."""
    texts = [state.input.message.text or ""]
    if state.context is not None:
        texts += [item.content for item in state.context.conversation.history if item.role == "user"]
    return texts


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)


__all__ = ["CRM_QUERY_TOOL_NAME", "QueryOutput", "QueryTurnState", "build_crm_query_tool"]
