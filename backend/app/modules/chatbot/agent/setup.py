"""Dựng AgentRunner lúc startup; cấu hình không hợp lệ thì dừng khởi động."""

from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.modules.chatbot.providers.base import ToolCallingProvider
from app.modules.chatbot.providers.crm_api import CrmListClient, CrmReportClient
from app.modules.chatbot.reporting.datasets import DATASETS
from app.modules.chatbot.reporting.raw.audit import QueryAudit
from app.modules.chatbot.reporting.raw.schema import CrmSchemaCache
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
    build_crm_query_tool,
    build_crm_records_tool,
    build_crm_report_tool,
    build_crm_schema_tool,
    build_product_docs_tool,
)

from .runner import AgentLimits, AgentRunner


def build_agent_runner(
    provider: ToolCallingProvider,
    retriever: Retriever | None,
    settings: Settings,
    *,
    agent_provider: ToolCallingProvider | None = None,
) -> AgentRunner:
    """Đăng ký tool và kiểm tra capability của provider.

    provider: provider chung, dùng cho stage phân tích bên trong tool product_docs_ask.
    agent_provider: provider của vòng lặp agent (AGENT_MODEL); None = dùng provider chung.

    Raise ToolConfigurationError khi provider không hỗ trợ tool calling hoặc
    schema tool không chuyển được sang dialect của provider: lỗi phải lộ ra
    lúc startup, không phải giữa một lượt chat.
    """
    loop_provider = agent_provider or provider
    if not isinstance(loop_provider, ToolCallingProvider):
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
        # Reporting Query API cùng base URL với API danh sách.
        report_client = CrmReportClient(settings.crm_api_base_url, timeout_s=settings.crm_api_timeout_s)
        tz = ZoneInfo(settings.crm_report_timezone)
        with_catalog = settings.crm_tools in ("catalog", "both")
        if with_catalog:
            # Catalog ngữ nghĩa: dataset report_api (customers, support_assignments,
            # device_deliveries) dùng report_client, tickets dùng API danh sách.
            client = CrmListClient(
                settings.crm_api_base_url,
                timeout_s=settings.crm_api_timeout_s,
                max_items=settings.crm_report_max_items,
            )
            tools.append(build_crm_report_tool(
                client, DATASETS, tz=tz, report_client=report_client,
                timeout_s=settings.agent_tool_timeout_s,
            ))
            tools.append(build_crm_records_tool(
                client, DATASETS, tz=tz, report_client=report_client,
                timeout_s=settings.agent_tool_timeout_s,
            ))
        if settings.crm_tools in ("query", "both"):
            # Truy vấn thô mọi bảng (phương án C): LLM tự dựng query theo crm_schema.
            cache = CrmSchemaCache(report_client, ttl_s=settings.crm_schema_cache_s)
            tools.append(build_crm_schema_tool(cache, timeout_s=settings.agent_tool_timeout_s))
            tools.append(build_crm_query_tool(
                report_client, cache, tz=tz, with_catalog=with_catalog,
                timeout_s=settings.agent_tool_timeout_s,
                audit=QueryAudit(settings.crm_query_audit_log),
            ))

    registry = ToolRegistry(tools)
    registry.validate_for(loop_provider.capabilities)
    return AgentRunner(loop_provider, registry, AgentLimits.from_settings(settings))
