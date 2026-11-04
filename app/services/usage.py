import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.models.schemas import (
    ModelUsageSummary,
    UsageLogEntry,
    UsageStatsResponse,
)


class UsageTracker:
    """Thread-safe usage tracker recording token counts, model calls, and costs."""

    def __init__(self, log_file: str = "logs/llm_usage.jsonl") -> None:
        self.log_file = Path(log_file)
        self._lock = threading.Lock()
        self._recent_logs: list[UsageLogEntry] = []
        self._breakdown_by_model: dict[str, ModelUsageSummary] = {}
        self._total_requests: int = 0
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tokens: int = 0
        self._total_cost_usd: float = 0.0

        # Ensure directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_existing_logs()

    def _load_existing_logs(self) -> None:
        """Load past usage logs from file if present."""
        if not self.log_file.exists():
            return
        try:
            with self.log_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    entry = UsageLogEntry(**data)
                    self._record_internal(entry, persist=False)
        except Exception:
            # Non-fatal if log file cannot be parsed
            pass

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        latency_ms: float,
        status: str = "success",
        fallback_triggered: bool = False,
    ) -> UsageLogEntry:
        """Record an LLM call with token counts and cost."""
        total_tokens = prompt_tokens + completion_tokens
        entry = UsageLogEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=round(cost_usd, 6),
            latency_ms=round(latency_ms, 2),
            status=status,
            fallback_triggered=fallback_triggered,
        )

        with self._lock:
            self._record_internal(entry, persist=True)

        return entry

    def _record_internal(self, entry: UsageLogEntry, persist: bool = True) -> None:
        self._total_requests += 1
        self._total_prompt_tokens += entry.prompt_tokens
        self._total_completion_tokens += entry.completion_tokens
        self._total_tokens += entry.total_tokens
        self._total_cost_usd = round(self._total_cost_usd + entry.cost_usd, 6)

        model_summary = self._breakdown_by_model.setdefault(entry.model, ModelUsageSummary())
        model_summary.requests += 1
        model_summary.prompt_tokens += entry.prompt_tokens
        model_summary.completion_tokens += entry.completion_tokens
        model_summary.total_tokens += entry.total_tokens
        model_summary.cost_usd = round(model_summary.cost_usd + entry.cost_usd, 6)

        self._recent_logs.insert(0, entry)
        if len(self._recent_logs) > 200:
            self._recent_logs.pop()

        if persist:
            try:
                with self.log_file.open("a", encoding="utf-8") as f:
                    f.write(entry.model_dump_json() + "\n")
            except Exception:
                pass

    def get_stats(self, limit: int = 50) -> UsageStatsResponse:
        """Retrieve aggregated usage statistics and recent logs."""
        with self._lock:
            return UsageStatsResponse(
                total_requests=self._total_requests,
                total_prompt_tokens=self._total_prompt_tokens,
                total_completion_tokens=self._total_completion_tokens,
                total_tokens=self._total_tokens,
                total_cost_usd=round(self._total_cost_usd, 6),
                breakdown_by_model={
                    k: ModelUsageSummary(**v.model_dump()) for k, v in self._breakdown_by_model.items()
                },
                recent_logs=list(self._recent_logs[:limit]),
            )

    def reset(self) -> None:
        """Reset all in-memory usage metrics and truncate log file."""
        with self._lock:
            self._recent_logs.clear()
            self._breakdown_by_model.clear()
            self._total_requests = 0
            self._total_prompt_tokens = 0
            self._total_completion_tokens = 0
            self._total_tokens = 0
            self._total_cost_usd = 0.0
            if self.log_file.exists():
                try:
                    self.log_file.write_text("", encoding="utf-8")
                except Exception:
                    pass
