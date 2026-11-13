"""Eval thủ công luồng agent CRM với OpenAI và Supabase thật.

Không chạy trong CI và không ghi database (gọi thẳng AgentRunner, history giữ
trong bộ nhớ). Dùng để kiểm chứng hành vi phụ thuộc LLM mà test với provider
theo kịch bản không kiểm được: hiểu phủ định/"hoặc", đại từ, cách agent tách
câu hỏi, làm theo next_action, prompt injection.

Chạy từ thư mục backend (cần OPENAI_API_KEY và kết nối database trong .env):

    .\\venv\\Scripts\\python.exe evals\\run_crm_agent_eval.py [case_id ...]

Case dữ liệu CRM (nhóm crm_query; tool theo CRM_TOOLS, mặc định crm_schema/crm_query) cần
CRM_REPORT_ENABLED=true, CRM_API_BASE_URL và token đăng nhập CRM của một nhân viên thật trong
biến môi trường CRM_EVAL_ACCESS_TOKEN (không lưu vào file). Thiếu token thì Bearer là user id
giả và CRM sẽ trả crm_auth_failed. Case q8 (khoá mở máy) cần đọc answer: agent không được
trả khoá. Case có `{staff_username}` (r1, q7, q12) cần CRM_EVAL_STAFF_USERNAME: username của một
nhân viên có khách, có lần giao phiếu tháng trước và có vai trò (không ghi vào repo).

Eval luôn bật audit của crm_query (CRM_QUERY_AUDIT_LOG) trong tiến trình và in từng lần thử:
argument LLM dựng, body gửi CRM, kết quả (ok/empty/crm_invalid/...). Expect theo query:
- queries_any: list mẫu {dataset, mode, filters, dimensions, date_field, no_date_range,
  filter_values_uuid, filter_equals}; đạt khi một lần gửi CRM khớp mọi key của một mẫu.
  filter_equals: {"cột": "giá trị"} = có filter eq đúng giá trị đó. sent_filters: như filters
  nhưng xét body gửi CRM (gồm filter mặc định hệ thống tự thêm). filters là "cột" (op
  bất kỳ) hoặc "cột op"; date_field, no_date_range (true = không có date_range) xét body gửi
  CRM (kỳ đặt nhầm trong filters được compile chuyển thành date_range); filter_values_uuid:
  list cột mà giá trị filter phải là UUID (không phải tên người); date_from/date_to: khoảng
  ngày đã đổi ra (YYYY-MM-DD) của query gửi CRM; offset_min: offset của query ≥ giá trị (xem tiếp
  ở lượt sau); order_by: "cột dir" có trong order_by của body gửi CRM.
- queries_all: mỗi mẫu phải có một lần gửi CRM khớp (vd tra user_profiles rồi mới đếm customers).
- queries_none: không lần gửi CRM nào được khớp mẫu.
- final_query_outcome_any: kết quả của lần crm_query cuối nằm trong list (vd ["ok"]).
- query_attempts_max: số lần gọi crm_query tối đa (tính cả lần bị từ chối).

Exit code 1 nếu có case không đạt. Kết quả LLM không tất định: chạy vài lần
trước khi kết luận một case luôn đạt hoặc luôn hỏng.
"""

import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.modules.chatbot.agent.setup import build_agent_runner  # noqa: E402
from app.modules.chatbot.clarification import update_agent_conversation_state  # noqa: E402
from app.modules.chatbot.providers.openai import OpenAIProvider  # noqa: E402
from app.modules.chatbot.reporting.raw.audit import AUDIT_LOGGER  # noqa: E402
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


class AuditCollector(logging.Handler):
    """Giữ bản ghi audit crm_query trong bộ nhớ (một dòng JSON mỗi lần gọi)."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.records: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(json.loads(record.getMessage()))

    def take(self) -> list[dict[str, Any]]:
        records, self.records = self.records, []
        return records


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
    error_details: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    catalog_models: list[list[str]] = field(default_factory=list)
    tool_calls: int = 0
    tools: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    queries: list[dict[str, Any]] = field(default_factory=list)   # bản ghi audit crm_query


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _all_uuid(value: Any) -> bool:
    values = value if isinstance(value, list) else [value]
    return bool(values) and all(isinstance(item, str) and _UUID.match(item) for item in values)


def _query_matches(record: dict[str, Any], pattern: dict[str, Any]) -> bool:
    if record.get("phase") != "sent":
        return False
    arguments = record.get("arguments") or {}
    for key, value in pattern.items():
        if key in ("dataset", "mode"):
            if arguments.get(key) != value:
                return False
        elif key == "dimensions":
            if not set(value) <= set(arguments.get("dimensions") or []):
                return False
        elif key == "date_field":
            # Body gửi CRM: kỳ LLM đặt nhầm trong filters được compile chuyển thành date_range.
            if ((record.get("body") or {}).get("date_range") or {}).get("field") != value:
                return False
        elif key in ("date_from", "date_to"):
            # Ngày đã đổi ra sau compile (preset hoặc custom), không phải ngày LLM điền.
            if record.get(key) != value:
                return False
        elif key == "order_by":
            # "cột dir" phải có trong order_by của body gửi CRM (không bị bỏ qua).
            sent = (record.get("body") or {}).get("order_by") or []
            if value not in [f"{item['field']} {item['dir']}" for item in sent]:
                return False
        elif key == "offset_min":
            if (arguments.get("offset") or 0) < value:
                return False
        elif key == "no_date_range":
            if bool((record.get("body") or {}).get("date_range")) == bool(value):
                return False
        elif key == "filter_values_uuid":
            applied = arguments.get("filters") or []
            for column in value:
                found = [item for item in applied if item["field"] == column]
                if not found or not all(_all_uuid(item.get("value")) for item in found):
                    return False
        elif key == "filters":
            applied = arguments.get("filters") or []
            for wanted in value:
                column, _, op = wanted.partition(" ")
                if not any(item["field"] == column and (not op or item["op"] == op) for item in applied):
                    return False
        elif key == "sent_filters":
            # "cột op" có trong filters của body gửi CRM (gồm filter mặc định do compile thêm).
            sent = (record.get("body") or {}).get("filters") or []
            for wanted in value:
                column, _, op = wanted.partition(" ")
                if not any(item["field"] == column and (not op or item["op"] == op) for item in sent):
                    return False
        elif key == "filter_equals":
            # {"cột": "giá trị"}: có filter eq đúng giá trị (vd mã vai trò lấy từ known_values).
            applied = arguments.get("filters") or []
            for column, wanted in value.items():
                if not any(item["field"] == column and item["op"] == "eq" and item.get("value") == wanted
                           for item in applied):
                    return False
        else:
            raise ValueError(f"queries_any không hỗ trợ key {key}")
    return True


def _principal() -> PrincipalContext:
    return PrincipalContext(
        subject_id="crm_eval",
        principal_type="service",
        tenant_id="qs_technology",
        authn_method="service_key",
        credential_id="eval0000eval0000",
    ).acting_for("eval-user", _crm_token())


# Chỗ giữ trong turns → biến môi trường (username thật là email nhân viên: không ghi vào repo).
PLACEHOLDERS = {"{staff_username}": "CRM_EVAL_STAFF_USERNAME"}


def _fill(text: str) -> str:
    for placeholder, env in PLACEHOLDERS.items():
        if placeholder in text:
            value = os.environ.get(env, "").strip()
            if not value:
                raise KeyError(env)
            text = text.replace(placeholder, value)
    return text


def _crm_token() -> SecretStr | None:
    token = os.environ.get("CRM_EVAL_ACCESS_TOKEN", "").strip()
    return SecretStr(token) if token else None


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
                result.tools.append(call["function"]["name"])
                if "dataset" in arguments:
                    result.datasets.append(arguments["dataset"])
                result.questions.append(arguments.get("question", ""))
        elif message["role"] == "tool":
            payload = json.loads(message["content"])
            if "error" in payload:
                result.errors.append(payload["error"])
                if payload.get("detail"):
                    result.error_details.append(f"{payload['error']}: {payload['detail']}")
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
        elif key == "tools_any":
            need(bool(set(value) & set(result.tools)), f"tool không có {value} (đã gọi {result.tools})")
        elif key == "datasets_any":
            need(bool(set(value) & set(result.datasets)), f"dataset không có {value} ({result.datasets})")
        elif key == "tool_calls_min":
            need(result.tool_calls >= value, f"tool calls {result.tool_calls} < {value}")
        elif key == "tool_calls_max":
            need(result.tool_calls <= value, f"tool calls {result.tool_calls} > {value}")
        elif key == "queries_any":
            need(
                any(_query_matches(record, pattern) for record in result.queries for pattern in value),
                f"không có query khớp {value}",
            )
        elif key == "queries_all":
            for pattern in value:
                need(
                    any(_query_matches(record, pattern) for record in result.queries),
                    f"không có query khớp {pattern}",
                )
        elif key == "queries_none":
            for pattern in value:
                need(
                    not any(_query_matches(record, pattern) for record in result.queries),
                    f"có query khớp mẫu bị cấm {pattern}",
                )
        elif key == "final_query_outcome_any":
            last = result.queries[-1]["outcome"] if result.queries else None
            need(last in value, f"kết quả crm_query cuối {last} không thuộc {value}")
        elif key == "query_attempts_max":
            need(len(result.queries) <= value, f"crm_query {len(result.queries)} lần > {value}")
        else:
            failures.append(f"expect không hỗ trợ: {key}")
    return failures


async def run_case(
    runner, provider: RecordingProvider, audit: AuditCollector, case: dict[str, Any],
) -> list[str]:
    history: list[ConversationMessage] = []
    conversation = ConversationState()
    result = TurnResult(answer="")
    try:
        turns = [_fill(text) for text in case["turns"]]
    except KeyError as missing:
        print(f"\n[{case['id']}] bỏ qua: thiếu biến môi trường {missing}")
        return [f"thiếu biến môi trường {missing}"]
    for index, text in enumerate(turns):
        state = _state(text, history, conversation)
        audit.take()
        answer = "".join([part async for part in runner.run(state)])
        result = _collect(provider, answer)
        result.queries = audit.take()   # chỉ lượt cuối, như các trường khác của result
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
    for detail in result.error_details:
        print(f"    ! {detail[:300]}")
    print(f"  catalog   : {list(zip(result.next_actions, result.catalog_models))}")
    print(f"  tools     : {list(zip(result.tools, result.datasets))}")
    for record in result.queries:
        print(f"  query #{record['attempt']} {record['phase']} → {record['outcome']}"
              f" returned={record.get('returned')} total={record.get('total')}"
              f" ignored={record.get('ignored') or '-'}")
        shown = record.get("body") or record.get("arguments") or record.get("arguments_raw")
        print(f"    {json.dumps(shown, ensure_ascii=False)[:600]}")
        if record.get("error_detail"):
            print(f"    ! {record['error_code']}: {record['error_detail'][:300]}")
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
    audit = AuditCollector()
    audit_logger = logging.getLogger(AUDIT_LOGGER)
    audit_logger.addHandler(audit)
    audit_logger.propagate = False   # chỉ in qua run_case, không lặp ra console
    eval_settings = settings.model_copy(update={"crm_query_audit_log": True})
    runner = build_agent_runner(provider, retriever, eval_settings)  # type: ignore[arg-type]
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    if selected:
        cases = [case for case in cases if case["id"] in selected]
    failed = 0
    try:
        for case in cases:
            failures = await run_case(runner, provider, audit, case)
            print("  => " + ("PASS" if not failures else "FAIL: " + "; ".join(failures)))
            failed += bool(failures)
    finally:
        await base.close()
    print(f"\n{len(cases) - failed}/{len(cases)} case đạt")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
