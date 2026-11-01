## Why
The CLI proves the agent works, but a reviewer can't *see* the pipeline: which sub-questions the planner chose, which tool calls ran in parallel, why a source was dropped, how confidence was computed. For a live walkthrough we need a glass-box view over the existing trace, without changing agent behaviour.

## What Changes
- Agent emits three extra trace events: `plan_ready`, `evidence_ready`, `answer_ready` (data that already exists, now in the JSONL).
- New optional package `research_agent.web`: FastAPI server + one static HTML page (no build step, no CDN, works offline).
- Live runs stream trace records over Server-Sent Events; saved runs replay from `runs/*.jsonl` + `outputs/*.json`.
- Fault toggles in the UI map to the existing `--fault` names (allow-listed server-side).
- New optional extra `ui = [fastapi, uvicorn]`.

## Impact
- `agent.py` gains 3 `tracer.event(...)` lines; no control-flow change. All existing tests stay green.
- UI is read-only: it never alters plans, budgets or prompts. API key is never sent to the browser.
