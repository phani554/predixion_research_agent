# Proposal: add observability and cost accounting

## Why
"Logging or tracing" and "cost and latency tradeoffs" are on the brief's production list, and "what would you monitor in production?" is a required README answer. When a run gives a bad answer we need to see which stage caused it: a bad plan, a failed tool, a filtered-out source, or a weak synthesis. The minimal in-memory tracer from change 02 counts calls; this change makes every run replayable from disk.

## What Changes
- Every run gets a `run_id`; spans for `plan`, `execute`, each `tool` call, each `llm` call, `synthesize`, `ground` are written as JSON lines to `runs/<run_id>.jsonl` with start time, duration, status, and key attributes (tool args, attempts, token counts, validation errors with a 300-char raw preview, sources kept/rejected).
- Events: `run_started` (question, active faults), `planner_fallback`, `follow_up_round`, `tool_cache_hit`, `unhandled_exception`, `run_finished` (metrics).
- `RunMetrics`: latency, LLM calls, tool calls, tool failures, prompt/completion tokens, estimated cost from `LLM_PRICE_IN_PER_M`/`LLM_PRICE_OUT_PER_M`, sources considered vs used.
- `--verbose` prints the plan and a metrics line; the saved run JSON includes the plan, selected and rejected sources (with reasons), and metrics.
- `--fault` CLI flag (repeatable) feeding the existing fault injection, so failure cases can be shown on demand in the demo.

## Capabilities
### New Capabilities
- `run-observability`: per-run traces, metrics and cost estimates.

## Impact
`tracing.py` gains JSONL persistence and cost math; spans added in `agent.py`; `cli.py` flags.

## Out of scope
Exporting to Langfuse/OpenTelemetry (the span shape maps 1:1; listed as next step), dashboards, alerting.
