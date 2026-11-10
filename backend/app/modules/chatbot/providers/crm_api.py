"""Client đọc danh sách bản ghi từ CRM backend cho báo cáo.

`Authorization: Bearer <token>`: CRM phân quyền và giới hạn phạm vi dữ liệu theo
token; dịch vụ AI không lọc quyền thêm. Không log token, không log nội dung bản ghi.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.tracing import span

logger = logging.getLogger(__name__)

PAGE_SIZE = 100


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
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            # Domain ngrok của môi trường kiểm thử trả trang cảnh báo HTML nếu thiếu header này.
            "ngrok-skip-browser-warning": "1",
        }
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
        if response.status_code in (401, 403):
            logger.warning(
                "crm list rejected credentials path=%s status=%d error=%s",
                path, response.status_code, _error_message(response),
            )
            raise CrmApiError("crm_auth_failed", "CRM rejected the user's credentials")
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


def _error_message(response: httpx.Response) -> str:
    """Thông báo lỗi CRM trả về (vd "session has been revoked"), cắt ngắn; không có token."""
    try:
        payload = response.json()
    except ValueError:
        return "-"
    message = payload.get("error") if isinstance(payload, dict) else None
    return str(message)[:200] if message else "-"
