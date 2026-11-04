"""Cost logging: one JSON line per LLM call."""

import json
import time
from pathlib import Path
from typing import Any


def _get_attr(obj: Any, name: str, default: Any = 0) -> Any:
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default


def cost_usd(usage: Any, price_in_per_m: float, price_out_per_m: float) -> float:
    input_tokens = _get_attr(usage, "input_tokens", 0)
    output_tokens = _get_attr(usage, "output_tokens", 0)
    return (input_tokens * price_in_per_m + output_tokens * price_out_per_m) / 1_000_000


def log_call(
    path: str,
    *,
    provider: str,
    model: str,
    usage: Any,
    latency_ms: float,
    price_in_per_m: float,
    price_out_per_m: float,
    ok: bool,
    fallback_used: bool = False,
) -> dict:
    input_tokens = _get_attr(usage, "input_tokens", 0)
    output_tokens = _get_attr(usage, "output_tokens", 0)
    estimated = _get_attr(usage, "estimated", False)

    record = {
        "ts": round(time.time(), 3),
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "usage_estimated": estimated,
        "latency_ms": round(latency_ms, 1),
        "cost_usd": round(cost_usd(usage, price_in_per_m, price_out_per_m), 8),
        "ok": ok,
        "fallback_used": fallback_used,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record
