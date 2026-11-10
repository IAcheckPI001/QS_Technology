"""Tool `crm_report`: số liệu tổng hợp từ CRM theo ReportQuery.

LLM chỉ điền ReportQuery (tên logic trong catalog). Tool kiểm tra query, gọi API
CRM bằng token của nhân viên (CRM phân quyền theo token), rồi engine lọc, nhóm,
tính metric và delta. LLM nhận kết quả đã tổng hợp, không nhận bản ghi thô;
`subject`/`description` bị bỏ ngay khi parse.
"""

import json
import logging
from collections.abc import Callable, Mapping
from datetime import tzinfo
from typing import Any

from pydantic import Field

from app.core.tracing import current_span, span
from app.modules.chatbot.providers.crm_api import CrmApiError, CrmListClient
from app.modules.chatbot.reporting.catalog import DatasetSpec
from app.modules.chatbot.reporting.engine import run_report
from app.modules.chatbot.reporting.validate import NormalizedQuery, ReportQueryError, validate_query
from app.modules.chatbot.schemas.default import SystemModel
from app.modules.chatbot.schemas.security.principal import PrincipalContext
from app.modules.chatbot.schemas.system.report import ReportQuery

from .base import ToolArgumentError, ToolContext, ToolOutput, ToolRejected, ToolSpec

CRM_REPORT_TOOL_NAME = "crm_report"

logger = logging.getLogger(__name__)

_TRUNCATION_MARGIN_TOKENS = 32

CRM_REPORT_DESCRIPTION = (
    "Số liệu tổng hợp từ CRM (đếm, thống kê, xu hướng, tồn đọng) trong phạm vi dữ liệu tài khoản "
    "nhân viên được phép xem. Dùng cho câu hỏi bao nhiêu/nhiều nhất/trung bình/so sánh theo kỳ về "
    "phiếu hỗ trợ (ticket) theo trạng thái, model, loại yêu cầu, nhân viên xử lý, khách hàng. "
    "Không dùng cho thông tin kỹ thuật sản phẩm (dùng product_docs_ask). Backend tự lọc, nhóm và "
    "tính: chỉ chọn metrics, dimensions, filters (AND), date_range, time_grain, sort, limit."
)

CRM_REPORT_GUIDE = """Gọi tool:
- Ngày tương đối ("tháng này", "tuần trước") dùng date_range.preset. Kỳ cụ thể dùng start/end, end là ngày đầu kỳ sau (không bao gồm), vd tháng 10/2026: start 2026-10-01, end 2026-11-01.
- So sánh các kỳ (tháng 9 với tháng 10): một call, date_range bao cả các kỳ + time_grain; backend trả change.delta/delta_pct so với kỳ liền trước.
- "Đang mở/tồn đọng": status_group = active hoặc metric active_ticket_count. "Mở quá N ngày": thêm filter age_hours gt N*24.
- Không có date_range: tính trên toàn bộ dữ liệu.

Đọc output:
- Giữ nguyên số liệu; không tự cộng/trừ/chia hay tự tính tỉ lệ. Dùng change cho chênh lệch giữa các kỳ.
- Nêu khoảng thời gian (applied.date_range, giờ Việt Nam) và các filter đã áp dụng; số liệu là trong phạm vi dữ liệu tài khoản này được xem.
- Giá trị null của avg/max: không có phiếu thỏa điều kiện. total_groups > row_count: còn nhóm chưa hiện.
- source_truncated: true: dữ liệu lấy về chưa đủ, nói rõ số liệu có thể thiếu.
- Trạng thái in_progress chỉ cập nhật khi có người mở chi tiết phiếu nên pending/in_progress có thể lệch thực tế; thời gian tạo→đóng của phiếu mở lại tính từ lúc tạo ban đầu.
- Chưa hỗ trợ: danh sách/chi tiết từng phiếu, nội dung phiếu, quá hạn/SLA. Nói rõ là chưa có dữ liệu cho yêu cầu đó.
- Lỗi crm_auth_failed: không truy cập được dữ liệu CRM bằng tài khoản này. crm_unavailable: CRM tạm thời không phản hồi."""


class AppliedDateRange(SystemModel):
    field: str
    start: str | None
    end: str | None
    timezone: str


class AppliedQuery(SystemModel):
    """Query sau chuẩn hóa: ngày tuyệt đối, giá trị đã chuẩn hóa, limit thực, filter hệ thống."""

    dataset: str
    metrics: list[str]
    dimensions: list[str]
    filters: list[str]
    system_filters: list[str]
    date_range: AppliedDateRange | None
    time_grain: str | None
    sort: list[str]
    limit: int | None


class ReportOutput(ToolOutput):
    applied: AppliedQuery
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int
    total_groups: int
    matched_count: int          # bản ghi thỏa mọi filter
    fetched_count: int          # bản ghi lấy từ CRM
    skipped_count: int          # bản ghi sai định dạng bị bỏ
    source_truncated: bool

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


def catalog_text(datasets: Mapping[str, DatasetSpec]) -> str:
    """Catalog cho description: trường, giá trị enum và metric của từng dataset."""
    lines: list[str] = []
    for spec in datasets.values():
        lines.append(f"Dataset {spec.name}: {spec.description}")
        lines.append("Metrics: " + "; ".join(
            f"{name}: {metric.description.rstrip('.')}" for name, metric in spec.metrics.items()
        ))
        fields = []
        for name, field in spec.fields.items():
            use = "/".join(
                part for part, ok in (("filter", field.filterable), ("dimension", field.groupable)) if ok
            )
            values = f" [{', '.join(field.values)}]" if field.values else ""
            fields.append(f"{name} ({field.type}, {use}){values}: {field.description.rstrip('.')}")
        lines.append("Fields: " + "; ".join(fields))
        lines.append(
            f"Date fields: {', '.join(spec.date_fields)} (mặc định {spec.default_date_field})."
        )
    print(f"Date fields:\n" + "\n".join(lines))
    return "\n".join(lines)


def build_crm_report_tool(
    client: CrmListClient,
    datasets: Mapping[str, DatasetSpec],
    *,
    tz: tzinfo,
    timeout_s: float = 20.0,
) -> ToolSpec:
    datasets = dict(datasets)

    async def run(arguments: ReportQuery, context: ToolContext) -> ReportOutput:
        state = context.parent_state
        token, credential = crm_credential(state.principal)
        # Cấu trúc truy vấn LLM yêu cầu, ghi trước khi validate để lần gọi sai vẫn thấy được.
        current_span().set(credential_source=credential, **query_shape(arguments))
        if not token:
            logger.warning("crm_report rejected: no acting user")
            raise ToolRejected("crm_user_missing", "no CRM user is attached to this conversation")
        try:
            with span("report.validate", "internal", dataset=arguments.dataset):
                query = validate_query(arguments, datasets, now=state.request_context.received_at, tz=tz)
        except ReportQueryError as error:
            logger.info("crm_report invalid query dataset=%s detail=%s", arguments.dataset, error)
            raise ToolArgumentError(str(error)) from None
        logger.info(
            "crm_report query credential=%s dataset=%s metrics=%s dimensions=%s filters=%s date=%s..%s grain=%s",
            credential, query.dataset.name, ",".join(query.metrics), ",".join(query.dimensions) or "-",
            "; ".join(c.describe() for c in query.filters) or "-",
            query.start.isoformat() if query.start else "-",
            query.end.isoformat() if query.end else "-", query.time_grain or "-",
        )
        try:
            with span("report.fetch", "internal", dataset=query.dataset.name) as fetch_span:
                page = await client.fetch_all(query.dataset.source_path, token)
                fetch_span.set(items=len(page.items), total=page.total, truncated=page.truncated)
        except CrmApiError as error:
            logger.warning("crm_report fetch failed code=%s detail=%s", error.code, error.detail)
            raise ToolRejected(error.code, error.detail) from None
        # Cấu trúc truy vấn đã nằm trên span tool (query_shape); ở đây chỉ số đếm.
        with span("report.engine", "internal", filters=len(query.filters)) as engine_span:
            records, skipped = query.dataset.parse(page.items)
            result = run_report(query, records)
            engine_span.set(
                parsed=len(records), skipped=skipped, matched=result.matched_count,
                rows=len(result.rows), groups=result.total_groups,
            )
        current_span().set(result_rows=len(result.rows), source_truncated=page.truncated)
        logger.info(
            "crm_report done fetched=%d parsed=%d skipped=%d matched=%d rows=%d groups=%d truncated=%s",
            len(page.items), len(records), skipped, result.matched_count, len(result.rows),
            result.total_groups, page.truncated,
        )
        return ReportOutput(
            applied=applied(query, tz),
            rows=result.rows,
            row_count=len(result.rows),
            total_groups=result.total_groups,
            matched_count=result.matched_count,
            fetched_count=len(page.items),
            skipped_count=skipped,
            source_truncated=page.truncated,
        )

    return ToolSpec(
        name=CRM_REPORT_TOOL_NAME,
        description=f"{CRM_REPORT_DESCRIPTION}\n{catalog_text(datasets)}",
        input_model=ReportQuery,
        output_model=ReportOutput,
        run=run,
        guide=CRM_REPORT_GUIDE,
        read_only=True,
        concurrency_safe=True,
        max_calls_per_turn=4,
        timeout_s=timeout_s,
    )


def crm_credential(principal: PrincipalContext) -> tuple[str | None, str]:
    """Bearer gọi CRM và nguồn của nó (chỉ nguồn được log, không log giá trị).

    Ưu tiên crm_access_token; không có thì dùng acting_user_id (CRM backend cũ gửi
    user_id làm token).
    """
    if principal.crm_access_token is not None:
        return principal.crm_access_token.get_secret_value(), "token"
    return principal.acting_user_id, "user_id"


def query_shape(query: ReportQuery) -> dict[str, object]:
    """Thuộc tính trace của ReportQuery: tên trường/enum của catalog, không có giá trị filter
    hay ngày cụ thể."""
    date_range = query.date_range
    return {
        "dataset": query.dataset,
        "metrics": list(query.metrics),
        "dimensions": list(query.dimensions),
        "filter_fields": [item.field for item in query.filters],
        "date_field": date_range.field if date_range else None,
        "date_mode": _date_mode(date_range),
        "date_preset": date_range.preset if date_range else None,
        "time_grain": query.time_grain,
        "sort_fields": [item.field for item in query.sort],
        "limit": query.limit,
    }


def _date_mode(date_range) -> str | None:
    """`preset` | `custom` (start/end) | `preset+custom` (cả hai, validate sẽ từ chối)."""
    if date_range is None:
        return None
    has_dates = date_range.start is not None or date_range.end is not None
    if date_range.preset is not None:
        return "preset+custom" if has_dates else "preset"
    return "custom" if has_dates else None


def applied(query: NormalizedQuery, tz: tzinfo) -> AppliedQuery:
    date_range = None
    if query.date_field is not None:
        date_range = AppliedDateRange(
            field=query.date_field,
            start=query.start.isoformat() if query.start else None,
            end=query.end.isoformat() if query.end else None,
            timezone=str(tz),
        )
    return AppliedQuery(
        dataset=query.dataset.name,
        metrics=list(query.metrics),
        dimensions=list(query.dimensions),
        filters=[condition.describe() for condition in query.filters],
        system_filters=[label for label, _ in query.dataset.system_filters],
        date_range=date_range,
        time_grain=query.time_grain,
        sort=[f"{field} {direction}" for field, direction in query.sort],
        limit=query.limit if query.dimensions else None,
    )


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
