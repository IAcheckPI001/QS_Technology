from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.pricing import ModelPrice, cost_usd, parse_price_overrides, price_for
from app.core.tracing import Trace, activate, span
from app.modules.chatbot.services import ChatbotService
from app.modules.chatbot.services.turn_sources import history_item, usage_info
from app.modules.chatbot.services.turn_usage import usage_from_trace


def _agent_like_trace() -> Trace:
    """Một lượt agent: 2 lần gọi gpt-4.1-mini (có cache), 1 lần phân tích gpt-4o-mini, 1 embedding."""
    trace = Trace("req-12345678", root_name="chat.request")
    with activate(trace):
        with span("llm.chat_tools", "llm", model="gpt-4.1-mini") as first:
            first.set(input_tokens=20_000, cached_input_tokens=10_000, output_tokens=100)
        with span("llm.chat_tools", "llm", model="gpt-4.1-mini") as second:
            second.set(input_tokens=11_168, output_tokens=159)
        with span("llm.chat_json", "llm", model="gpt-4o-mini") as analysis:
            analysis.set(input_tokens=1_000, output_tokens=50)
        with span("embedding", "embedding", model="text-embedding-3-small") as embed:
            embed.set(input_tokens=14)
        with span("db.fetch_chunks", "db"):
            pass
    trace.finish()
    return trace


def test_price_lookup_matches_exact_then_longest_versioned_prefix():
    assert price_for("gpt-4.1-mini") == ModelPrice(input=0.40, cached_input=0.10, output=1.60)
    # Không nhầm gpt-4.1-mini-… thành gpt-4.1.
    assert price_for("gpt-4.1-mini-2025-04-14").input == 0.40
    assert price_for("GPT-4o-mini").output == 0.60
    assert price_for("unknown-model") is None
    overrides = {"gpt-4.1-mini": ModelPrice(input=1.0, output=2.0)}
    assert price_for("gpt-4.1-mini", overrides).input == 1.0


def test_cost_uses_cached_rate_for_cached_part_of_input():
    price = ModelPrice(input=0.40, cached_input=0.10, output=1.60)
    # 10k thường × 0,40 + 10k cache × 0,10 + 100 × 1,60 (USD / 1 triệu)
    assert cost_usd(price, input_tokens=20_000, cached_input_tokens=10_000, output_tokens=100) == pytest.approx(0.00516)


@pytest.mark.parametrize("raw", ["[]", '{"m": 1}', '{"m": {"output": 1}}', '{"m": {"input": -1}}', "not json"])
def test_price_overrides_reject_bad_json(raw):
    with pytest.raises(ValueError):
        parse_price_overrides(raw)


def test_usage_from_trace_sums_every_call_and_prices_each_model():
    usage = usage_from_trace(_agent_like_trace())

    assert usage.source == "trace"
    assert usage.llm_calls == 3
    assert (usage.input_tokens, usage.cached_input_tokens, usage.output_tokens) == (32_168, 10_000, 309)
    assert usage.embedding_tokens == 14
    expected = (
        (21_168 * 0.40 + 10_000 * 0.10 + 259 * 1.60)  # gpt-4.1-mini
        + (1_000 * 0.15 + 50 * 0.60)  # gpt-4o-mini
        + 14 * 0.02  # embedding
    ) / 1_000_000
    assert usage.cost_usd == pytest.approx(expected)
    assert {(item["kind"], item["model"]) for item in usage.by_model} == {
        ("llm", "gpt-4.1-mini"), ("llm", "gpt-4o-mini"), ("embedding", "text-embedding-3-small"),
    }
    assert usage.unpriced_models == []


def test_unknown_model_is_reported_not_priced():
    trace = Trace("req-12345678", root_name="chat.request")
    with activate(trace), span("llm.chat_text", "llm", model="mystery-1") as call:
        call.set(input_tokens=500, output_tokens=10)
    usage = usage_from_trace(trace)
    assert usage.cost_usd == 0
    assert usage.unpriced_models == ["mystery-1"]
    assert usage.input_tokens == 500


def test_turn_record_writes_real_usage_from_active_trace():
    service = SimpleNamespace(
        _provider=SimpleNamespace(model="gpt-4o-mini"),
        _retrieval_snapshot=lambda state: {"chunks": [], "retrieval_status": "not_applicable"},
    )
    service._usage = lambda message, answer: ChatbotService._usage(service, message, answer)
    trace = _agent_like_trace()

    with activate(trace):
        record = ChatbotService._turn_record(service, SimpleNamespace(), "Câu hỏi", "Trả lời")

    assert record["input_tokens"] == 32_168
    assert record["output_tokens"] == 309
    assert record["cost_usd"] > 0.005
    assert record["retrieval_snapshot"]["usage"]["source"] == "trace"
    assert record["retrieval_snapshot"]["usage"]["llm_calls"] == 3


def test_turn_record_without_trace_keeps_old_estimate():
    service = SimpleNamespace(
        _provider=SimpleNamespace(model="gpt-4o-mini"),
        _retrieval_snapshot=lambda state: {"chunks": []},
    )
    service._usage = lambda message, answer: ChatbotService._usage(service, message, answer)

    record = ChatbotService._turn_record(service, SimpleNamespace(), "Xin chào", "Chào bạn")

    assert record["retrieval_snapshot"]["usage"]["source"] == "estimate"
    assert record["input_tokens"] > 0


def _row(**extra):
    now = datetime.now(timezone.utc)
    base = dict(
        id=uuid4(), session_id=uuid4(), query_origin="q", answer="a", status="completed",
        created_at=now, updated_date=now, channel="crm", model="gpt-4.1-mini",
        input_tokens=0, output_tokens=0, total_tokens=0, cost_usd=None, latency_ms=100, retrieval_snapshot=None,
    )
    base.update(extra)
    return SimpleNamespace(**base)


def test_history_item_reports_usage_source_and_vnd_cost():
    real = history_item(_row(
        input_tokens=31_168, output_tokens=259, total_tokens=31_427, cost_usd=0.0129,
        retrieval_snapshot={"chunks": [], "usage": {"source": "trace", "llm_calls": 6, "cached_input_tokens": 0,
                                                    "embedding_tokens": 14, "unpriced_models": []}},
    ), 26_000)
    assert real.usage.source == "trace"
    assert real.usage.llm_calls == 6
    assert real.cost_vnd == pytest.approx(335.4)

    old = history_item(_row(input_tokens=14, output_tokens=40, total_tokens=54, cost_usd=0.000026,
                            retrieval_snapshot={"chunks": []}), 26_000)
    assert old.usage.source == "estimate"

    # Lượt không gọi AI (bị chặn): không có nguồn số liệu.
    assert usage_info(_row(status="blocked")) is None
