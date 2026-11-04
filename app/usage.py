"""Added for Session 5: totals per day (UTC) from logs/cost.jsonl, for GET /usage."""

import json
from datetime import UTC, datetime
from pathlib import Path


def usage_by_day(path: str) -> dict[str, dict]:
    days: dict[str, dict] = {}
    p = Path(path)
    if not p.exists():
        return days
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue  # skip a blank or half-written line instead of failing the whole report
        day = datetime.fromtimestamp(r["ts"], tz=UTC).date().isoformat()
        d = days.setdefault(
            day,
            {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            },
        )
        d["calls"] += 1
        d["input_tokens"] += r["input_tokens"]
        d["output_tokens"] += r["output_tokens"]
        d["cost_usd"] = round(d["cost_usd"] + r["cost_usd"], 8)
    return days
