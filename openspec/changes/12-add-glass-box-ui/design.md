## Decisions
- **Reuse the tracer, don't fork the pipeline.** `LiveTracer(Tracer)` overrides `_emit` to also push each record onto a queue, and `span()` to push a `span_start` notice so in-flight work is visible. The JSONL file is byte-identical to a CLI run.
- **SSE over WebSockets.** One-way stream, plain HTTP, auto-reconnect in the browser, zero extra deps.
- **Thread per run.** `run_research` is synchronous and already uses thread pools; the request returns a `run_id` at once and the stream drains the queue.
- **Replay = same renderer.** Spans are written when they end, so replay re-creates each span's start at `start_ms` and plays events with real proportions compressed to ≤ 9 s. Offline-safe demo.
- **Vanilla HTML/JS.** One file, no React/build/CDN: nothing to break on interview Wi-Fi and easy to read.
- **Safety.** Fault names allow-listed; `/api/config` exposes model, provider host and budgets only; all trace text is HTML-escaped before rendering (sources are untrusted).

## Stage mapping (UI)
Guard ← run_started · Plan ← plan span / llm(plan) · Search ← tool web_search|wikipedia · Read ← tool fetch_page · Filter ← evidence_ready / follow_up_round · Synthesize ← synthesize span · Ground ← ground span · Answer ← answer_ready.
