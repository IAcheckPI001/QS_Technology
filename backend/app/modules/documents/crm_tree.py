"""Đọc cây tài liệu công khai của CRM để lấy link xem/tải PDF mới (URL đã ký, hết hạn) khi người dùng bấm.

Cache cây trong bộ nhớ `ttl_s` giây (mặc định 300) để nhiều lần bấm không gọi CRM liên tục; URL ký của CRM sống lâu
hơn TTL. Không lưu URL ký vào DB và không ghi vào log (chỉ in đường dẫn không có query).
"""

from __future__ import annotations

import asyncio
import logging
from time import monotonic
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

PdfMode = Literal["view", "download"]


class CrmTreeError(RuntimeError):
    """CRM không trả được cây (mạng, HTTP lỗi, sai định dạng)."""


class CrmDocumentTree:
    def __init__(self, tree_url: str, base_url: str, *, ttl_s: float = 300.0, timeout_s: float = 15.0,
                 client: httpx.AsyncClient | None = None) -> None:
        self._tree_url = tree_url
        self._base = base_url.rstrip("/")
        self._ttl_s = ttl_s
        self._client = client or httpx.AsyncClient(timeout=timeout_s, headers={"User-Agent": "qs-workspace/documents"})
        self._cached: tuple[float, dict[str, dict[str, Any]]] | None = None
        self._lock = asyncio.Lock()

    async def _nodes(self) -> dict[str, dict[str, Any]]:
        async with self._lock:
            if self._cached and monotonic() - self._cached[0] < self._ttl_s:
                return self._cached[1]
            try:
                response = await self._client.get(self._tree_url)
                response.raise_for_status()
                tree = response.json()
            except (httpx.HTTPError, ValueError) as error:
                logger.warning("crm document tree failed url=%s error=%s", self._tree_url, type(error).__name__)
                raise CrmTreeError("không đọc được cây tài liệu CRM") from None
            if not isinstance(tree, dict) or "children" not in tree:
                raise CrmTreeError("cây tài liệu CRM không đúng dạng")
            nodes: dict[str, dict[str, Any]] = {}

            def walk(node: dict[str, Any]) -> None:
                if node.get("node_type") == "document" and node.get("id"):
                    nodes[str(node["id"])] = node
                for child in node.get("children") or []:
                    if isinstance(child, dict):
                        walk(child)

            walk(tree)
            self._cached = (monotonic(), nodes)
            return nodes

    async def pdf_url(self, crm_id: str, mode: PdfMode) -> str | None:
        """URL tuyệt đối (đã ký) để xem hoặc tải PDF; None khi tài liệu không còn trên CRM."""
        node = (await self._nodes()).get(crm_id)
        if node is None:
            return None
        path = node.get("view_pdf_url" if mode == "view" else "download_pdf_url")
        if not isinstance(path, str) or not path:
            return None
        return path if path.startswith("http") else f"{self._base}{path}"

    async def close(self) -> None:
        await self._client.aclose()
