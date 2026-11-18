"""Usage và chi phí thật của một lượt chat (B3, FRONTEND_REQUIREMENTS M2/Q4).

Cộng usage do OpenAI trả về của mọi lần gọi AI và embedding trong lượt (đọc từ trace đang chạy,
`Trace.usage_by_model`), đổi ra USD theo giá từng model (`core/pricing.py`). Không có trace thì
giữ cách ước tính cũ từ chữ câu hỏi/câu trả lời, ghi rõ `source = "estimate"`.

Ghi vào `chat_history`:
- cột `input_tokens` / `output_tokens` (và `total_tokens` tính từ hai cột này): token của lời gọi AI,
  không gồm embedding; `cost_usd`: gồm cả embedding;
- chi tiết ở `retrieval_snapshot["usage"]` (khoá chỉ thêm, không cần SQL): nguồn số liệu, số lần gọi,
  token cache, token embedding, từng model, model chưa có giá.
"""

from dataclasses import dataclass, field

from app.core.pricing import ModelPrice, cost_usd, price_for
from app.core.tracing import Trace

USAGE_SOURCE_TRACE = "trace"
USAGE_SOURCE_ESTIMATE = "estimate"


@dataclass(frozen=True)
class TurnUsage:
    source: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    embedding_tokens: int = 0
    llm_calls: int = 0
    cost_usd: float = 0.0
    by_model: list[dict] = field(default_factory=list)
    # Model gặp trong lượt nhưng chưa có giá: chi phí của chúng không được cộng.
    unpriced_models: list[str] = field(default_factory=list)

    def columns(self) -> dict:
        """Giá trị cho các cột của chat_history."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 8),
        }

    def detail(self) -> dict:
        """Chi tiết lưu ở retrieval_snapshot["usage"] (chỉ metadata)."""
        return {
            "source": self.source,
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "embedding_tokens": self.embedding_tokens,
            "cost_usd": round(self.cost_usd, 8),
            "by_model": self.by_model,
            "unpriced_models": self.unpriced_models,
        }


def usage_from_trace(trace: Trace, overrides: dict[str, ModelPrice] | None = None) -> TurnUsage:
    """Usage thật của lượt từ các span `llm`/`embedding` của trace."""
    totals = {"input": 0, "cached": 0, "output": 0, "embedding": 0, "calls": 0}
    cost = 0.0
    by_model: list[dict] = []
    unpriced: list[str] = []
    for group in trace.usage_by_model():
        kind, model = str(group["kind"]), str(group["model"])
        input_tokens = int(group["input_tokens"])
        cached = int(group["cached_input_tokens"])
        output = int(group["output_tokens"])
        price = price_for(model, overrides)
        item_cost = cost_usd(price, input_tokens=input_tokens, cached_input_tokens=cached, output_tokens=output) if price else None
        if price is None and (input_tokens or output):
            unpriced.append(model)
        cost += item_cost or 0.0
        if kind == "embedding":
            totals["embedding"] += input_tokens
        else:
            totals["input"] += input_tokens
            totals["cached"] += cached
            totals["output"] += output
            totals["calls"] += int(group["calls"])
        by_model.append({
            "kind": kind, "model": model, "calls": int(group["calls"]),
            "input_tokens": input_tokens, "cached_input_tokens": cached, "output_tokens": output,
            "cost_usd": None if item_cost is None else round(item_cost, 8),
        })
    return TurnUsage(
        source=USAGE_SOURCE_TRACE,
        input_tokens=totals["input"],
        output_tokens=totals["output"],
        cached_input_tokens=totals["cached"],
        embedding_tokens=totals["embedding"],
        llm_calls=totals["calls"],
        cost_usd=cost,
        by_model=by_model,
        unpriced_models=sorted(set(unpriced)),
    )
