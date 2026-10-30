# Design: define the answer contract

## Context
Empty repo. The assignment lists the exact sections the final answer must have and values "deterministic output structure". We need a stable target for every later change and for evals.

## Decisions

### 1. Pydantic v2 models as the contract (`src/research_agent/schemas.py`)
`FinalAnswer`, `Finding{statement, source_ids: list[str] (min 1), support: "supported"|"weak" = "supported"}`, `SourceRef{id, title, url}`, `Confidence` enum `low|medium|high`, `AnswerStatus` literal, `RunMetrics`, `RunResult{run_id, answer, plan, sources, rejected, metrics}`.
**Why:** validation for free, JSON schema we can paste into prompts later, one source of truth.
**Alternative:** TypedDict/dataclasses. Rejected: no runtime validation, which is the whole point at LLM boundaries.

### 2. `status` separates "answered" from honest refusals
Evaluators look for failure handling. A refusal (`insufficient_evidence`, `out_of_scope`) is a correct outcome, not an error; callers and evals need to tell them apart.

### 3. Guard before tokens (`guard.check_question(question, settings) -> (clean_q, error | None)`)
Cheap checks first; costs nothing and removes a class of junk input.

### 4. Settings dataclass (`config.Settings.from_env()`)
All budgets in one reviewable place; tiny built-in .env loader (no python-dotenv dependency).

### 5. Orchestrator entry point (`agent.run_research(question, settings=None, llm=None, tools=None, tracer=None) -> RunResult`)
Dependency injection of `llm` and `tools` from day one so tests never need the network. The top-level function catches unexpected exceptions and converts them to `status: error`.

### 6. CLI with argparse (`cli.main(argv) -> int`)
No extra dependency; `--json`, `--verbose`, `--no-cache`, `--fault`, `--out` flags (later changes fill some in).

## Risks / Trade-offs
- The schema may need fields later (e.g. `support` on findings): adding optional fields with defaults is backwards compatible.
