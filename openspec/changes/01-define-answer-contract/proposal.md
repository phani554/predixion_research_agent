# Proposal: define the answer contract

## Why
Before any agent logic exists we need to agree on what the system takes in and what it gives back. The assignment grades "structured final output" and "deterministic output structure": if the output shape is decided by whatever the LLM happens to return, every later feature (grounding, confidence, evals) has nothing stable to check against. Defining input/output first is also step 1 of the assignment's own recommended workflow.

## What Changes
- A `FinalAnswer` Pydantic model with every section the brief requires: question, short answer, key findings (each citing source ids), sources used, confidence (level + score + reasons), limitations, assumptions, next steps, and a `status`.
- A `status` field so callers can tell an answer from an honest refusal: `answered | partial | insufficient_evidence | out_of_scope | invalid_input | error`.
- An input guard that rejects empty/too-short and over-long questions before any tokens are spent.
- `Settings` loaded from env/.env holding every budget and limit in one place.
- A CLI (`python -m research_agent "question"`) that prints Markdown or `--json`, and saves the full run JSON.
- Until the pipeline exists, a valid question returns `status: error` with a clear "not implemented" limitation (the contract still holds).

## Capabilities
### New Capabilities
- `answer-contract`: input validation and the structured output every run returns.

## Impact
New package skeleton (`pyproject.toml`, `src/research_agent/{config,schemas,guard,render,agent,cli}.py`), `.env.example`, first tests.

## Out of scope
LLM calls, tools, planning, any web access, a web UI or API server.
