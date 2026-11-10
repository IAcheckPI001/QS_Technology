"""AgentRunner: orchestrator của luồng agent (vòng lặp tool-calling có giới hạn).

LLM trong vòng lặp tự chọn tool theo từng bước; code điều khiển vòng lặp, giới
hạn, deadline, thực thi tool và ghi trace. Không có bước planner LLM riêng:
`plan()` để sẵn chỗ chèn khi số tool lớn.

Cancellation: CancelledError (client ngắt) luôn được truyền lên, không bị bắt
thành lỗi tool. Tool song song chạy trong TaskGroup nên bị huỷ cùng lượt; tầng
agent không tạo task chạy ngầm tách rời.

Runner không biết tool làm gì: hành vi riêng do ToolSpec khai báo (guide ghép
vào prompt, read_only/concurrency_safe cho song song, deduplicate cho call trùng,
max_calls_per_turn cho trần riêng). State riêng của tool nằm trong
AgentRun.tool_states, tool tự quản.

Kiểm soát bằng code, không dựa vào prompt: call trùng của tool deduplicate dùng
lại kết quả thành công trước đó; [S#] trong câu trả lời cuối không phải nguồn
của lượt bị bỏ.
"""

import asyncio
import json
import logging
import re
import time
from collections import Counter
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.core.config import Settings
from app.core.tracing import NON_ERROR_STATUSES, error_detail_items, set_root, span
from app.modules.chatbot.providers.base import ToolCallingProvider
from app.modules.chatbot.schemas.system import (
    AgentRun,
    AgentStep,
    AssistantTurn,
    LLMCall,
    LLMStage,
    RunState,
    ToolCallRequest,
    ToolChoice,
)
from app.modules.chatbot.stages.execution_stage import SourceAllocator
from app.modules.chatbot.tools import ToolContext, ToolOutcome, ToolRegistry, ToolSpec
from app.util.normalize import guess_reply_language
from app.util.token_counter import count_tokens

from .deadline import Deadline
from .prompts import build_system_prompt

logger = logging.getLogger(__name__)

# Không mở lời gọi LLM/tool khi thời gian còn lại dưới mức này (độ phân giải
# đồng hồ có thể để lại vài ms sau một timeout; lời gọi đó chắc chắn hết giờ).
MIN_CALL_BUDGET_S = 0.05
DEDUPLICATED = "deduplicated"
TOOL_CALL_LIMIT = "tool_call_limit"
# Khoảng trắng ngay trước [S#] bị bỏ cùng citation không hợp lệ.
_CITATION = re.compile(r"[ \t]*\[(S[0-9]+)\]")


class AgentError(RuntimeError):
    """Lượt agent không hoàn tất được (hết giờ, không có câu trả lời, chưa cấu hình)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AgentLimits:
    max_steps: int = 5
    max_tool_calls: int = 8
    turn_timeout_s: float = 60.0
    llm_timeout_s: float = 20.0
    tool_timeout_s: float = 20.0
    final_reserve_s: float = 10.0
    tool_output_tokens: int = 3000
    parallel_tools: int = 3
    max_concurrent_runs: int = 8
    history_messages: int = 6
    max_answer_tokens: int = 1200

    @classmethod
    def from_settings(cls, settings: Settings) -> "AgentLimits":
        return cls(
            max_steps=settings.agent_max_steps,
            max_tool_calls=settings.agent_max_tool_calls,
            turn_timeout_s=settings.agent_turn_timeout_s,
            llm_timeout_s=settings.agent_llm_timeout_s,
            tool_timeout_s=settings.agent_tool_timeout_s,
            final_reserve_s=settings.agent_final_reserve_s,
            tool_output_tokens=settings.agent_tool_output_tokens,
            parallel_tools=settings.agent_parallel_tools,
            max_concurrent_runs=settings.agent_max_concurrent_runs,
            history_messages=settings.agent_history_messages,
        )


class AgentRunner:
    def __init__(
        self,
        provider: ToolCallingProvider,
        registry: ToolRegistry,
        limits: AgentLimits | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._limits = limits or AgentLimits()
        self._clock = clock
        # Giới hạn số lượt agent đồng thời của tiến trình (DB pool, rate limit provider).
        self._run_slots = asyncio.Semaphore(self._limits.max_concurrent_runs)

    @property
    def model(self) -> str:
        return self._provider.model

    @property
    def tool_names(self) -> list[str]:
        return self._registry.names

    async def run(self, state: RunState) -> AsyncIterator[str]:
        """Chạy một lượt; câu trả lời cuối được trả thành một chunk."""
        with span("agent.run", "internal") as run_span:
            with span("agent.wait_slot", "internal"):
                await self._run_slots.acquire()
            try:
                answer = await self._run(state)
            finally:
                self._run_slots.release()
                if state.agent is not None:
                    steps = state.agent.steps
                    run_span.set(
                        steps=sum(1 for step in steps if step.kind == "llm"),
                        tool_calls=sum(1 for step in steps if step.kind == "tool"),
                        answered_without_tools=state.agent.answered_without_tools,
                        invalid_citations=len(state.agent.invalid_citations),
                    )
                    # Lượt vẫn trả lời được (outcome ok) nhưng tool lỗi: đánh dấu trên root
                    # để lọc/grep được mà không phải đọc từng span.
                    tool_errors = [
                        f"{step.name}:{step.status}"
                        for step in steps
                        if step.kind == "tool" and step.status not in NON_ERROR_STATUSES
                    ]
                    if tool_errors:
                        set_root(tool_errors=tool_errors)
        yield answer

    def plan(self, state: RunState, specs: Sequence[ToolSpec]) -> None:
        """Chỗ chèn bước lập kế hoạch trước vòng lặp (chưa dùng)."""
        return None

    async def _run(self, state: RunState) -> str:
        if state.context is None:
            raise AgentError("agent_context_missing", "Agent requires a loaded context.")
        limits = self._limits
        deadline = Deadline(limits.turn_timeout_s, self._clock)
        state.agent = AgentRun()
        specs = self._registry.allowed(state.principal)
        allowed = {spec.name for spec in specs}
        capabilities = self._provider.capabilities
        tools = self._registry.provider_tools(specs, capabilities.schema_dialect)
        sources = SourceAllocator.for_state(state)
        self.plan(state, specs)
        messages = self.build_messages(state, specs)
        # Chỉ metadata: không log nội dung tin nhắn, argument hay output của tool.
        logger.info(
            "agent turn start tools=%s acting_user=%s",
            ",".join(sorted(allowed)) or "-", state.principal.acting_user_id is not None,
        )

        step = 0
        tool_calls_used = 0
        completed: dict[str, ToolOutcome] = {}   # call key -> outcome thành công trong lượt
        calls_per_tool: Counter[str] = Counter()
        while step < limits.max_steps:
            step += 1
            timeout = deadline.budget(limits.llm_timeout_s, limits.final_reserve_s)
            if timeout < MIN_CALL_BUDGET_S:
                break
            try:
                turn = await self._complete(state, messages, tools, "auto", timeout, step)
            except TimeoutError:
                break
            if not turn.tool_calls:
                if turn.content and turn.content.strip():
                    return self._drop_unknown_citations(state, turn.content)
                break  # rỗng: thử lại một lần ở bước cuối với tool_choice="none"

            # Content đi kèm tool call là suy nghĩ trung gian: không gửi cho người dùng,
            # nhưng giữ trong assistant message cho đúng giao thức.
            messages.append(_assistant_message(turn))
            calls = turn.tool_calls
            tool_timeout = deadline.budget(limits.tool_timeout_s, limits.final_reserve_s)
            room = (
                limits.max_tool_calls - tool_calls_used if tool_timeout >= MIN_CALL_BUDGET_S else 0
            )
            runnable, skipped = calls[:max(room, 0)], calls[max(room, 0):]
            outcomes = await self._execute_unique(
                state, runnable, allowed, tool_timeout, sources, step, completed, calls_per_tool,
            )
            tool_calls_used += len(runnable)
            # Bỏ qua vì hết giờ hay vì hết số lượt gọi tool: LLM nhận đúng lý do.
            skipped_code = "tool_budget_exhausted" if tool_timeout >= MIN_CALL_BUDGET_S else "tool_timeout"
            for call in skipped:
                outcome = ToolOutcome(tool_call_id=call.id, name=call.name, error_code=skipped_code)
                self._record_tool(state, step, outcome)
                outcomes.append(outcome)
            # Mỗi tool_call_id phải có đúng một message role=tool, theo thứ tự call.
            for outcome in outcomes:
                messages.append({
                    "role": "tool",
                    "tool_call_id": outcome.tool_call_id,
                    "content": outcome.message_content(limits.tool_output_tokens, self._count),
                })
            if skipped or tool_calls_used >= limits.max_tool_calls:
                break

        final_timeout = deadline.budget(limits.llm_timeout_s)
        if final_timeout < MIN_CALL_BUDGET_S:
            raise AgentError("agent_timeout", "Agent turn ran out of time.")
        try:
            final = await self._complete(state, messages, tools, "none", final_timeout, step + 1)
        except TimeoutError:
            raise AgentError("agent_timeout", "Agent turn ran out of time.") from None
        if not (final.content and final.content.strip()):
            raise AgentError("agent_empty_answer", "Agent returned no answer.")
        return self._drop_unknown_citations(state, final.content)

    def build_messages(
        self,
        state: RunState,
        specs: Sequence[ToolSpec] | None = None,
    ) -> list[dict[str, Any]]:
        """specs: tool principal được dùng; chỉ guide của các tool này vào system prompt."""
        assert state.context is not None
        if specs is None:
            specs = self._registry.allowed(state.principal)
        conversation = state.context.conversation
        message = state.input.message.text
        history = [
            {"role": item.role, "content": item.content}
            for item in conversation.history[-self._limits.history_messages:]
        ] if self._limits.history_messages else []
        system = build_system_prompt(
            state.request_context.received_at,
            conversation.state.language or guess_reply_language(message),
            specs,
        )
        return [
            {"role": "system", "content": system},
            *history,
            {"role": "user", "content": message},
        ]

    async def _complete(
        self,
        state: RunState,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: ToolChoice,
        timeout_s: float,
        step: int,
    ) -> AssistantTurn:
        assert state.agent is not None
        started_at = perf_counter()
        try:
            with span(
                "llm.chat_tools", "llm",
                step=step, tool_choice=tool_choice, model=self._provider.model,
                messages=len(messages), timeout_s=round(timeout_s, 1),
            ) as llm_span:
                async with asyncio.timeout(timeout_s):
                    turn = await self._provider.chat_complete_tools(
                        messages,
                        tools,
                        tool_choice=tool_choice,
                        parallel_tool_calls=self._provider.capabilities.parallel_tool_calls,
                        max_tokens=self._limits.max_answer_tokens,
                    )
                llm_span.set(
                    finish_reason=turn.finish_reason,
                    tool_calls=[call.name for call in turn.tool_calls],
                    input_tokens=turn.usage.input_tokens,
                    output_tokens=turn.usage.output_tokens,
                )
        except TimeoutError:
            state.agent.add_step(AgentStep(
                step=step, kind="llm", name=tool_choice, status="llm_timeout",
                latency_ms=_elapsed_ms(started_at),
            ))
            logger.warning("agent llm step timed out step=%d tool_choice=%s", step, tool_choice)
            raise
        latency_ms = _elapsed_ms(started_at)
        state.agent.add_step(AgentStep(
            step=step, kind="llm", name=tool_choice, status="ok",
            latency_ms=latency_ms, finish_reason=turn.finish_reason,
        ))
        logger.info(
            "agent llm step=%d tool_choice=%s finish=%s tool_calls=%s latency_ms=%d",
            step, tool_choice, turn.finish_reason,
            ",".join(call.name for call in turn.tool_calls) or "-", latency_ms,
        )
        state.stats.record(LLMCall(
            stage=LLMStage.THINK,
            iteration=step,
            provider=self._provider.kind,
            model=self._provider.model,
            input_tokens=turn.usage.input_tokens,
            output_tokens=turn.usage.output_tokens,
            latency_ms=latency_ms,
        ))
        if turn.finish_reason == "length" and not turn.tool_calls:
            # Câu trả lời bị cắt vẫn được trả; tool call bị cắt sẽ thành tool_invalid_args.
            logger.warning("agent answer truncated by max_tokens step=%d", step)
        return turn

    async def _execute_unique(
        self,
        state: RunState,
        calls: Sequence[ToolCallRequest],
        allowed: set[str],
        timeout_s: float,
        sources: SourceAllocator,
        step: int,
        completed: dict[str, ToolOutcome],
        calls_per_tool: Counter[str],
    ) -> list[ToolOutcome]:
        """Như _execute, thêm hai kiểm soát theo khai báo của từng tool.

        - deduplicate: call trùng với call thành công ở bước trước, hoặc với call
          khác trong cùng response, dùng lại output (kể cả lỗi của call cùng
          response) với tool_call_id riêng. Call lỗi ở bước trước được thử lại.
          Tool không deduplicate (tool ghi) thì mỗi call đều chạy.
        - max_calls_per_turn: call vượt trần nhận tool_call_limit; call khác vẫn chạy.
        """
        keys: list[str] = []
        fresh: dict[str, ToolCallRequest] = {}
        limited: dict[str, int] = {}             # tool_call_id -> trần của tool
        for call in calls:
            spec = self._registry.get(call.name)
            key = _call_key(call) if spec is not None and spec.deduplicates else f"#{call.id}"
            keys.append(key)
            if key in completed or key in fresh:
                continue
            cap = spec.max_calls_per_turn if spec is not None else None
            if cap is not None and calls_per_tool[call.name] >= cap:
                limited[call.id] = cap
                continue
            calls_per_tool[call.name] += 1
            fresh[key] = call
        results = await self._execute(state, list(fresh.values()), allowed, timeout_s, sources, step)
        by_key = dict(zip(fresh, results))
        outcomes = []
        for call, key in zip(calls, keys):
            if call.id in limited:
                outcome = ToolOutcome(
                    tool_call_id=call.id,
                    name=call.name,
                    error_code=TOOL_CALL_LIMIT,
                    error_detail=f"{call.name} allows at most {limited[call.id]} calls per turn",
                )
                self._record_tool(state, step, outcome)
                outcomes.append(outcome)
                continue
            original = by_key.get(key)
            if original is not None and original.tool_call_id == call.id:
                outcomes.append(original)
                continue
            source = completed.get(key) or original
            assert source is not None
            outcome = ToolOutcome(
                tool_call_id=call.id,
                name=call.name,
                output=source.output,
                error_code=source.error_code,
                error_detail=source.error_detail,
            )
            self._record_tool(state, step, outcome, status=DEDUPLICATED)
            outcomes.append(outcome)
        completed.update({key: outcome for key, outcome in by_key.items() if outcome.ok})
        return outcomes

    async def _execute(
        self,
        state: RunState,
        calls: Sequence[ToolCallRequest],
        allowed: set[str],
        timeout_s: float,
        sources: SourceAllocator,
        step: int,
    ) -> list[ToolOutcome]:
        """Chạy các tool call của một response.

        Các call trong một response độc lập (LLM chưa thấy kết quả của nhau). Chỉ
        chạy song song khi provider cho phép và mọi tool đều read_only và
        concurrency_safe; ngược lại chạy tuần tự theo thứ tự call.
        """
        if not calls:
            return []
        specs = [self._registry.get(call.name) for call in calls]
        parallel = (
            len(calls) > 1
            and self._provider.capabilities.parallel_tool_calls
            and all(spec is not None and spec.read_only and spec.concurrency_safe for spec in specs)
        )
        if not parallel:
            return [
                await self._invoke(state, call, allowed, timeout_s, sources, step)
                for call in calls
            ]
        slots = asyncio.Semaphore(self._limits.parallel_tools)

        async def guarded(call: ToolCallRequest) -> ToolOutcome:
            async with slots:
                return await self._invoke(state, call, allowed, timeout_s, sources, step)

        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(guarded(call)) for call in calls]
        return [task.result() for task in tasks]

    async def _invoke(
        self,
        state: RunState,
        call: ToolCallRequest,
        allowed: set[str],
        timeout_s: float,
        sources: SourceAllocator,
        step: int,
    ) -> ToolOutcome:
        context = ToolContext(parent_state=state, sources=sources, tool_call_id=call.id)
        with span(f"tool.{call.name[:64]}", "tool", step=step, tool_call_id=call.id) as tool_span:
            outcome = await self._registry.invoke(call, context, allowed=allowed, timeout_s=timeout_s)
            if not outcome.ok:
                tool_span.fail(outcome.error_code or "tool_failed")
                _set_error_detail(tool_span, outcome)
        self._record_tool(state, step, outcome, executed=True)
        return outcome

    def _record_tool(
        self,
        state: RunState,
        step: int,
        outcome: ToolOutcome,
        status: str | None = None,
        executed: bool = False,
    ) -> None:
        assert state.agent is not None
        if not executed:
            # Call không chạy (gộp trùng, vượt trần, hết lượt/giờ): span tức thời để
            # trace vẫn đủ một mục cho mỗi tool_call_id.
            with span(f"tool.{outcome.name[:64]}", "tool", step=step, tool_call_id=outcome.tool_call_id) as skipped:
                skipped.fail(status or outcome.error_code or "tool_failed")
                if not outcome.ok:
                    _set_error_detail(skipped, outcome)
        state.agent.add_step(AgentStep(
            step=step,
            kind="tool",
            name=outcome.name,
            tool_call_id=outcome.tool_call_id,
            status=status or ("ok" if outcome.ok else outcome.error_code or "tool_failed"),
            latency_ms=outcome.latency_ms,
        ))
        # error_detail do tool viết (chỉ lý do, không chứa dữ liệu nhạy cảm).
        logger.info(
            "agent tool step=%d tool=%s status=%s latency_ms=%d detail=%s",
            step, outcome.name, status or ("ok" if outcome.ok else outcome.error_code),
            outcome.latency_ms, (outcome.error_detail or "-")[:300],
        )

    def _drop_unknown_citations(self, state: RunState, answer: str) -> str:
        """Bỏ [S#] không phải nguồn đã trả cho agent trong lượt (LLM bịa hoặc nhớ nhầm)."""
        assert state.agent is not None
        valid = set(state.sources()) | set(state.agent.source_texts)
        invalid: list[str] = []

        def keep(match: re.Match[str]) -> str:
            if match.group(1) in valid:
                return match.group(0)
            invalid.append(match.group(1))
            return ""

        cleaned = _CITATION.sub(keep, answer)
        if invalid:
            state.agent.invalid_citations = list(dict.fromkeys(invalid))
            logger.warning("agent answer cited unknown sources count=%d", len(invalid))
        return cleaned

    def _count(self, text: str) -> int:
        return count_tokens(text, self._provider.model)


def _set_error_detail(target: Any, outcome: ToolOutcome) -> None:
    """Lý do lỗi tool (do tool viết, đã gửi cho LLM) vào span; giá trị trong nháy bị che."""
    items = error_detail_items(outcome.error_detail)
    if items:
        target.set(error_detail=items)


def _call_key(call: ToolCallRequest) -> str:
    """Khóa so trùng: tên tool + argument đã chuẩn hóa (thứ tự key, khoảng trắng)."""
    try:
        arguments = json.loads(call.arguments_raw or "{}")
    except ValueError:
        return f"{call.name}:{call.arguments_raw}"
    normalized = json.dumps(_squash(arguments), sort_keys=True, ensure_ascii=False)
    return f"{call.name}:{normalized}"


def _squash(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        return [_squash(item) for item in value]
    if isinstance(value, dict):
        return {key: _squash(item) for key, item in value.items()}
    return value


def _assistant_message(turn: AssistantTurn) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": turn.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments_raw},
            }
            for call in turn.tool_calls
        ],
    }


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)
