import json
from pathlib import Path

from app.cost import cost_usd, log_call
from app.llm.types import Usage


def test_cost_calculation():
    usage = Usage(input_tokens=1200, output_tokens=300)
    # 1,200 * 0.50 + 300 * 1.50 = 600 + 450 = 1050 / 1_000_000 = 0.00105
    price = cost_usd(usage, price_in_per_m=0.50, price_out_per_m=1.50)
    assert round(price, 8) == 0.00105


def test_log_call_records_jsonl(tmp_path):
    log_path = str(tmp_path / "cost.jsonl")
    usage = Usage(input_tokens=100, output_tokens=50)
    record = log_call(
        log_path,
        provider="test-provider",
        model="test-model",
        usage=usage,
        latency_ms=123.4,
        price_in_per_m=0.5,
        price_out_per_m=1.5,
        ok=True,
        fallback_used=False,
    )
    assert record["cost_usd"] == 0.000125
    lines = Path(log_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["model"] == "test-model"
    assert saved["input_tokens"] == 100


def test_usage_totals_per_day(client, tmp_path):
    log = [
        {"ts": 1792800000.0, "input_tokens": 1200, "output_tokens": 300, "cost_usd": 0.00105},  # 2026-10-24
        {"ts": 1792810000.0, "input_tokens": 800, "output_tokens": 200, "cost_usd": 0.0007},  # 2026-10-24
        {"ts": 1792900000.0, "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.000125},  # 2026-10-25
    ]
    path = client.settings.cost_log_path
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in log) + "\n{half-written line\n")
    r = client.get("/usage")
    assert r.status_code == 200
    assert r.json() == {
        "2026-10-24": {"calls": 2, "input_tokens": 2000, "output_tokens": 500, "cost_usd": 0.00175},
        "2026-10-25": {"calls": 1, "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.000125},
    }
