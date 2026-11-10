"""Dựng AgentRunner lúc startup; cấu hình không hợp lệ thì dừng khởi động."""

from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.modules.chatbot.providers.base import ToolCallingProvider
from app.modules.chatbot.providers.crm_api import CrmListClient, CrmReportClient
from app.modules.chatbot.reporting.datasets import DATASETS
from app.modules.chatbot.extraction.product_catalog import RegistryProductCatalog
from app.modules.chatbot.retrieval import Retriever
from app.modules.chatbot.stages.analysis_stage import AnalysisStage
from app.modules.chatbot.stages.catalog_lookup_stage import CatalogLookupStage
from app.modules.chatbot.stages.clarification_resume_stage import ClarificationResumeStage
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from app.modules.chatbot.stages.retrieval_pipeline import RetrievalPipeline
from app.modules.chatbot.tools import (
    ToolConfigurationError,
    ToolRegistry,
    ToolSpec,
    build_crm_records_tool,
    build_crm_report_tool,
    build_product_docs_tool,
)

from .runner import AgentLimits, AgentRunner


def build_agent_runner(
    provider: ToolCallingProvider,
    retriever: Retriever | None,
    settings: Settings,
) -> AgentRunner:
    """Đăng ký tool và kiểm tra capability của provider.

    Raise ToolConfigurationError khi provider không hỗ trợ tool calling hoặc
    schema tool không chuyển được sang dialect của provider: lỗi phải lộ ra
    lúc startup, không phải giữa một lượt chat.
    """
    if not isinstance(provider, ToolCallingProvider):
        raise ToolConfigurationError("provider does not implement tool calling")
    if retriever is None:
        raise ToolConfigurationError("product docs tool requires a configured retriever")
    pipeline = RetrievalPipeline(
        ClarificationResumeStage(),
        AnalysisStage(provider),  # type: ignore[arg-type]
        ExecutionStage(retriever=retriever),
        CatalogLookupStage(RegistryProductCatalog()),
    )
    tools: list[ToolSpec] = [
        build_product_docs_tool(pipeline, timeout_s=settings.agent_tool_timeout_s),
    ]
    if settings.crm_report_enabled:
        client = CrmListClient(
            settings.crm_api_base_url,
            timeout_s=settings.crm_api_timeout_s,
            max_items=settings.crm_report_max_items,
        )
        # Reporting Query API cùng base URL; dataset report_api (customers, support_assignments,
        # device_deliveries) dùng client này, tickets vẫn dùng API danh sách.
        report_client = CrmReportClient(settings.crm_api_base_url, timeout_s=settings.crm_api_timeout_s)
        tz = ZoneInfo(settings.crm_report_timezone)
        tools.append(build_crm_report_tool(
            client, DATASETS, tz=tz, report_client=report_client,
            timeout_s=settings.agent_tool_timeout_s,
        ))
        tools.append(build_crm_records_tool(
            client, DATASETS, tz=tz, report_client=report_client,
            timeout_s=settings.agent_tool_timeout_s,
        ))
    registry = ToolRegistry(tools)
    registry.validate_for(provider.capabilities)
    return AgentRunner(provider, registry, AgentLimits.from_settings(settings))
