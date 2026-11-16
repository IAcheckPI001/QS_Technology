"""Phần dùng chung của các tool gọi CRM: credential của nhân viên và chạy query song song."""

import asyncio
import logging
from typing import Any

from app.modules.chatbot.providers.crm_api import (
    CrmApiError,
    CrmReportClient,
    InvalidQueryMode,
    ReportPage,
)
from app.modules.chatbot.schemas.security.principal import PrincipalContext

from .base import ToolRejected

logger = logging.getLogger(__name__)


def crm_credential(principal: PrincipalContext) -> tuple[str | None, str]:
    """Bearer gọi CRM và nguồn của nó (chỉ nguồn được log, không log giá trị).

    Ưu tiên crm_access_token; không có thì dùng acting_user_id (CRM backend cũ gửi
    user_id làm token).
    """
    if principal.crm_access_token is not None:
        return principal.crm_access_token.get_secret_value(), "token"
    return principal.acting_user_id, "user_id"


async def query_all(
    client: CrmReportClient,
    bodies: list[dict[str, Any]],
    token: str,
    *,
    on_invalid: InvalidQueryMode = "contract",
) -> list[ReportPage]:
    """Chạy các query song song; lỗi CRM đầu tiên thành ToolRejected (query còn lại bị huỷ)."""
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(client.query(body, token, on_invalid=on_invalid)) for body in bodies
            ]
    except* CrmApiError as errors:
        error = errors.exceptions[0]
        assert isinstance(error, CrmApiError)
        logger.warning("crm report fetch failed code=%s detail=%s", error.code, error.detail)
        raise ToolRejected(error.code, error.detail) from None
    return [task.result() for task in tasks]


__all__ = ["crm_credential", "query_all"]
