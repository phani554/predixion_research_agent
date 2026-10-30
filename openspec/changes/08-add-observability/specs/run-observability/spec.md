# Spec Delta: run-observability

## Purpose
Makes every run inspectable after the fact: traces per stage, metrics, cost, and reproducible failure injection.

## ADDED Requirements

### Requirement: Persistent per-run trace
When `runs_dir` is set, every span and event MUST be appended as one JSON object per line to `runs/<run_id>.jsonl`. Spans MUST include `span`, `start_ms`, `duration_ms`, `status` (`ok`, `error`, or a stage-specific status like `invalid_output`) and an `error` field when an exception passed through. Tracing MUST never swallow exceptions.

#### Scenario: Normal run
- **WHEN** a question is researched
- **THEN** the trace file contains `run_started`, a `plan` span, `tool` spans, `llm` spans, `synthesize` and `ground` spans, and `run_finished` with metrics

#### Scenario: Exception inside a span
- **WHEN** code inside a span raises
- **THEN** the span is written with `status: error` and the error text, and the exception still propagates

### Requirement: Invalid model output is debuggable
An `llm` span whose reply failed validation MUST record `status: invalid_output`, the validation error, and the first 300 characters of the raw reply. API keys MUST never be written.

#### Scenario: Malformed reply
- **WHEN** the first planner reply is not JSON
- **THEN** its llm span shows `invalid_output`, the parse error, and a raw preview

### Requirement: Run metrics and cost
Each `RunResult.metrics` MUST report latency_ms, llm_calls, tool_calls, tool_failures, prompt_tokens, completion_tokens, est_cost_usd (tokens × configured per-million prices), sources_considered and sources_used.

#### Scenario: Cost estimate
- **WHEN** a run uses 1,000,000 prompt tokens at price-in 0.30 and 0 completion tokens
- **THEN** est_cost_usd is 0.30

### Requirement: Inspectable output
`--verbose` MUST print the plan (step, tool, sub-question, query) and a one-line metrics summary. The saved run JSON MUST include the plan, selected sources, rejected sources with reasons, and metrics.

#### Scenario: Why was a source dropped?
- **WHEN** a pinterest result was filtered out
- **THEN** the run JSON's `rejected` list contains its URL with reason `blocked domain (pinterest.com)`

### Requirement: Faults on demand
The CLI MUST accept repeatable `--fault <name>` flags (`web_search:timeout`, `web_search:error`, `fetch_page:error`, `fetch_page:injection`, `wikipedia:error`, `llm:malformed`, `llm:down`) and the `RA_FAULTS` env var, and the trace's `run_started` event MUST list active faults.

#### Scenario: Demo a search outage
- **WHEN** the CLI runs with `--fault web_search:timeout`
- **THEN** the run completes without crashing, its limitations mention failed tool calls, and `run_started.faults` contains `web_search:timeout`
