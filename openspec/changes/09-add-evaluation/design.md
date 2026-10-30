# Design: evaluation

## Decisions

### 1. Behavioural, not exact-match
We check what must always be true (honest status, grounding, no leaked prompt, failure surfaced) rather than "the answer equals X", because live web content and model outputs vary run to run. **Alternative:** golden answers + LLM judge. Better for answer quality, but costly and itself noisy; future work.

### 2. Failure cases are first-class eval cases
Faults are declared per case (`faults: [web_search:timeout]`), so reliability is measured the same way as quality, and the demo video's failure path is reproducible.

### 3. Baseline comparison
A single LLM call with no tools shows what the agent adds: citations, abstention on unknown entities, visible limitations. Cheap to run, very persuasive in the write-up.

### 4. Interfaces
- `evals/run_evals.py`: `check(case, result) -> list[str]`, `report(rows) -> str`, CLI `--ids`, `--baseline`
- `src/research_agent/baseline.py`: `run_baseline(question, llm) -> DraftAnswer`

## Risks / Trade-offs
- Live evals are slow on free tiers (rate limits) and non-deterministic; we record the run, model and date in EVALUATION.md and keep the result files.
