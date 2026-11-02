"""Product catalog: tìm model theo tiêu chí bằng dữ liệu sản phẩm có cấu trúc.

Hiện đọc bảng capabilities và coverage trong registry (code). Khi dữ liệu chuyển
sang database, thay RegistryProductCatalog bằng repository cùng Protocol, không
sửa stage hay tool.
"""

from typing import Protocol

from app.modules.chatbot.extraction.registry import REGISTRY as R
from app.modules.chatbot.extraction.validate_registry import (
    InterfaceMatch,
    display_name,
    models_with_interfaces,
)
from app.modules.chatbot.schemas.system import CatalogModel


class ProductCatalog(Protocol):
    def find_by_interfaces(
        self,
        required: list[str],
        excluded: list[str],
        match: InterfaceMatch,
    ) -> list[CatalogModel]: ...

    def all_models(self) -> list[CatalogModel]: ...


class RegistryProductCatalog:
    def find_by_interfaces(
        self,
        required: list[str],
        excluded: list[str],
        match: InterfaceMatch,
    ) -> list[CatalogModel]:
        return [_model(code) for code in models_with_interfaces(required, excluded, match)]

    def all_models(self) -> list[CatalogModel]:
        return [_model(code) for code in R["product_models"]]


def _model(code: str) -> CatalogModel:
    technical = R["coverage"].get("technical_docs")
    if technical is None:
        has_docs, interfaces = True, []
    else:
        has_docs = code in technical
        interfaces = list(technical[code]) if isinstance(technical, dict) and has_docs else []
    return CatalogModel(
        code=code,
        name=display_name(code),
        has_technical_docs=has_docs,
        documented_interfaces=interfaces,
    )
