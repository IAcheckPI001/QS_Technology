"""Eval thủ công luồng agent CRM với OpenAI và Supabase thật.

Không chạy trong CI và không ghi database (gọi thẳng AgentRunner, history giữ
trong bộ nhớ). Dùng để kiểm chứng hành vi phụ thuộc LLM mà test với provider
theo kịch bản không kiểm được: hiểu phủ định/"hoặc", đại từ, cách agent tách
câu hỏi, làm theo next_action, prompt injection.

Chạy từ thư mục backend (cần OPENAI_API_KEY và kết nối database trong .env):

    .\\venv\\Scripts\\python.exe evals\\run_crm_agent_eval.py [case_id ...]

Exit code 1 nếu có case không đạt. Kết quả LLM không tất định: chạy vài lần
trước khi kết luận một case luôn đạt hoặc luôn hỏng.
"""

import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.modules.chatbot.agent.setup import build_agent_runner  # noqa: E402
from app.modules.chatbot.clarification import update_agent_conversation_state  # noqa: E402
from app.modules.chatbot.providers.openai import OpenAIProvider  # noqa: E402
from app.modules.chatbot.repositories.doc_chunk_repository import DocChunkRepository  # noqa: E402
from app.modules.chatbot.retrieval import Retriever, RetrieverConfig  # noqa: E402
from app.modules.chatbot.schemas.default import ChannelType  # noqa: E402
from app.modules.chatbot.schemas.inbound import (  # noqa: E402
    ChannelInfo,
    InboundRequest,
    MessageUser,
    ResourceRefs,
    SessionInfo,
)
from app.modules.chatbot.schemas.security.principal import (  # noqa: E402
    PrincipalContext,
    RequestContext,
)
from app.modules.chatbot.tools.product_docs import product_docs_plans  # noqa: E402
from app.modules.chatbot.schemas.system import (  # noqa: E402
    Conversation,
    ConversationMessage,
    ConversationState,
    QueryInfo,
    RetrievalScope,
    RunContext,
    RunState,
)

CASES = Path(__file__).with_name("crm_agent_cases.json")


class RecordingProvider:
    """Bọc provider thật, giữ lại messages của lần gọi agent cuối (có mọi tool message)."""

    def __init__(self, provider: OpenAIProvider) -> None:
        self._provider = provider
        self.last_messages: list[dict[str, Any]] = []

    kind = property(lambda self: self._provider.kind)
    model = property(lambda self: self._provider.model)
    capabilities = property(lambda self: self._provider.capabilities)

    async def chat_complete_tools(self, messages, tools, **options):
        self.last_messages = [dict(message) for message in messages]
        return await self._provider.chat_complete_tools(messages, tools, **options)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)


@dataclass
class TurnResult:
    answer: str
    questions: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    catalog_models: list[list[str]] = field(default_factory=list)
    tool_calls: int = 0


def _principal() -> PrincipalContext:
    return PrincipalContext(
        subject_id="crm_eval",
        principal_type="service",
        tenant_id="qs_technology",
        authn_method="service_key",
        credential_id="eval0000eval0000",
    ).acting_for("eval-user")


def _state(text: str, history: list[ConversationMessage], conversation: ConversationState) -> RunState:
    inbound = InboundRequest(
        message=MessageUser(message_id=str(uuid4()), text=text),
        session=SessionInfo(session_id=str(uuid4())),
        channel=ChannelInfo(type=ChannelType.CRM),
        resources=ResourceRefs(),
    )
    state = RunState(
        input=inbound,
        principal=_principal(),
        request_context=RequestContext(
            request_id=f"eval-{uuid4().hex[:8]}",
            channel=ChannelType.CRM,
            received_at=datetime.now(UTC),
        ),
    )
    state.context = RunContext(
        conversation=Conversation(history=list(history), state=conversation),
        query=QueryInfo(origin=text),
        retrieval_scope=RetrievalScope(collections=["crm-technical"]),
    )
    state.context_status = "pruned"
    return state


def _collect(provider: RecordingProvider, answer: str) -> TurnResult:
    result = TurnResult(answer=answer)
    for message in provider.last_messages:
        if message["role"] == "assistant":
            for call in message.get("tool_calls") or []:
                result.tool_calls += 1
                arguments = json.loads(call["function"]["arguments"] or "{}")
                result.questions.append(arguments.get("question", ""))
        elif message["role"] == "tool":
            payload = json.loads(message["content"])
            if "error" in payload:
                result.errors.append(payload["error"])
                continue
            result.statuses.append(payload.get("status", ""))
            match = payload.get("catalog_match")
            if match:
                result.next_actions.append(match["next_action"])
                result.catalog_models.append([model["code"] for model in match["models"]])
    return result


def _check(result: TurnResult, expect: dict[str, Any]) -> list[str]:
    failures = []
    questions = " ".join(result.questions)

    def need(ok: bool, message: str) -> None:
        if not ok:
            failures.append(message)

    for key, value in expect.items():
        if key == "questions_contain_all":
            need(all(v in questions for v in value), f"questions thiếu {value}")
        elif key == "answer_contains_all":
            need(all(v in result.answer for v in value), f"answer thiếu {value}")
        elif key == "answer_not_contains":
            need(not any(v in result.answer for v in value), f"answer chứa {value}")
        elif key == "statuses_any":
            need(bool(set(value) & set(result.statuses)), f"status không có {value}")
        elif key == "statuses_none":
            need(not set(value) & set(result.statuses), f"status có {value}")
        elif key == "next_actions_any":
            need(bool(set(value) & set(result.next_actions)), f"next_action không có {value}")
        elif key == "next_actions_none":
            need(not set(value) & set(result.next_actions), f"next_action có {value}")
        elif key == "catalog_models":
            need(value in result.catalog_models, f"catalog models khác {value}")
        elif key == "errors_none":
            need(not set(value) & set(result.errors), f"lỗi tool {value}")
        elif key == "tool_calls_min":
            need(result.tool_calls >= value, f"tool calls {result.tool_calls} < {value}")
        elif key == "tool_calls_max":
            need(result.tool_calls <= value, f"tool calls {result.tool_calls} > {value}")
        else:
            failures.append(f"expect không hỗ trợ: {key}")
    return failures


async def run_case(runner, provider: RecordingProvider, case: dict[str, Any]) -> list[str]:
    history: list[ConversationMessage] = []
    conversation = ConversationState()
    result = TurnResult(answer="")
    for index, text in enumerate(case["turns"]):
        state = _state(text, history, conversation)
        answer = "".join([part async for part in runner.run(state)])
        result = _collect(provider, answer)
        conversation = update_agent_conversation_state(state, [
            model for plan in product_docs_plans(state.agent) for model in plan.product_models
        ])
        history += [
            ConversationMessage(role="user", content=text, message_id=f"t{index}:user"),
            ConversationMessage(role="assistant", content=answer, message_id=f"t{index}:assistant"),
        ]
    print(f"\n[{case['id']}] {case['turns'][-1]}")
    print(f"  questions : {result.questions}")
    print(f"  statuses  : {result.statuses}  errors: {result.errors}")
    print(f"  catalog   : {list(zip(result.next_actions, result.catalog_models))}")
    print(f"  answer    : {result.answer[:300]}")
    return _check(result, case["expect"])


async def main(selected: list[str]) -> int:
    if not settings.openai_api_key:
        print("Thiếu OPENAI_API_KEY: eval cần provider thật.")
        return 2
    base = OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        embedding_model=settings.embedding_model,
    )
    provider = RecordingProvider(base)
    retriever = Retriever(base, DocChunkRepository(), RetrieverConfig.from_settings(settings))
    runner = build_agent_runner(provider, retriever, settings)  # type: ignore[arg-type]
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    if selected:
        cases = [case for case in cases if case["id"] in selected]
    failed = 0
    try:
        for case in cases:
            failures = await run_case(runner, provider, case)
            print("  => " + ("PASS" if not failures else "FAIL: " + "; ".join(failures)))
            failed += bool(failures)
    finally:
        await base.close()
    print(f"\n{len(cases) - failed}/{len(cases)} case đạt")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
