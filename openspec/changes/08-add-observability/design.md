# Design: observability

## Decisions

### 1. Local JSONL, OTel-shaped
A span is `{span, start_ms, duration_ms, status, ...attrs}`, the same shape as an OpenTelemetry span, so exporting to Langfuse/Helicone/OTel later is a sink swap. **Alternative:** add Langfuse now. Rejected: needs an account and keys for reviewers to run it; zero-dependency files are enough to debug and to show in the demo.

### 2. Tracer passed explicitly
`Tracer` is an argument, not a global, so tests run with `runs_dir=None` (in-memory) and parallel workers share one thread-safe instance.

### 3. Cost is an estimate, prices are config
Free-tier runs cost $0; the price env vars let the README show what the same run would cost on a paid model, which is the cost/latency discussion the brief wants.

### 4. Interfaces (`src/research_agent/tracing.py`)
- `Tracer(run_id=None, runs_dir="runs", price_in=0.0, price_out=0.0)`
- `.span(name, **attrs)` context manager yielding a mutable record; `.event(name, **attrs)`; `.record_llm(prompt, completion)`; `.record_tool(failed)`; `.finish() -> RunMetrics`
- `run_id` format `YYYYMMDD-HHMMSS-<6 hex>`.

## What we'd monitor in production (feeds the README)
Answer status mix (answered/partial/insufficient/error), confidence distribution, weak-finding rate, tool failure rate by tool and domain, fallback-plan rate, repair-call rate, p50/p95 latency per stage, tokens and cost per run, injection flags per day.
