"""Tool `product_docs_ask`: chạy lại pipeline tra cứu tài liệu hiện có cho một câu hỏi của agent.

Clarification → Analysis (intent/entity registry) → Catalog lookup (bảng
capabilities) → Execution (retrieval), không compose: agent tự viết câu trả lời
từ output này. Tool không ghi database.

Backend kiểm soát dữ liệu, agent quyết định bước tiếp:
- `catalog_match.next_action` cho biết bước kế tiếp hợp lệ sau khi tìm model;
- model trong câu hỏi phải có bằng chứng (nhân viên đã nhắc, ngữ cảnh phiên,
  kết quả tìm của lượt, hoặc nguồn agent trích qua `based_on_sources`).
"""

import json
import re
from collections.abc import Callable, Sequence
from typing import Any, Literal

from pydantic import Field

from app.modules.chatbot.extraction.registry import REGISTRY
from app.modules.chatbot.extraction.validate_registry import display_name, models_in_text
from app.modules.chatbot.schemas.default import SystemModel
from app.modules.chatbot.schemas.system import (
    AgentRun,
    AgentToolPlan,
    CatalogMatch,
    ConversationMessage,
    RunState,
    TaskKind,
    TaskStatus,
    ToolTurnState,
)
from app.modules.chatbot.stages.answer_composer import serialize_turn
from app.modules.chatbot.stages.catalog_lookup_stage import AWAITING_MODELS
from app.modules.chatbot.stages.retrieval_pipeline import RetrievalPipeline

from .base import ToolArgumentError, ToolContext, ToolOutput, ToolRejected, ToolSpec

PRODUCT_DOCS_TOOL_NAME = "product_docs_ask"

PRODUCT_DOCS_DESCRIPTION = (
    "Tra cứu tài liệu kỹ thuật và catalog sản phẩm của QS Technology: giới thiệu, thông số, "
    "tìm model theo tiêu chí, so sánh model, lắp đặt/đấu dây, vận hành, cấu hình tham số, xử lý "
    "lỗi/alarm, thông tin công ty. Dùng cho mọi thông tin về sản phẩm. "
    "`question` phải tự đủ nghĩa (không dùng 'nó', 'model đó') và ghi rõ mã model nếu đã biết "
    "(vd F86, 6AV); mỗi lần gọi một câu hỏi. `based_on_sources`: chỉ dùng khi model trong "
    "question được chọn từ nguồn của lần gọi trước (xem hướng dẫn của tool)."
)

# Luật riêng của tool này: chỉ vào system prompt khi principal được dùng tool.
PRODUCT_DOCS_GUIDE = """Output.status:
- answered: chỉ dựa vào sources; ghi [S#] theo source_id. Giữ nguyên mã model, connector, tham số, lỗi. Nguồn của model nào chỉ dùng cho model đó (sources[].product_models).
- matched / no_match: kết quả tìm model theo dữ liệu sản phẩm (catalog_match), xem bên dưới.
- needs_clarification: hỏi lại nhân viên, liệt kê clarification.candidates theo `name`. Lượt sau, khi nhân viên đã chọn, gọi lại tool với `code` của model.
- no_docs: nói rõ chưa có tài liệu cho nội dung/model đó.
- handoff: nội dung ngoài tài liệu (giá, bảo hành, chính sách, mua hàng); nêu handoff_reason và hướng nhân viên tới bộ phận phụ trách. Không tự báo giá hay cam kết.
- out_of_scope: nói ngắn rằng ngoài phạm vi tài liệu. failed: tra cứu lỗi.
- task_results[].status = awaiting_models: ý đó cần model là kết quả tìm ở cùng lần gọi; gọi lại riêng cho từng model theo next_action.
- Lỗi model_not_evidenced: không tự chọn model; hỏi lại nhân viên hoặc làm theo next_action.

Câu hỏi nhiều bước (tìm model theo tiêu chí, rồi hỏi tiếp về model đó): tìm trước, đọc kết quả, rồi mới hỏi tiếp.
- Đếm và chọn model theo catalog_match.models (dữ liệu sản phẩm), không theo văn bản nguồn. Làm đúng catalog_match.next_action:
  - report_no_match: nói rõ dữ liệu sản phẩm xác nhận không có model nào thỏa các điều kiện đã nêu; không tra tiếp.
  - lookup_each: gọi song song, mỗi model một câu hỏi có mã model (code).
  - ask_selection: liệt kê các model (theo name) và hỏi nhân viên muốn xem model nào; không tra tiếp trong lượt này. Lượt sau, nhân viên chọn một vài model hoặc "tất cả" thì tra tiếp cho các model đó.
  - verify_with_sources: còn điều kiện chưa có trong dữ liệu sản phẩm (unmapped_conditions). Chỉ chọn model mà nguồn nói rõ thỏa điều kiện; khi hỏi tiếp về model đó, truyền based_on_sources là các source_id đó. Nói rõ kết quả là "theo tài liệu tìm được", có thể chưa đầy đủ. Từ 4 model trở lên thì hỏi nhân viên chọn.
- Model có has_technical_docs = false: nói rõ chưa có tài liệu chi tiết, chỉ có thông tin tổng quan.
- Phân biệt "dữ liệu xác nhận không có" (no_match) với "không tìm thấy trong tài liệu" (no_docs, hoặc verify_with_sources không có nguồn nào khớp)."""

DocsStatus = Literal[
    "answered", "matched", "no_match", "needs_clarification", "no_docs", "handoff",
    "out_of_scope", "failed",
]

# Giới hạn số nguồn agent trích trong một lần gọi (kiểm tra bằng code, không đưa vào schema).
MAX_CITED_SOURCES = 10
REGISTRY_MODELS: tuple[str, ...] = tuple(REGISTRY["product_models"])
_SOURCE_ID = re.compile(r"^S[1-9][0-9]*$")

# Biên an toàn cho các trường truncated/omitted_sources thêm vào sau khi cắt.
_TRUNCATION_MARGIN_TOKENS = 32
_MIN_SOURCE_TOKENS = 48
_SENTENCE_END = re.compile(r"[.!?。…](?=\s)|\n")


class ProductDocsTurnState(ToolTurnState):
    """State của tool tra cứu tài liệu trong một lượt agent."""

    # Model backend đã xác nhận bằng dữ liệu có cấu trúc (catalog_match lookup_each):
    # bằng chứng cho guard ở các lần tra cứu sau trong cùng lượt.
    discovered_models: list[str] = Field(default_factory=list)
    # Plan retrieval của từng lần gọi (retrieval snapshot, ngữ cảnh model của phiên).
    plans: list[AgentToolPlan] = Field(default_factory=list)


def product_docs_plans(agent: AgentRun | None) -> list[AgentToolPlan]:
    """Plan các lần gọi product_docs_ask trong lượt (rỗng nếu lượt không gọi tool này)."""
    state = agent.tool_state(ProductDocsTurnState) if agent is not None else None
    return list(state.plans) if state is not None else []


class ProductDocsAskInput(SystemModel):
    question: str = Field(
        min_length=1,
        max_length=1000,
        description="Câu hỏi tự đủ nghĩa, ghi rõ mã model nếu đã biết.",
    )
    based_on_sources: list[str] = Field(
        default_factory=list,
        description=(
            "source_id (vd S3) đã nhận trong lượt này, nói rõ model trong question thỏa điều kiện "
            "của câu hỏi trước. Để [] khi model do nhân viên nêu hoặc có trong catalog_match."
        ),
    )


class DocsTaskResult(SystemModel):
    task_id: str
    kind: str
    status: str
    queries: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    context_model: str | None = None
    error: str | None = None


class DocsSource(SystemModel):
    source_id: str | None = None
    section: str
    pages: str | None = None
    content: str


class DocsSourceGroup(SystemModel):
    query: str
    answer_mode: str
    # Model đã lọc khi retrieve nhóm nguồn này; [] = không lọc theo model.
    product_models: list[str] = Field(default_factory=list)
    sources: list[DocsSource] = Field(default_factory=list)


class DocsCandidate(SystemModel):
    code: str           # mã dùng khi gọi lại tool
    name: str           # tên hiển thị khi hỏi nhân viên


class DocsClarification(SystemModel):
    reason: str
    blocking: bool
    mentions: list[str] = Field(default_factory=list)
    candidates: list[DocsCandidate] = Field(default_factory=list)


class ProductDocsAskOutput(ToolOutput):
    status: DocsStatus
    task_results: list[DocsTaskResult] = Field(default_factory=list)
    sources: list[DocsSourceGroup] = Field(default_factory=list)
    clarification: DocsClarification | None = None
    handoff_reason: str | None = None
    catalog_match: CatalogMatch | None = None

    def to_llm(self, budget_tokens: int, count: Callable[[str], int]) -> dict[str, Any]:
        """Cắt theo cấu trúc: luôn giữ status/clarification/task_results/catalog_match, thêm nguồn
        theo thứ tự rank tới khi hết budget, nguồn cuối cắt ở ranh giới câu."""
        payload = self.model_dump(mode="json", exclude_none=True)
        groups = payload.pop("sources", [])
        payload["sources"] = []
        budget = budget_tokens - _TRUNCATION_MARGIN_TOKENS
        used = count(_j(payload))
        omitted = 0
        truncated = False
        full = False    # hết budget: mọi nguồn sau (rank thấp hơn) đều bị lược
        for group in groups:
            kept = {**group, "sources": []}
            group_cost = count(_j(kept))
            if full or used + group_cost > budget:
                full = True
                omitted += len(group["sources"])
                continue
            payload["sources"].append(kept)
            used += group_cost
            for source in group["sources"]:
                if full:
                    omitted += 1
                    continue
                cost = count(_j(source)) + 1
                if used + cost <= budget:
                    kept["sources"].append(source)
                    used += cost
                    continue
                full = True
                room = budget - used - count(_j({**source, "content": ""})) - 1
                content = _cut_at_sentence(source["content"], room, count)
                if content:
                    shortened = {**source, "content": content}
                    kept["sources"].append(shortened)
                    used += count(_j(shortened)) + 1
                    truncated = True
                else:
                    omitted += 1
        if omitted or truncated:
            payload["truncated"] = True
            payload["omitted_sources"] = omitted
        return payload


def build_product_docs_tool(pipeline: RetrievalPipeline, timeout_s: float = 20.0) -> ToolSpec:
    async def run(arguments: ProductDocsAskInput, context: ToolContext) -> ProductDocsAskOutput:
        parent = context.parent_state
        turn = context.turn_state(ProductDocsTurnState)
        evidence = evidence_models(parent, arguments.based_on_sources, turn.discovered_models)
        check_question_models(arguments.question, evidence)
        child = child_state(parent, arguments.question, evidence)
        await pipeline.run(child, context.sources)
        for trace in child.retrieval_traces:
            parent.add_trace(trace)
        output = build_output(child)
        assert parent.agent is not None     # turn_state đã tạo
        parent.agent.add_source_texts({
            source.source_id: source.content
            for group in output.sources
            for source in group.sources
            if source.source_id
        })
        match = child.catalog_match
        if match is not None and match.next_action == "lookup_each":
            # Chỉ khi backend cho tra tiếp; vượt ngưỡng thì nhân viên phải chọn trước.
            turn.discovered_models = list(dict.fromkeys(
                [*turn.discovered_models, *(model.code for model in match.models)]
            ))
        if child.plan is not None:
            turn.plans = [*turn.plans, AgentToolPlan(
                tool_call_id=context.tool_call_id,
                question=arguments.question,
                plan=child.plan,
                product_models=answered_models(child),
            )]
        return output

    return ToolSpec(
        name=PRODUCT_DOCS_TOOL_NAME,
        description=PRODUCT_DOCS_DESCRIPTION,
        input_model=ProductDocsAskInput,
        output_model=ProductDocsAskOutput,
        run=run,
        guide=PRODUCT_DOCS_GUIDE,
        read_only=True,
        concurrency_safe=True,
        timeout_s=timeout_s,
    )


def evidence_models(
    parent: RunState,
    based_on_sources: list[str],
    discovered_models: Sequence[str] = (),
) -> list[str]:
    """Model được phép dùng trong câu hỏi của agent, theo thứ tự registry.

    Nhân viên đã nhắc (tin nhắn, history), ngữ cảnh model của phiên, model backend
    đã xác nhận trong lượt (discovered_models), và model có trong nguồn agent trích.
    Raise ToolArgumentError khi trích nguồn không có trong lượt.
    """
    if parent.context is None:
        raise ValueError("product docs tool requires a loaded context")
    conversation = parent.context.conversation
    text = "\n".join([
        parent.input.message.text,
        *(message.content for message in conversation.history),
        *_cited_texts(parent, based_on_sources),
    ])
    found = set(models_in_text(text))
    found.update(conversation.state.last_models)
    if conversation.state.active_model:
        found.add(conversation.state.active_model)
    found.update(discovered_models)
    return [model for model in REGISTRY_MODELS if model in found]


def check_question_models(question: str, evidence: list[str]) -> None:
    """Từ chối trước khi gọi LLM khi câu hỏi có model không có bằng chứng.

    Guard trong AnalysisStage vẫn chạy (LLM có thể tự thêm model); bước này chặn
    sớm call vô ích, vd. agent tra tiếp cả 6 model khi backend yêu cầu hỏi chọn.
    """
    missing = [model for model in models_in_text(question) if model not in evidence]
    if missing:
        raise ToolRejected(
            "model_not_evidenced",
            f"models {', '.join(missing)} were not mentioned by the employee nor confirmed in "
            "this turn; ask the employee, follow catalog_match.next_action, or cite the sources "
            "that state them via based_on_sources",
        )


def _cited_texts(parent: RunState, based_on_sources: list[str]) -> list[str]:
    if not based_on_sources:
        return []
    if len(based_on_sources) > MAX_CITED_SOURCES:
        raise ToolArgumentError(f"based_on_sources: at most {MAX_CITED_SOURCES} source ids")
    known = parent.agent.source_texts if parent.agent is not None else {}
    unknown = [
        source_id for source_id in based_on_sources
        if not _SOURCE_ID.fullmatch(source_id) or source_id not in known
    ]
    if unknown:
        raise ToolArgumentError(
            f"based_on_sources: unknown source ids {', '.join(unknown[:5])}; cite only "
            "source_id values returned by earlier calls in this turn"
        )
    return [known[source_id] for source_id in dict.fromkeys(based_on_sources)]


def answered_models(state: RunState) -> list[str]:
    """Model của các sub-query có nguồn (task retrieve có hit)."""
    if state.analysis is None or state.plan is None:
        return []
    sub_queries = {sub_query.id: sub_query for sub_query in state.analysis.sub_queries}
    models: list[str] = []
    for task in state.plan.tasks:
        result = task.result
        if task.kind is not TaskKind.RETRIEVE or result is None or result.retrieval is None:
            continue
        for sub_result in result.retrieval.results:
            sub_query = sub_queries.get(sub_result.sub_query_id)
            if sub_result.hits and sub_query is not None:
                models.extend(sub_query.entities.product_models)
    return list(dict.fromkeys(models))


def child_state(parent: RunState, question: str, evidence: list[str] | None = None) -> RunState:
    """RunState riêng cho một lần tra cứu.

    - query.origin là câu hỏi của agent; tin nhắn thật của người dùng được thêm vào
      history để AnalysisStage thấy, và guard model lấy bằng chứng từ state.input
      cộng evidence_models.
    - Giữ last_models/active_model của phiên (kế thừa model và phát hiện xung đột
      bằng code); CatalogLookupStage chặn kế thừa trong lần gọi có tìm model.
    - Không dùng pending: luồng agent tự hỏi lại qua history.
    """
    if parent.context is None:
        raise ValueError("product docs tool requires a loaded context")
    context = parent.context
    current = ConversationMessage(
        role="user",
        content=parent.input.message.text,
        message_id=f"{parent.input.message.message_id}:user",
    )
    child_context = context.model_copy(update={
        "conversation": context.conversation.model_copy(update={
            "state": context.conversation.state.model_copy(update={
                "pending": None,
                "clarify_attempts": 0,
            }),
            "history": [*context.conversation.history, current],
        }),
        "query": context.query.model_copy(update={"origin": question}),
    })
    return RunState(
        input=parent.input,
        principal=parent.principal,
        request_context=parent.request_context,
        context=child_context,
        context_status="pruned",
        security=parent.security,
        evidence_models=list(evidence or []),
    )


def build_output(state: RunState) -> ProductDocsAskOutput:
    assert state.analysis is not None and state.plan is not None
    task_results, groups = serialize_turn(state, include_models=True)
    awaiting = _awaiting_ids(state)
    for item, task in zip(task_results, state.plan.tasks):
        if set(task.sub_query_ids) & awaiting:
            item["status"] = AWAITING_MODELS
    clarification = state.analysis.clarification
    return ProductDocsAskOutput(
        status=docs_status(state),
        catalog_match=state.catalog_match,
        task_results=[DocsTaskResult.model_validate(item) for item in task_results],
        sources=[DocsSourceGroup.model_validate(group) for group in groups],
        clarification=None if clarification is None else DocsClarification(
            reason=clarification.reason,
            blocking=clarification.blocking,
            mentions=clarification.mentions,
            candidates=[
                DocsCandidate(code=code, name=display_name(code))
                for code in dict.fromkeys(
                    model for models in clarification.candidates.values() for model in models
                )
            ],
        ),
        handoff_reason=state.analysis.handoff_reason,
    )


def docs_status(state: RunState) -> DocsStatus:
    assert state.analysis is not None and state.plan is not None
    tasks = state.plan.tasks
    kinds = {task.kind for task in tasks}
    retrieve = [task for task in tasks if task.kind is TaskKind.RETRIEVE]
    if any(
        sub_result.hits
        for task in retrieve
        if task.result is not None and task.result.retrieval is not None
        for sub_result in task.result.retrieval.results
    ):
        return "answered"
    match = state.catalog_match
    if match is not None and match.next_action == "report_no_match":
        return "no_match"
    if match is not None and match.next_action in ("lookup_each", "ask_selection"):
        return "matched"
    awaiting = _awaiting_ids(state)
    if any(
        task.kind is TaskKind.CLARIFY and not set(task.sub_query_ids) <= awaiting
        for task in tasks
    ):
        return "needs_clarification"
    if TaskKind.NO_DOCS in kinds:
        return "no_docs"
    if TaskKind.HANDOFF in kinds:
        return "handoff"
    if retrieve and all(task.status is TaskStatus.FAILED for task in retrieve):
        return "failed"
    if retrieve:
        return "no_docs"
    return "out_of_scope"


def _awaiting_ids(state: RunState) -> set[str]:
    """Sub-query chờ model là kết quả tìm của cùng lần gọi (không phải câu hỏi lại nhân viên)."""
    assert state.analysis is not None
    return {
        sub_query.id
        for sub_query in state.analysis.sub_queries
        if sub_query.clarification is not None
        and sub_query.clarification.reason == AWAITING_MODELS
    }


def _cut_at_sentence(text: str, max_tokens: int, count: Callable[[str], int]) -> str | None:
    """Phần đầu của text không quá max_tokens, kết thúc ở ranh giới câu."""
    if max_tokens < _MIN_SOURCE_TOKENS:
        return None
    total = count(text)
    if total <= max_tokens:
        return text
    limit = len(text) * max_tokens // total
    for _ in range(6):
        cut = text[:limit]
        ends = [match.end() for match in _SENTENCE_END.finditer(cut)]
        boundary = next((end for end in reversed(ends) if end >= len(cut) // 2), len(cut))
        candidate = cut[:boundary].rstrip() + " …"
        if count(candidate) <= max_tokens:
            return candidate
        limit = limit * 4 // 5
    return None


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
