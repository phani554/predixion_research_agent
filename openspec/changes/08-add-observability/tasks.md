# Tasks

## 1. Tracer
- [x] 1.1 Extend `Tracer` with JSONL persistence, error capture in spans, cost estimate, `finish()`; verify: unit tests for the error span and the cost scenario

## 2. Instrument the pipeline
- [x] 2.1 Add spans/events in `agent.py`, `planner.py` (fallback event), `executor.py` (follow-up event), `tools/base.py` (tool spans, cache hits), `llm.py` (invalid_output + raw preview); verify: run one live question and inspect `runs/<id>.jsonl`

## 3. Output
- [x] 3.1 `--verbose` plan + metrics line, run JSON with plan/sources/rejected/metrics, `--fault` flag; verify: `python -m research_agent "Compare LangGraph and CrewAI" --fault web_search:timeout -v` completes and shows the failure in limitations
