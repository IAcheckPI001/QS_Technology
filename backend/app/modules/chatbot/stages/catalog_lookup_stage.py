"""CatalogLookupStage: tìm model theo tiêu chí bằng dữ liệu có cấu trúc (chỉ luồng agent).

Chạy giữa Analysis và Execution trong pipeline của tool `product_docs_ask`.
Sub-query discovery là `lookup.product_catalog` chưa có model và có điều kiện
(control_interface, excluded_control_interface hoặc unmapped_conditions):

- chỉ có điều kiện thuộc bảng capabilities: lọc bằng code, bỏ retrieval;
- còn điều kiện ngoài bảng: bảng chỉ thu hẹp ứng viên, vẫn retrieve catalog để
  agent kiểm chứng bằng nguồn;
- điều kiện thuộc bảng loại hết model: no_match, không retrieve.

Sub-query khác trong cùng lần gọi cần model mà model chưa có trong câu hỏi của
agent (thiếu model, xung đột ngữ cảnh, so sánh thiếu model, hoặc model kế thừa
từ lượt trước) được giữ lại với lý do `awaiting_models`: model của nó là kết quả
của discovery, agent gọi lại sau khi đọc catalog_match.
"""

from app.modules.chatbot.extraction.product_catalog import ProductCatalog
from app.modules.chatbot.extraction.registry import MAX_AUTO_LOOKUP_MODELS, REGISTRY as R
from app.modules.chatbot.extraction.validate_registry import models_in_text
from app.modules.chatbot.schemas.system import (
    Analysis,
    CatalogConditions,
    CatalogMatch,
    CatalogModel,
    CatalogNextAction,
    ClarificationPlan,
    Route,
    RunState,
    SubQueryAnalysis,
    SubQueryClarification,
)

DISCOVERY_INTENT = "lookup.product_catalog"
AWAITING_MODELS = "awaiting_models"
# Lý do hỏi lại nghĩa là "chưa biết model": trong lần gọi có discovery, model đó là kết quả tìm.
_MODEL_GAP_REASONS = frozenset({
    "missing_product_model",
    "context_conflict",
    "insufficient_models_for_comparison",
})


class CatalogLookupStage:
    name = "catalog_lookup_stage"

    def __init__(self, catalog: ProductCatalog) -> None:
        self._catalog = catalog

    def execute(self, state: RunState) -> RunState:
        analysis = state.analysis
        if analysis is None or state.context is None:
            return state
        discovery = next((sq for sq in analysis.sub_queries if _is_discovery(sq)), None)
        if discovery is None:
            return state

        entities = discovery.entities
        structured = bool(entities.control_interface or entities.excluded_control_interface)
        candidates = (
            self._catalog.find_by_interfaces(
                entities.control_interface,
                entities.excluded_control_interface,
                entities.interface_match,
            )
            if structured
            else self._catalog.all_models()
        )
        action = _next_action(structured, candidates, entities.unmapped_conditions)
        state.catalog_match = CatalogMatch(
            sub_query_id=discovery.id,
            applied=CatalogConditions(
                control_interface=entities.control_interface,
                excluded_control_interface=entities.excluded_control_interface,
                match=entities.interface_match,
            ),
            unmapped_conditions=entities.unmapped_conditions,
            models=candidates,
            next_action=action,
        )

        # Câu hỏi của agent phải tự đủ nghĩa và ghi mã model: model không có trong đó
        # là model kế thừa từ lượt trước, không phải model của kết quả tìm.
        question_models = set(models_in_text(state.context.query.origin))
        sub_queries = []
        for sub_query in analysis.sub_queries:
            if sub_query.id == discovery.id:
                sub_query = _discovery(sub_query, action, candidates, structured)
            elif _depends_on_discovery(sub_query, question_models):
                sub_query = _awaiting(sub_query, question_models)
            sub_queries.append(sub_query)
        state.analysis = _with_sub_queries(analysis, sub_queries)
        return state


def _is_discovery(sub_query: SubQueryAnalysis) -> bool:
    entities = sub_query.entities
    return (
        sub_query.intent == DISCOVERY_INTENT
        and sub_query.route is Route.RETRIEVE
        and not entities.product_models
        and bool(
            entities.control_interface
            or entities.excluded_control_interface
            or entities.unmapped_conditions
        )
    )


def _next_action(
    structured: bool,
    candidates: list[CatalogModel],
    unmapped_conditions: list[str],
) -> CatalogNextAction:
    if structured and not candidates:
        return "report_no_match"
    if unmapped_conditions:
        return "verify_with_sources"
    if len(candidates) <= MAX_AUTO_LOOKUP_MODELS:
        return "lookup_each"
    return "ask_selection"


def _discovery(
    sub_query: SubQueryAnalysis,
    action: CatalogNextAction,
    candidates: list[CatalogModel],
    structured: bool,
) -> SubQueryAnalysis:
    if action != "verify_with_sources":
        return sub_query.model_copy(update={"route": Route.CATALOG, "retrieval_scope": None})
    if not structured or sub_query.retrieval_scope is None:
        # Không có điều kiện thuộc bảng: không lọc theo model, để giữ cả chunk catalog chung.
        return sub_query
    scope = sub_query.retrieval_scope.model_copy(
        update={"model_filter": [model.code for model in candidates]}
    )
    return sub_query.model_copy(update={"retrieval_scope": scope})


def _depends_on_discovery(sub_query: SubQueryAnalysis, question_models: set[str]) -> bool:
    if sub_query.intent is None or R["intents"][sub_query.intent]["model_policy"] == "none":
        return False
    clarification = sub_query.clarification
    if clarification is not None and clarification.reason in _MODEL_GAP_REASONS:
        return True
    return any(model not in question_models for model in sub_query.entities.product_models)


def _awaiting(sub_query: SubQueryAnalysis, question_models: set[str]) -> SubQueryAnalysis:
    models = [model for model in sub_query.entities.product_models if model in question_models]
    return sub_query.model_copy(update={
        "entities": sub_query.entities.model_copy(update={"product_models": models}),
        "route": Route.CLARIFY,
        "retrieval_scope": None,
        "unsupported_models": [],
        "clarification": SubQueryClarification(reason=AWAITING_MODELS, blocking=True),
        "warnings": [*sub_query.warnings, AWAITING_MODELS],
    })


def _with_sub_queries(analysis: Analysis, sub_queries: list[SubQueryAnalysis]) -> Analysis:
    """Tính lại phần kế hoạch phụ thuộc route/clarification của các sub-query.

    Câu hỏi lại của lượt không lấy từ sub-query awaiting_models: đó không phải câu
    hỏi cho nhân viên mà là bước agent tự làm tiếp.
    """
    clarified = [
        sub_query
        for sub_query in sub_queries
        if sub_query.clarification is not None
        and sub_query.clarification.reason != AWAITING_MODELS
    ]
    clarified.sort(key=lambda sub_query: not sub_query.clarification.blocking)
    clarification = None
    if clarified:
        first = clarified[0]
        clarification = ClarificationPlan(
            sub_query_id=first.id,
            **first.clarification.model_dump(),
        )
    return analysis.model_copy(update={
        "sub_queries": sub_queries,
        "answer_sub_query_ids": [sq.id for sq in sub_queries if sq.route is Route.RETRIEVE],
        "no_docs_sub_query_ids": [sq.id for sq in sub_queries if sq.route is Route.NO_DOCS],
        "clarification": clarification,
    })
