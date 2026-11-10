"""Client đọc dữ liệu CRM cho báo cáo: API danh sách bản ghi và Reporting Query API.

`Authorization: Bearer <token>`: CRM phân quyền và giới hạn phạm vi dữ liệu theo
token; dịch vụ AI không lọc quyền thêm. Không log token, không log nội dung bản ghi.

Mã lỗi gửi agent: 401 → `crm_auth_failed` (token sai/hết hạn), 403 → `crm_forbidden`
(tài khoản không có quyền với dữ liệu này), 400 của Reporting API →
`crm_report_contract_error` (catalog lệch schema CRM: lỗi phía dịch vụ AI, không do LLM),
còn lại → `crm_unavailable`.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.tracing import span

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
REPORT_QUERY_PATH = "/api/v1/reports/query"
REPORT_MAX_ROWS = 1000          # trần `limit` của POST /reports/query


class CrmApiError(Exception):
    """Lỗi gọi CRM; `code` trả cho agent, chi tiết kỹ thuật chỉ vào log."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ListPage:
    items: list[dict[str, Any]]
    total: int | None           # CRM báo tổng số bản ghi (None nếu không có)
    truncated: bool             # dừng ở max_items trước khi lấy hết


class CrmListClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float,
        max_items: int,
        page_size: int = PAGE_SIZE,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_items = max_items
        self._page_size = page_size
        self._transport = transport

    async def fetch_all(self, path: str, token: str) -> ListPage:
        """Lấy lần lượt các trang `?limit=&offset=` tới khi đủ `total`, gặp trang thiếu, hoặc max_items."""
        headers = _headers(token)
        items: list[dict[str, Any]] = []
        total: int | None = None
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout_s,
            transport=self._transport,
        ) as client:
            while len(items) < self._max_items:
                limit = min(self._page_size, self._max_items - len(items))
                page, page_total = await self._page(client, path, limit, len(items))
                total = page_total if page_total is not None else total
                items.extend(page)
                if len(page) < limit or (total is not None and len(items) >= total):
                    break
        truncated = len(items) >= self._max_items and (total is None or total > len(items))
        logger.info(
            "crm list fetched path=%s items=%d total=%s truncated=%s",
            path, len(items), total, truncated,
        )
        return ListPage(items=items, total=total, truncated=truncated)

    async def _page(
        self,
        client: httpx.AsyncClient,
        path: str,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int | None]:
        try:
            with span("http.crm_list", "http", path=path, limit=limit, offset=offset) as http_span:
                response = await client.get(path, params={"limit": limit, "offset": offset})
                http_span.set(status_code=response.status_code)
                if response.status_code != 200:
                    http_span.fail(f"http_{response.status_code}")
        except httpx.TimeoutException:
            logger.warning("crm list timed out path=%s offset=%d", path, offset)
            raise CrmApiError("crm_unavailable", "CRM did not respond in time") from None
        except httpx.HTTPError as error:
            logger.warning("crm list request failed path=%s error=%s", path, type(error).__name__)
            raise CrmApiError("crm_unavailable", "CRM is unreachable") from None
        _raise_for_access(response, path)
        if response.status_code != 200:
            logger.warning(
                "crm list failed path=%s status=%d error=%s",
                path, response.status_code, _error_message(response),
            )
            raise CrmApiError("crm_unavailable", f"CRM returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            payload = None
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            logger.warning("crm list returned unexpected body path=%s", path)
            raise CrmApiError("crm_unavailable", "CRM returned an unexpected response")
        total = payload.get("total")
        return items, total if isinstance(total, int) and not isinstance(total, bool) else None


@dataclass(frozen=True)
class ReportPage:
    rows: list[dict[str, Any]]
    totals: dict[str, Any] | None
    truncated: bool             # số dòng chạm `limit` đã gửi: có thể còn dòng chưa lấy


class CrmReportClient:
    """`POST /api/v1/reports/query`: CRM dựng SQL tham số hoá từ JSON và chạy theo quyền của token.

    Request do `reporting/compile.py` sinh từ catalog, không do LLM viết; vì vậy 400 là lỗi
    cấu hình catalog (`crm_report_contract_error`), chi tiết chỉ vào log.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float,
        path: str = REPORT_QUERY_PATH,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._path = path
        self._transport = transport

    async def query(self, request: dict[str, Any], token: str) -> ReportPage:
        dataset = str(request.get("dataset"))
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=_headers(token),
                timeout=self._timeout_s,
                transport=self._transport,
            ) as client:
                with span("http.crm_report", "http", dataset=dataset) as http_span:
                    response = await client.post(self._path, json=request)
                    http_span.set(status_code=response.status_code)
                    if response.status_code != 200:
                        http_span.fail(f"http_{response.status_code}")
        except httpx.TimeoutException:
            logger.warning("crm report timed out dataset=%s", dataset)
            raise CrmApiError("crm_unavailable", "CRM did not respond in time") from None
        except httpx.HTTPError as error:
            logger.warning("crm report request failed dataset=%s error=%s", dataset, type(error).__name__)
            raise CrmApiError("crm_unavailable", "CRM is unreachable") from None
        _raise_for_access(response, self._path)
        if response.status_code == 400:
            # Spec do catalog sinh ra: CRM từ chối nghĩa là catalog lệch schema CRM.
            logger.error(
                "crm report rejected spec dataset=%s error=%s", dataset, _error_message(response),
            )
            raise CrmApiError(
                "crm_report_contract_error", "report definition does not match the CRM schema",
            )
        if response.status_code != 200:
            logger.warning(
                "crm report failed dataset=%s status=%d error=%s",
                dataset, response.status_code, _error_message(response),
            )
            raise CrmApiError("crm_unavailable", f"CRM returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            payload = None
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            logger.warning("crm report returned unexpected body dataset=%s", dataset)
            raise CrmApiError("crm_unavailable", "CRM returned an unexpected response")
        totals = payload.get("totals")
        limit = request.get("limit")
        truncated = isinstance(limit, int) and len(rows) >= limit
        logger.info("crm report fetched dataset=%s rows=%d truncated=%s", dataset, len(rows), truncated)
        return ReportPage(rows=rows, totals=totals if isinstance(totals, dict) else None, truncated=truncated)


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        # Domain ngrok của môi trường kiểm thử trả trang cảnh báo HTML nếu thiếu header này.
        "ngrok-skip-browser-warning": "1",
    }


def _raise_for_access(response: httpx.Response, path: str) -> None:
    if response.status_code == 401:
        logger.warning(
            "crm rejected credentials path=%s status=401 error=%s", path, _error_message(response),
        )
        raise CrmApiError("crm_auth_failed", "CRM rejected the user's credentials")
    if response.status_code == 403:
        logger.warning(
            "crm denied access path=%s status=403 error=%s", path, _error_message(response),
        )
        raise CrmApiError("crm_forbidden", "the user's CRM account may not read this data")


def _error_message(response: httpx.Response) -> str:
    """Thông báo lỗi CRM trả về (vd "session has been revoked"), cắt ngắn; không có token."""
    try:
        payload = response.json()
    except ValueError:
        return "-"
    message = payload.get("error") if isinstance(payload, dict) else None
    return str(message)[:200] if message else "-"
