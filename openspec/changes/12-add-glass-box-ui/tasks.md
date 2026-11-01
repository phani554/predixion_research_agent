## 1. Trace events
- [ ] 1.1 In `agent.py` emit `plan_ready` (plan dump) after the plan span, `evidence_ready` (sources without `content`, rejected, uncovered, tool_errors) after the execute span, and `answer_ready` (answer dump) in `_finish` before `tracer.finish()`. Verify: `pytest -q` still green.

## 2. Server
- [ ] 2.1 Add `research_agent/web/server.py` (LiveTracer, `/api/config`, `POST /api/runs`, `/api/runs/{id}/stream` SSE, `/api/runs`, `/api/runs/{id}/trace`) and `__main__.py`. Add `ui` extra and package-data for `static/*` in pyproject. Verify: `tests/test_web.py` passes.

## 3. Page
- [ ] 3.1 Add `static/index.html`: stage stepper with what/how/this-run panel, timeline waterfall, live trace log with raw records, tabs Plan / Sources / Answer / Metrics / Raw, sample questions, fault toggles, replay picker. Verify: `python -m research_agent.web`, run the vector-DB sample, then replay it.
