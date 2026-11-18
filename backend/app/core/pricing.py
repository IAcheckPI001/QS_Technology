"""Bảng giá model của nhà cung cấp AI (USD / 1 triệu token) để đổi usage thật ra chi phí (B3).

Giá mặc định theo bảng giá OpenAI đã biết lúc viết (2026-11-18), **cần đối chiếu định kỳ** với
trang giá của OpenAI; ghi đè bằng biến `LLM_PRICES_JSON` không cần đổi code, vd.
`{"gpt-4.1-mini": {"input": 0.4, "cached_input": 0.1, "output": 1.6}}`.
Tên model có hậu tố phiên bản (vd `gpt-4.1-mini-2025-04-14`) khớp theo tiền tố dài nhất.
"""

import json
from dataclasses import dataclass

TOKENS_PER_UNIT = 1_000_000


@dataclass(frozen=True)
class ModelPrice:
    input: float
    output: float = 0.0
    # Token vào được cache (một phần của input_tokens); None = tính như input thường.
    cached_input: float | None = None


DEFAULT_PRICES: dict[str, ModelPrice] = {
    "gpt-4o-mini": ModelPrice(input=0.15, cached_input=0.075, output=0.60),
    "gpt-4o": ModelPrice(input=2.50, cached_input=1.25, output=10.00),
    "gpt-4.1-nano": ModelPrice(input=0.10, cached_input=0.025, output=0.40),
    "gpt-4.1-mini": ModelPrice(input=0.40, cached_input=0.10, output=1.60),
    "gpt-4.1": ModelPrice(input=2.00, cached_input=0.50, output=8.00),
    "text-embedding-3-small": ModelPrice(input=0.02),
    "text-embedding-3-large": ModelPrice(input=0.13),
}


def parse_price_overrides(raw: str) -> dict[str, ModelPrice]:
    """`LLM_PRICES_JSON` → bảng giá ghi đè. Sai dạng thì ném ValueError (Settings báo lỗi khi khởi động)."""
    if not raw or not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM_PRICES_JSON must be a JSON object of model -> prices")
    prices: dict[str, ModelPrice] = {}
    for model, item in data.items():
        if not isinstance(model, str) or not model or not isinstance(item, dict):
            raise ValueError(f"invalid price entry for {model!r}")
        values = {key: item.get(key) for key in ("input", "output", "cached_input")}
        for key, value in values.items():
            if value is not None and (not isinstance(value, int | float) or isinstance(value, bool) or value < 0):
                raise ValueError(f"invalid {key} price for {model!r}")
        if values["input"] is None:
            raise ValueError(f"missing input price for {model!r}")
        prices[model] = ModelPrice(
            input=float(values["input"]),
            output=float(values["output"] or 0.0),
            cached_input=None if values["cached_input"] is None else float(values["cached_input"]),
        )
    return prices


def price_for(model: str, overrides: dict[str, ModelPrice] | None = None) -> ModelPrice | None:
    """Giá của model: ghi đè trước, rồi bảng mặc định; khớp chính xác hoặc tiền tố dài nhất."""
    name = (model or "").strip().lower()
    if not name:
        return None
    for table in (overrides or {}, DEFAULT_PRICES):
        lowered = {key.lower(): value for key, value in table.items()}
        if name in lowered:
            return lowered[name]
        prefixes = [key for key in lowered if name.startswith(key + "-")]
        if prefixes:
            return lowered[max(prefixes, key=len)]
    return None


def cost_usd(price: ModelPrice, *, input_tokens: int, cached_input_tokens: int = 0, output_tokens: int = 0) -> float:
    """Chi phí USD: phần input được cache tính theo giá cache (nếu model có), phần còn lại giá thường."""
    cached = min(max(cached_input_tokens, 0), max(input_tokens, 0))
    uncached = max(input_tokens, 0) - cached
    cached_rate = price.input if price.cached_input is None else price.cached_input
    total = uncached * price.input + cached * cached_rate + max(output_tokens, 0) * price.output
    return total / TOKENS_PER_UNIT
