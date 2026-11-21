"""Ký URL cho ảnh tài liệu trong Supabase Storage (bucket private, D-014 giai đoạn B).

Khóa service role chỉ dùng ở đây (backend) và không bao giờ ghi log hay gửi cho client; client chỉ nhận URL ký
ngắn hạn. Gọi theo lô một lần cho mỗi bucket. Lỗi mạng hoặc từng đường dẫn không ký được → bỏ ảnh đó, câu trả lời
vẫn chạy.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence

import httpx

from app.core.config import Settings
from app.modules.chatbot.schemas.system import ChunkAsset

logger = logging.getLogger(__name__)

AssetKey = tuple[str, str]   # (bucket, path)


class AssetSigner:
    def __init__(
        self,
        base_url: str,
        service_key: str,
        *,
        ttl_s: int = 900,
        timeout_s: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {service_key}", "apikey": service_key}
        self._ttl_s = ttl_s
        self._client = client or httpx.AsyncClient(timeout=timeout_s)

    @classmethod
    def from_settings(cls, settings: Settings) -> "AssetSigner | None":
        """None khi cờ tắt hoặc thiếu cấu hình: chat chạy như cũ, không có event `sources`."""
        if not (settings.chat_sources_enabled and settings.supabase_url and settings.supabase_service_role_key):
            return None
        return cls(settings.supabase_url, settings.supabase_service_role_key, ttl_s=settings.asset_url_ttl_s)

    async def sign(self, assets: Iterable[ChunkAsset]) -> dict[AssetKey, str]:
        by_bucket: dict[str, list[str]] = {}
        for asset in assets:
            paths = by_bucket.setdefault(asset.bucket, [])
            if asset.path not in paths:
                paths.append(asset.path)
        signed: dict[AssetKey, str] = {}
        for bucket, paths in by_bucket.items():
            signed.update(await self._sign_bucket(bucket, paths))
        return signed

    async def _sign_bucket(self, bucket: str, paths: Sequence[str]) -> dict[AssetKey, str]:
        url = f"{self._base}/storage/v1/object/sign/{bucket}"
        try:
            response = await self._client.post(
                url, headers=self._headers, json={"expiresIn": self._ttl_s, "paths": list(paths)})
            response.raise_for_status()
            rows = response.json()
        except Exception as error:   # không ghi URL/khóa; chỉ loại lỗi
            logger.warning("asset signing failed bucket=%s paths=%d error=%s", bucket, len(paths), type(error).__name__)
            return {}
        signed: dict[AssetKey, str] = {}
        for row in rows if isinstance(rows, list) else []:
            path, relative = row.get("path"), row.get("signedURL")
            if row.get("error") or not path or not relative:
                continue
            signed[(bucket, path)] = relative if relative.startswith("http") else self._absolute(relative)
        return signed

    def _absolute(self, relative: str) -> str:
        prefix = "" if relative.startswith("/storage/v1") else "/storage/v1"
        return f"{self._base}{prefix}{relative}"

    async def close(self) -> None:
        await self._client.aclose()
