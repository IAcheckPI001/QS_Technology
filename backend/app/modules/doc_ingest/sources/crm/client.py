"""Gọi API công khai của CRM bằng stdlib (`.venv-ingest` không có httpx; không thêm dependency)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

Fetcher = Callable[[str], bytes]


class CrmError(RuntimeError):
    pass


def http_fetcher(user_agent: str, timeout_s: float) -> Fetcher:
    def fetch(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:   # noqa: S310 - URL từ cấu hình
                return response.read()
        except urllib.error.HTTPError as exc:
            raise CrmError(f"HTTP {exc.code} khi gọi {strip_query(url)}") from None
        except urllib.error.URLError as exc:
            raise CrmError(f"không kết nối được {strip_query(url)}: {exc.reason}") from None

    return fetch


def strip_query(url: str) -> str:
    """Bỏ query (`exp`, `sig` của URL đã ký) trước khi in hoặc lưu."""
    return url.split("?", 1)[0]


def fetch_tree(fetch: Fetcher, api_url: str) -> dict[str, Any]:
    data = json.loads(fetch(api_url).decode("utf-8"))
    if not isinstance(data, dict) or "children" not in data:
        raise CrmError("cây tài liệu CRM không đúng dạng (thiếu `children`)")
    return data
