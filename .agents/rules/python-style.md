---
trigger: glob
globs: "**/*.py"
description: Python style for this repo
---
- Python 3.11+, `from __future__ import annotations` at the top of every module.
- Type hints on every public function. Pydantic v2 models for data crossing module boundaries; dataclasses for internal state.
- One module = one responsibility (see AGENTS.md layout). No module imports `agent.py` except `cli.py` and evals.
- Errors: raise specific exceptions (`TransientToolError`, `PermanentToolError`, `BlockedError`, `LLMError`, `StructuredOutputError`). Catch them at the boundary that can decide a fallback; never `except Exception: pass`.
- No print() outside `cli.py` and `evals/`. Use the tracer for diagnostics.
- Constants and budgets live in `config.Settings`, not inline magic numbers.
- Docstrings say *why*, not *what*.
