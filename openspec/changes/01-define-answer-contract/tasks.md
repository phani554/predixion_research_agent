# Tasks

## 1. Skeleton
- [x] 1.1 Add `pyproject.toml` (deps: pydantic, openai, httpx, trafilatura, ddgs, pyyaml; dev: pytest; pytest `pythonpath=src`, `live` marker deselected by default), `.gitignore`, `.env.example`, empty package; verify: `pip install -e ".[dev]"` and `pytest -q` run (0 tests is fine)

## 2. Contract
- [x] 2.1 Add `schemas.py` with FinalAnswer, Finding, SourceRef, Confidence, AnswerStatus, RunMetrics, RunResult per design; verify: `tests/test_schemas.py::test_finding_requires_a_citation`
- [x] 2.2 Add `config.Settings` + `from_env()` with the .env loader; verify: test that env wins over .env

## 3. Guard and entry point
- [x] 3.1 Add `guard.check_question`; verify: tests for blank and 600-char questions
- [x] 3.2 Add `agent.run_research` returning invalid_input from the guard and `status: error` ("pipeline not implemented") otherwise, wrapping unexpected exceptions; verify: tests for both

## 4. CLI and rendering
- [x] 4.1 Add `render.to_markdown(result, verbose)` and `cli.main` with `--json`/`--out`, exit codes, `__main__.py`; verify: `python -m research_agent "   " --json` prints invalid_input JSON and exits 2
