"""In-memory execution tracing and metrics collection."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

from research_agent.schemas import RunMetrics


class Tracer:
    """Collects execution spans, events, and resource metrics during an agent run."""

    def __init__(self, metrics: RunMetrics | None = None) -> None:
        self.metrics: RunMetrics = metrics or RunMetrics()
        self.events: list[dict[str, Any]] = []
        self.spans: list[dict[str, Any]] = []

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        """Measure the wall-clock execution time of a logical processing phase."""
        start_t = time.monotonic()
        try:
            yield
        finally:
            duration_s = time.monotonic() - start_t
            self.spans.append({"name": name, "duration_s": duration_s})

    def event(self, name: str, **kwargs: Any) -> None:
        """Record an annotated timestamped event during pipeline execution."""
        record: dict[str, Any] = {"name": name, "timestamp": time.time(), **kwargs}
        self.events.append(record)

    def record_llm(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        purpose: str = "",
        cost_usd: float = 0.0,
    ) -> None:
        """Increment model usage counts, consumed tokens, and estimated cost."""
        self.metrics.llm_calls += 1
        self.metrics.input_tokens += prompt_tokens
        self.metrics.output_tokens += completion_tokens
        self.metrics.estimated_cost_usd += cost_usd
        self.event(
            "llm_completion",
            purpose=purpose,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def record_tool(self, tool_name: str, duration_s: float = 0.0) -> None:
        """Record a tool invocation and increment tool metrics."""
        self.metrics.tool_calls += 1
        self.event("tool_invocation", tool_name=tool_name, duration_s=duration_s)

