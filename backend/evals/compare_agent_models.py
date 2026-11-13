"""So sánh model cho vòng lặp agent CRM trên cùng bộ case (thủ công, không chạy trong CI).

Mỗi model chạy N lần các case nhóm crm_query của `crm_agent_cases.json` (hoặc các case truyền
vào), dùng lại `run_case`/`_check` của `run_crm_agent_eval.py`. Stage phân tích trong
product_docs_ask vẫn dùng OPENAI_MODEL, đúng như khi đặt AGENT_MODEL lúc chạy thật.

In bảng cho mỗi model: số lần đạt từng case, số bước LLM (trung bình và phân phối), số lần
crm_query ra rỗng/bị CRM từ chối, lỗi tool theo mã (crm_forbidden, tool_call_limit, ...), token
vào/ra, phần token cố định (system prompt + định nghĩa tool gửi lại ở mỗi bước) và latency mỗi
lượt (p50/p95). Không in dữ liệu CRM; chi tiết từng lượt (query gửi CRM, câu trả lời) ghi vào
file --log nếu có, số đo có cấu trúc ghi vào file --json để so giữa các đợt đo.

Chạy từ thư mục backend (cần OPENAI_API_KEY, CRM_REPORT_ENABLED=true, CRM_API_BASE_URL trong
.env; token CRM chỉ qua biến môi trường). File --log/--json có dữ liệu CRM thật: ghi ra ngoài repo.

    $env:CRM_EVAL_ACCESS_TOKEN = "<token>"; $env:CRM_REPORT_ENABLED = "true"
    .\\venv\\Scripts\\python.exe evals\\compare_agent_models.py --models gpt-4o-mini gpt-4.1 gpt-5-mini `
        --runs 3 [--cases q9_customers_of_staff_by_name ...] [--effort low] [--log out.txt] [--json out.json]

Model suy luận (gpt-5…, o3…) chạy với AGENT_MAX_COMPLETION_TOKENS = 4000 nếu chưa đặt lớn hơn.
"""

import argparse
import asyncio
import contextlib
import io
import json
import re
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_crm_agent_eval as ev  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.modules.chatbot.agent.runner import AgentError  # noqa: E402
from app.modules.chatbot.providers.openai import OpenAIProvider, is_reasoning_model  # noqa: E402
from app.util.token_counter import count_tokens  # noqa: E402

REASONING_MIN_COMPLETION_TOKENS = 4000


class MeteredProvider(ev.RecordingProvider):
    """Đếm bước LLM, token, phần token cố định và lỗi tool của vòng lặp agent."""

    def __init__(self, provider: OpenAIProvider) -> None:
        super().__init__(provider)
        self.reset()

    def reset(self) -> None:
        self.steps = self.input_tokens = self.output_tokens = 0
        self.fixed_tokens = 0                 # tổng qua mọi bước: system prompt + định nghĩa tool
        self.tool_errors: list[str] = []      # mã lỗi mọi message role=tool của mọi lượt
        self._seen_tool_calls: set[str] = set()

    async def chat_complete_tools(self, messages, tools, **options):
        self._scan_tool_errors(messages)
        turn = await super().chat_complete_tools(messages, tools, **options)
        self.steps += 1
        self.input_tokens += turn.usage.input_tokens
        self.output_tokens += turn.usage.output_tokens
        system = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        self.fixed_tokens += count_tokens(system + json.dumps(tools, ensure_ascii=False), self.model)
        return turn

    def _scan_tool_errors(self, messages) -> None:
        """Message role=tool mới (chưa thấy ở bước trước): ghi mã lỗi nếu có."""
        for message in messages:
            if message["role"] != "tool" or message["tool_call_id"] in self._seen_tool_calls:
                continue
            self._seen_tool_calls.add(message["tool_call_id"])
            try:
                payload = json.loads(message["content"])
            except ValueError:
                continue
            if isinstance(payload, dict) and "error" in payload:
                self.tool_errors.append(str(payload["error"]))


class OutcomeCollector(ev.AuditCollector):
    """Như AuditCollector, giữ thêm outcome crm_query của mọi lượt (run_case chỉ giữ lượt cuối)."""

    def __init__(self) -> None:
        super().__init__()
        self.outcomes: list[str] = []
        self.reject_reasons: list[str] = []

    def emit(self, record) -> None:
        super().emit(record)
        item = self.records[-1]
        self.outcomes.append(item.get("outcome", "?"))
        if item.get("outcome") in ("rejected", "invalid_args"):
            self.reject_reasons.extend(reject_reasons(item.get("error_detail") or ""))


# Lý do query bị chặn trước khi tới CRM, theo thông điệp của compile_raw/values.py.
_REJECT_PATTERNS = (
    ("date_filter", "is a date column"),
    ("uuid", "uuid column"),
    ("enum", "allows only"),
    ("number", "not a number"),
    ("bool", "use true or false"),
    ("path", "is not available"),
    ("path", "has no relation"),
    ("date_range", "date_range:"),
)


def reject_reasons(detail: str) -> list[str]:
    """Mỗi lỗi trong detail (nối bằng '; ') → một nhóm lý do; không khớp → 'other'."""
    reasons = []
    for part in filter(None, (piece.strip() for piece in detail.split("; "))):
        if part.startswith("check relations"):      # đuôi của lỗi "has no relation ...; check ..."
            continue
        reasons.append(next((name for name, text in _REJECT_PATTERNS if text in part), "other"))
    return reasons


@dataclass
class RunRecord:
    model: str
    case: str
    attempt: int
    passed: bool
    failures: list[str]
    steps: int
    input_tokens: int
    output_tokens: int
    fixed_tokens: int
    latency_s: float
    tool_errors: list[str]
    query_outcomes: list[str]
    error: str | None = None          # mã AgentError hoặc tên exception khi lượt không chạy xong
    reject_reasons: list[str] = field(default_factory=list)   # query bị chặn trước CRM, theo lý do
    # Đạt nếu bỏ qua giới hạn số lần gọi (tool_calls_max, query_attempts_max): tách lỗi "sai" với
    # lỗi "tốn bước" (eval 2026-11-12: r2, q3 lấy đúng dữ liệu nhưng gọi thêm tool tra tên).
    passed_ignoring_budget: bool = False


_BUDGET_FAILURE = re.compile(r"^(tool calls \d+ > \d+|crm_query \d+ lần > \d+)$")


def passed_ignoring_budget(failures: list[str]) -> bool:
    return all(_BUDGET_FAILURE.match(failure) for failure in failures)


@dataclass
class CaseStats:
    passed: int = 0
    runs: int = 0
    failures: list[str] = field(default_factory=list)


@dataclass
class ModelStats:
    cases: dict[str, CaseStats] = field(default_factory=dict)
    runs: list[RunRecord] = field(default_factory=list)

    @property
    def steps(self) -> list[int]:
        return [run.steps for run in self.runs]

    @property
    def latency_s(self) -> list[float]:
        return [run.latency_s for run in self.runs]

    def outcome_count(self, outcome: str) -> int:
        return sum(run.query_outcomes.count(outcome) for run in self.runs)

    def tool_error_counts(self) -> Counter[str]:
        return Counter(code for run in self.runs for code in run.tool_errors)

    def reject_reason_counts(self) -> Counter[str]:
        return Counter(reason for run in self.runs for reason in run.reject_reasons)

    def run_errors(self) -> Counter[str]:
        return Counter(run.error for run in self.runs if run.error)

    def fixed_share(self) -> float | None:
        total = sum(run.input_tokens for run in self.runs)
        return sum(run.fixed_tokens for run in self.runs) / total if total else None


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]


async def run_model(model: str, cases: list[dict[str, Any]], runs: int, effort: str | None, log) -> ModelStats:
    base = OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model,
                          embedding_model=settings.embedding_model)
    loop_base = OpenAIProvider(api_key=settings.openai_api_key, model=model,
                               embedding_model=settings.embedding_model, reasoning_effort=effort)
    metered = MeteredProvider(loop_base)
    max_tokens = settings.agent_max_completion_tokens
    if is_reasoning_model(model):
        max_tokens = max(max_tokens, REASONING_MIN_COMPLETION_TOKENS)
    run_settings = settings.model_copy(update={
        "crm_query_audit_log": True, "agent_model": model, "agent_max_completion_tokens": max_tokens,
    })
    retriever = ev.Retriever(base, ev.DocChunkRepository(), ev.RetrieverConfig.from_settings(settings))
    runner = ev.build_agent_runner(base, retriever, run_settings, agent_provider=metered)  # type: ignore[arg-type]
    audit = OutcomeCollector()
    audit_logger = ev.logging.getLogger(ev.AUDIT_LOGGER)
    audit_logger.addHandler(audit)
    audit_logger.propagate = False
    stats = ModelStats()
    try:
        for case in cases:
            case_stats = stats.cases.setdefault(case["id"], CaseStats())
            for attempt in range(runs):
                metered.reset()
                audit.outcomes = []
                audit.reject_reasons = []
                buffer = io.StringIO()
                error: str | None = None
                started = time.perf_counter()
                try:
                    with contextlib.redirect_stdout(buffer):
                        failures = await ev.run_case(runner, metered, audit, case)
                except AgentError as exc:
                    failures = [f"lỗi agent: {exc.code}"]
                    error = exc.code
                except Exception as exc:  # noqa: BLE001 - một lượt lỗi không dừng cả đợt đo
                    failures = [f"lỗi chạy: {type(exc).__name__}: {str(exc)[:160]}"]
                    error = type(exc).__name__
                elapsed = time.perf_counter() - started
                case_stats.runs += 1
                case_stats.passed += not failures
                case_stats.failures.extend(failures)
                stats.runs.append(RunRecord(
                    model=model, case=case["id"], attempt=attempt + 1, passed=not failures,
                    failures=failures, steps=metered.steps, input_tokens=metered.input_tokens,
                    output_tokens=metered.output_tokens, fixed_tokens=metered.fixed_tokens,
                    latency_s=round(elapsed, 2), tool_errors=list(metered.tool_errors),
                    query_outcomes=list(audit.outcomes), error=error,
                    reject_reasons=list(audit.reject_reasons),
                    passed_ignoring_budget=passed_ignoring_budget(failures),
                ))
                output = buffer.getvalue()
                if log is not None:
                    log.write(f"\n===== {model} | {case['id']} | lần {attempt + 1} | {elapsed:.1f}s "
                              f"| {'PASS' if not failures else 'FAIL'}\n{output}")
                    if failures:
                        log.write("  FAIL: " + "; ".join(failures) + "\n")
                print(f"  {model} {case['id']} #{attempt + 1}: {'PASS' if not failures else 'FAIL'} "
                      f"({metered.steps} bước, {elapsed:.1f}s)", flush=True)
    finally:
        audit_logger.removeHandler(audit)
        await base.close()
        await loop_base.close()
    return stats


def _counts(counter: Counter[Any]) -> str:
    return ", ".join(f"{key}:{value}" for key, value in sorted(counter.items())) or "-"


def report(results: dict[str, ModelStats], cases: list[dict[str, Any]]) -> None:
    models = list(results)
    width = max(*(len(case["id"]) for case in cases), len("% token cố định"))
    print("\n" + "case".ljust(width) + "  " + "  ".join(model.rjust(14) for model in models))
    for case in cases:
        cells = []
        for model in models:
            item = results[model].cases.get(case["id"], CaseStats())
            cells.append(f"{item.passed}/{item.runs}".rjust(14))
        print(case["id"].ljust(width) + "  " + "  ".join(cells))

    def share(stats: ModelStats) -> str:
        value = stats.fixed_share()
        return f"{value:.0%}" if value is not None else "-"

    rows = [
        ("tổng đạt", lambda s: f"{sum(c.passed for c in s.cases.values())}/{sum(c.runs for c in s.cases.values())}"),
        ("đạt bỏ giới hạn gọi", lambda s: f"{sum(r.passed_ignoring_budget for r in s.runs)}/{len(s.runs)}"),
        ("bước LLM tb", lambda s: f"{statistics.mean(s.steps):.1f}" if s.steps else "-"),
        ("query rỗng", lambda s: str(s.outcome_count("empty"))),
        ("CRM từ chối", lambda s: str(s.outcome_count("crm_invalid"))),
        ("query bị chặn", lambda s: str(s.outcome_count("rejected") + s.outcome_count("invalid_args"))),
        ("lỗi chạy", lambda s: str(sum(s.run_errors().values()))),
        ("token vào tb", lambda s: f"{statistics.mean(r.input_tokens for r in s.runs):.0f}" if s.runs else "-"),
        ("token ra tb", lambda s: f"{statistics.mean(r.output_tokens for r in s.runs):.0f}" if s.runs else "-"),
        ("% token cố định", share),
        ("latency p50 s", lambda s: f"{statistics.median(s.latency_s):.1f}" if s.latency_s else "-"),
        ("latency p95 s", lambda s: f"{_p95(s.latency_s):.1f}" if s.latency_s else "-"),
    ]
    print("-" * (width + 16 * len(models)))
    for label, value in rows:
        print(label.ljust(width) + "  " + "  ".join(value(results[model]).rjust(14) for model in models))

    # Phân bố và mã lỗi có độ dài thay đổi: in theo từng model thay vì theo cột.
    for model in models:
        stats = results[model]
        print(f"\n[{model}]")
        print(f"  phân phối bước : {_counts(Counter(stats.steps))}")
        print(f"  lỗi tool       : {_counts(stats.tool_error_counts())}")
        print(f"  lỗi chạy       : {_counts(stats.run_errors())}")
        print(f"  chặn theo lý do: {_counts(stats.reject_reason_counts())}")


def summary(stats: ModelStats) -> dict[str, Any]:
    return {
        "passed": sum(run.passed for run in stats.runs),
        "passed_ignoring_budget": sum(run.passed_ignoring_budget for run in stats.runs),
        "runs": len(stats.runs),
        "steps_mean": statistics.mean(stats.steps) if stats.steps else None,
        "steps_distribution": dict(sorted(Counter(stats.steps).items())),
        "query_outcomes": dict(Counter(o for run in stats.runs for o in run.query_outcomes)),
        "tool_errors": dict(stats.tool_error_counts()),
        "run_errors": dict(stats.run_errors()),
        "reject_reasons": dict(stats.reject_reason_counts()),
        "input_tokens_mean": statistics.mean(r.input_tokens for r in stats.runs) if stats.runs else None,
        "output_tokens_mean": statistics.mean(r.output_tokens for r in stats.runs) if stats.runs else None,
        "fixed_token_share": stats.fixed_share(),
        "latency_p50_s": statistics.median(stats.latency_s) if stats.latency_s else None,
        "latency_p95_s": _p95(stats.latency_s) if stats.latency_s else None,
    }


def write_json(path: str, results: dict[str, ModelStats], args: argparse.Namespace) -> None:
    payload = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "config": {
            "crm_tools": settings.crm_tools,
            "openai_model": settings.openai_model,
            "agent_max_steps": settings.agent_max_steps,
            "agent_max_tool_calls": settings.agent_max_tool_calls,
            "agent_max_completion_tokens": settings.agent_max_completion_tokens,
            "effort": args.effort,
            "runs": args.runs,
        },
        "models": {
            model: {"summary": summary(stats), "runs": [asdict(run) for run in stats.runs]}
            for model, stats in results.items()
        },
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--cases", nargs="*", default=[])
    parser.add_argument("--effort", default=None, help="reasoning_effort cho model suy luận")
    parser.add_argument("--log", default=None, help="file ghi chi tiết từng lượt")
    parser.add_argument("--json", default=None, help="file ghi số đo có cấu trúc (so giữa các đợt)")
    args = parser.parse_args()
    if not settings.openai_api_key or not settings.crm_report_enabled:
        print("Cần OPENAI_API_KEY và CRM_REPORT_ENABLED=true.")
        return 2
    all_cases = json.loads(ev.CASES.read_text(encoding="utf-8"))["cases"]
    if args.cases:
        cases = [case for case in all_cases if case["id"] in args.cases]
    else:
        cases = [case for case in all_cases if case.get("group") == "crm_query"]
    log = open(args.log, "w", encoding="utf-8") if args.log else None  # noqa: SIM115
    results: dict[str, ModelStats] = {}
    try:
        for model in args.models:
            print(f"[{model}]", flush=True)
            results[model] = await run_model(model, cases, args.runs, args.effort, log)
    finally:
        if log is not None:
            log.close()
    report(results, cases)
    if args.json:
        write_json(args.json, results, args)
        print(f"\nĐã ghi {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
