"""Tool của luồng agent: registry, contract và các tool đã đăng ký."""

from .base import ToolArgumentError, ToolContext, ToolOutcome, ToolOutput, ToolRejected, ToolSpec
from .crm_report import CRM_REPORT_TOOL_NAME, ReportOutput, build_crm_report_tool
from .product_docs import (
    PRODUCT_DOCS_TOOL_NAME,
    ProductDocsAskInput,
    ProductDocsAskOutput,
    build_product_docs_tool,
)
from .registry import ToolConfigurationError, ToolRegistry
from .schema import ToolSchemaError, to_provider_schema

__all__ = [
    "CRM_REPORT_TOOL_NAME",
    "PRODUCT_DOCS_TOOL_NAME",
    "ProductDocsAskInput",
    "ProductDocsAskOutput",
    "ReportOutput",
    "ToolArgumentError",
    "ToolConfigurationError",
    "ToolContext",
    "ToolOutcome",
    "ToolOutput",
    "ToolRegistry",
    "ToolRejected",
    "ToolSchemaError",
    "ToolSpec",
    "build_crm_report_tool",
    "build_product_docs_tool",
    "to_provider_schema",
]
