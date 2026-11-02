"""Dựng AgentRunner lúc startup; cấu hình không hợp lệ thì dừng khởi động."""

from app.core.config import Settings
from app.modules.chatbot.providers.base import ToolCallingProvider
from app.modules.chatbot.extraction.product_catalog import RegistryProductCatalog
from app.modules.chatbot.retrieval import Retriever
from app.modules.chatbot.stages.analysis_stage import AnalysisStage
from app.modules.chatbot.stages.catalog_lookup_stage import CatalogLookupStage
from app.modules.chatbot.stages.clarification_resume_stage import ClarificationResumeStage
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from app.modules.chatbot.stages.retrieval_pipeline import RetrievalPipeline
from app.modules.chatbot.tools import ToolConfigurationError, ToolRegistry, build_product_docs_tool

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
    registry = ToolRegistry([
        build_product_docs_tool(pipeline, timeout_s=settings.agent_tool_timeout_s),
    ])
    registry.validate_for(provider.capabilities)
    return AgentRunner(provider, registry, AgentLimits.from_settings(settings))
