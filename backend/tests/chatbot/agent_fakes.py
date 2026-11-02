"""Fake dùng chung cho test luồng agent: provider tool-calling theo kịch bản, retriever, tool."""

import asyncio
import inspect
import json
import re
from types import SimpleNamespace

from app.modules.chatbot.agent import AgentLimits, AgentRunner
from app.modules.chatbot.extraction.product_catalog import RegistryProductCatalog
from app.modules.chatbot.providers.openai import OPENAI_CAPABILITIES
from app.modules.chatbot.retrieval import Retriever, RetrieverConfig
from app.modules.chatbot.schemas.default import ChannelType, SystemModel
from app.modules.chatbot.schemas.system import (
    AssistantTurn,
    ChunkMatch,
    Conversation,
    ModelProvider,
    QueryInfo,
    RetrievalScope,
    RunContext,
    RunState,
    TokenUsage,
    ToolCallRequest,
)
from app.modules.chatbot.stages.analysis_stage import AnalysisStage
from app.modules.chatbot.stages.catalog_lookup_stage import CatalogLookupStage
from app.modules.chatbot.stages.clarification_resume_stage import ClarificationResumeStage
from app.modules.chatbot.stages.execution_stage import ExecutionStage
from app.modules.chatbot.stages.retrieval_pipeline import RetrievalPipeline
from app.modules.chatbot.tools import (
    ToolOutput,
    ToolRegistry,
    ToolSpec,
    build_product_docs_tool,
)
from tests.chatbot.builders import make_inbound, make_request_context, make_service_principal


def answer(text: str, finish_reason: str = "stop") -> AssistantTurn:
    return AssistantTurn(content=text, finish_reason=finish_reason,
                         usage=TokenUsage(input_tokens=10, output_tokens=5))


def calls(*items, content: str | None = None) -> AssistantTurn:
    """items: (id, name, arguments) với arguments là dict hoặc chuỗi JSON thô."""
    return AssistantTurn(
        content=content,
        finish_reason="tool_calls",
        tool_calls=[
            ToolCallRequest(
                id=call_id,
                name=name,
                arguments_raw=arguments if isinstance(arguments, str) else json.dumps(arguments),
            )
            for call_id, name, arguments in items
        ],
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )


def ask(call_id: str, question: str) -> tuple[str, str, dict]:
    return call_id, "product_docs_ask", {"question": question}


class ScriptedToolProvider:
    """Provider agent theo kịch bản; analysis (chat_complete_json) lấy từ hàng đợi riêng.

    Mỗi phần tử của `turns` là AssistantTurn, Exception, hoặc callable (sync/async)
    trả về AssistantTurn. `analyze(query)`: sinh output analysis từ <query> thay cho
    hàng đợi, dùng khi nhiều lần tra cứu chạy song song (thứ tự gọi không cố định).
    """

    kind = ModelProvider.OPENAI
    model = "test-model"

    def __init__(self, turns=(), analysis_outputs=(), capabilities=OPENAI_CAPABILITIES,
                 analyze=None):
        self.turns = list(turns)
        self.analysis_outputs = list(analysis_outputs)
        self.analyze = analyze
        self._capabilities = capabilities
        self.calls = []
        self.analysis_messages = []

    @property
    def capabilities(self):
        return self._capabilities

    async def chat_complete_tools(self, messages, tools, *, tool_choice="auto",
                                  parallel_tool_calls=True, max_tokens=1200):
        self.calls.append(SimpleNamespace(
            messages=[dict(message) for message in messages],
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
        ))
        turn = self.turns.pop(0)
        if isinstance(turn, BaseException):
            raise turn
        if callable(turn):
            turn = turn()
            if inspect.isawaitable(turn):
                turn = await turn
        return turn

    async def chat_complete_json(self, messages, response_format=None):
        self.analysis_messages.append(messages)
        if self.analyze is not None:
            query = re.search(r"<query>(.*)</query>", messages[1]["content"], re.S).group(1)
            return self.analyze(query)
        output = self.analysis_outputs.pop(0)
        if callable(output):
            output = output()
            if inspect.isawaitable(output):
                output = await output
        return output

    async def stream_chat(self, messages):
        yield "pipeline answer"


def sub_query(query, intent, models=(), unresolved=(), handoff_reason=None,
              dependency="model_specific", ci=(), excluded=(), match="all", unmapped=()):
    return {
        "standalone_query": query,
        "intent": intent,
        "product_models": list(models),
        "unresolved_mentions": list(unresolved),
        "control_interface": list(ci),
        "excluded_control_interface": list(excluded),
        "interface_match": match,
        "unmapped_conditions": list(unmapped),
        "spec_attributes": [],
        "handoff_reason": handoff_reason,
        "history_conflict": False,
        "model_dependency": dependency,
    }


def analysis_output(*sub_queries):
    return {"sub_queries": list(sub_queries), "pending_answer": None, "language": "vi"}


class FakeEmbedder:
    async def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeChunks:
    """match_doc_chunks giả: kết quả theo (domain, models); `gate` chặn để test huỷ."""

    def __init__(self, results=None, gate: asyncio.Event | None = None):
        self.results = results or {}
        self.gate = gate
        self.calls = []
        self.started = asyncio.Event()
        self.cancelled = False

    async def match(self, **kwargs):
        self.calls.append(kwargs)
        self.started.set()
        if self.gate is not None:
            try:
                await self.gate.wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        key = (kwargs["domain"], tuple(kwargs["models"] or ()))
        return list(self.results.get(key, []))

    async def fetch_by_ids(self, ids):
        return []


def chunk(chunk_id: int, doc_id: str = "f86_installation", vector: float = 0.6,
          content: str | None = None) -> ChunkMatch:
    return ChunkMatch(
        id=chunk_id,
        doc_id=doc_id,
        section_title=f"Section {chunk_id}",
        section_path=["Lắp đặt", f"Section {chunk_id}"],
        page_start=chunk_id,
        content=content or f"Nội dung {chunk_id}. Câu thứ hai của đoạn {chunk_id}.",
        vector_score=vector,
        fused_score=0.03,
    )


def docs_pipeline(provider, chunks: FakeChunks) -> RetrievalPipeline:
    return RetrievalPipeline(
        ClarificationResumeStage(),
        AnalysisStage(provider),
        ExecutionStage(retriever=Retriever(FakeEmbedder(), chunks, RetrieverConfig())),
        CatalogLookupStage(RegistryProductCatalog()),
    )


def docs_registry(provider, chunks: FakeChunks, timeout_s: float = 20.0) -> ToolRegistry:
    return ToolRegistry([build_product_docs_tool(docs_pipeline(provider, chunks), timeout_s)])


def agent_runner(provider, registry: ToolRegistry, **limits) -> AgentRunner:
    return AgentRunner(provider, registry, AgentLimits(**limits))


class EchoIn(SystemModel):
    text: str


class EchoOut(ToolOutput):
    text: str


class ToolProbe:
    """Ghi số tool đang chạy đồng thời và các lần bị huỷ."""

    def __init__(self):
        self.running = 0
        self.max_running = 0
        self.cancelled = []
        self.started = asyncio.Event()


def echo_tool(name="echo", *, delay=0.0, fail=False, concurrency_safe=True,
              probe: ToolProbe | None = None, block: asyncio.Event | None = None,
              timeout_s=20.0) -> ToolSpec:
    async def run(arguments: EchoIn, context) -> EchoOut:
        if probe is not None:
            probe.running += 1
            probe.max_running = max(probe.max_running, probe.running)
            probe.started.set()
        try:
            if block is not None:
                await block.wait()
            if delay:
                await asyncio.sleep(delay)
            if fail:
                raise RuntimeError("boom")
            return EchoOut(text=arguments.text)
        except asyncio.CancelledError:
            if probe is not None:
                probe.cancelled.append(arguments.text)
            raise
        finally:
            if probe is not None:
                probe.running -= 1

    return ToolSpec(
        name=name,
        description=f"Echo tool {name}",
        input_model=EchoIn,
        output_model=EchoOut,
        run=run,
        concurrency_safe=concurrency_safe,
        timeout_s=timeout_s,
    )


def crm_state(text: str = "Câu hỏi", history=()) -> RunState:
    inbound = make_inbound(text, channel=ChannelType.CRM)
    state = RunState(
        input=inbound,
        principal=make_service_principal(),
        request_context=make_request_context(ChannelType.CRM),
    )
    state.context = RunContext(
        conversation=Conversation(history=list(history)),
        query=QueryInfo(origin=text),
        retrieval_scope=RetrievalScope(collections=["crm-technical"]),
    )
    state.context_status = "pruned"
    return state


def tool_messages(messages) -> list[dict]:
    return [message for message in messages if message["role"] == "tool"]
