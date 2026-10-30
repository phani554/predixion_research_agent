# Proposal: add an evaluation suite

## Why
"No evaluation discipline" is a weak signal in the brief, and the submission must include an evaluation document with at least 5 test queries, expected behaviour, and what worked and what didn't. Unit tests prove the code does what we wrote; evals prove the system behaves well on real questions, real web pages and a real model, including the ugly cases.

## What Changes
- `evals/queries.yaml`: 12 cases across categories: 4 happy paths (the brief's own example queries), hallucination bait (fictional products), an unknowable future event, out-of-scope arithmetic, empty input, prompt injection in the question, and three injected failures (search timeout, poisoned page, malformed model output).
- Behavioural checks per case (`status_in`, `min_sources`, `min_findings`, `mention_any`, `confidence_not`, `limitation_any`, `not_contains`) plus universal invariants (every finding cited, every cited id listed). No exact-answer matching: web results change daily; honesty and grounding don't.
- `evals/run_evals.py` runs the real agent per case (with that case's faults), prints PASS/FAIL lines, and writes `evals/results/<timestamp>.json` + `.md` (status, confidence, findings/weak, sources, latency, tool failures, failure reasons).
- `--baseline` also runs a non-agentic single-call answer (no tools) for comparison.
- `--ids` to run a subset (free-tier rate limits).

## Capabilities
### New Capabilities
- `evaluation`: repeatable behavioural evaluation of the agent on real queries and injected failures.

## Impact
New `evals/` folder and `baseline.py`. Results feed `docs/EVALUATION.md` and `samples/`.

## Out of scope
LLM-as-judge scoring, large benchmark datasets, CI-gated evals (they need network and a key).
