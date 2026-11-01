"""Execution tracing, JSONL persistence, and cost accounting."""
from __future__ import annotations

import json
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from research_agent.schemas import RunMetrics


class Tracer:
    """Collects execution spans, events, JSONL traces, and resource metrics during an agent run."""

    def __init__(
        self,
        run_id: str | None = None,
        runs_dir: str | Path | None = "runs",
        price_in: float = 0.0,
        price_out: float = 0.0,
        metrics: RunMetrics | None = None,
    ) -> None:
        if run_id:
            self.run_id = run_id
        else:
            time_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            self.run_id = f"{time_str}-{uuid.uuid4().hex[:6]}"

        self.runs_dir: Path | None = Path(runs_dir) if runs_dir else None
        self.price_in = price_in
        self.price_out = price_out
        self.metrics: RunMetrics = metrics or RunMetrics()
        self._start_time = time.monotonic()
        self._lock = threading.Lock()

        self.spans: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def _now_ms(self) -> float:
        return round(time.time() * 1000.0, 2)

    def _emit(self, record: dict[str, Any]) -> None:
        self._write_jsonl(record)

    def _write_jsonl(self, entry: dict[str, Any]) -> None:
        """Append an entry as a JSON object line to the run trace file."""
        if not self.runs_dir:
            return
        with self._lock:
            try:
                self.runs_dir.mkdir(parents=True, exist_ok=True)
                file_path = self.runs_dir / f"{self.run_id}.jsonl"
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception:
                pass  # Tracing must never crash the main application

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[dict[str, Any]]:
        """Measure execution time of a processing phase, recording status, duration, and errors."""
        start_t = time.monotonic()
        start_ms = time.time() * 1000.0
        record: dict[str, Any] = {
            "span": name,
            "name": name,  # For backwards-compatibility
            "status": "ok",
            **attrs,
        }
        try:
            yield record
        except Exception as exc:
            if record.get("status") == "ok":
                record["status"] = "error"
            record["error"] = str(exc)
            raise
        finally:
            duration_ms = (time.monotonic() - start_t) * 1000.0
            record["start_ms"] = round(start_ms, 2)
            record["duration_ms"] = round(duration_ms, 2)
            record["duration_s"] = round(duration_ms / 1000.0, 4)
            with self._lock:
                self.spans.append(record)
            self._emit(record)

    def event(self, name: str, **kwargs: Any) -> None:
        """Record an annotated timestamped event during pipeline execution."""
        record: dict[str, Any] = {
            "event": name,
            "name": name,  # For backwards-compatibility
            "timestamp_ms": self._now_ms(),
            **kwargs,
        }
        with self._lock:
            self.events.append(record)
        self._emit(record)

    def record_llm(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        purpose: str = "",
        cost_usd: float | None = None,
    ) -> None:
        """Increment model usage counts, consumed tokens, and estimated cost."""
        with self._lock:
            self.metrics.llm_calls += 1
            self.metrics.input_tokens += prompt_tokens
            self.metrics.prompt_tokens += prompt_tokens
            self.metrics.output_tokens += completion_tokens
            self.metrics.completion_tokens += completion_tokens

            if cost_usd is not None and cost_usd > 0:
                cost = cost_usd
            else:
                cost = (prompt_tokens / 1_000_000.0) * self.price_in + (completion_tokens / 1_000_000.0) * self.price_out
            self.metrics.est_cost_usd = round(self.metrics.est_cost_usd + cost, 6)
            self.metrics.estimated_cost_usd = self.metrics.est_cost_usd

        self.event(
            "llm_completion",
            purpose=purpose,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost, 6),
        )

    def record_tool(self, tool_name: str = "", duration_s: float = 0.0, failed: bool = False) -> None:
        """Record a tool invocation and increment tool metrics."""
        with self._lock:
            self.metrics.tool_calls += 1
            if failed:
                self.metrics.tool_failures += 1
        self.event("tool_invocation", tool_name=tool_name, duration_s=duration_s, failed=failed)

    def finish(self, sources_considered: int = 0, sources_used: int = 0) -> RunMetrics:
        """Finalize the trace run, recording duration, sources metrics, and a run_finished event."""
        duration_s = time.monotonic() - self._start_time
        with self._lock:
            self.metrics.total_time_s = round(duration_s, 2)
            self.metrics.latency_ms = round(duration_s * 1000.0, 2)
            self.metrics.sources_considered = sources_considered
            self.metrics.sources_used = sources_used
            metrics_copy = self.metrics.model_copy()

        self.event("run_finished", metrics=metrics_copy.model_dump())
        return metrics_copy
