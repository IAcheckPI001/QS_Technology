"""Tool của luồng agent: registry, contract và các tool đã đăng ký."""

from .base import ToolArgumentError, ToolContext, ToolOutcome, ToolOutput, ToolRejected, ToolSpec
from .crm_query import CRM_QUERY_TOOL_NAME, QueryOutput, build_crm_query_tool
from .crm_records import CRM_RECORDS_TOOL_NAME, RecordsOutput, build_crm_records_tool
from .crm_report import CRM_REPORT_TOOL_NAME, ReportOutput, build_crm_report_tool
from .crm_schema import CRM_SCHEMA_TOOL_NAME, SchemaOutput, build_crm_schema_tool
from .product_docs import (
    PRODUCT_DOCS_TOOL_NAME,
    ProductDocsAskInput,
    ProductDocsAskOutput,
    build_product_docs_tool,
)
from .registry import ToolConfigurationError, ToolRegistry
from .schema import ToolSchemaError, to_provider_schema

__all__ = [
    "CRM_QUERY_TOOL_NAME",
    "CRM_RECORDS_TOOL_NAME",
    "CRM_REPORT_TOOL_NAME",
    "CRM_SCHEMA_TOOL_NAME",
    "PRODUCT_DOCS_TOOL_NAME",
    "ProductDocsAskInput",
    "ProductDocsAskOutput",
    "QueryOutput",
    "RecordsOutput",
    "ReportOutput",
    "SchemaOutput",
    "ToolArgumentError",
    "ToolConfigurationError",
    "ToolContext",
    "ToolOutcome",
    "ToolOutput",
    "ToolRegistry",
    "ToolRejected",
    "ToolSchemaError",
    "ToolSpec",
    "build_crm_query_tool",
    "build_crm_records_tool",
    "build_crm_report_tool",
    "build_crm_schema_tool",
    "build_product_docs_tool",
    "to_provider_schema",
]
