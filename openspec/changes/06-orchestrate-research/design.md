# Design: research execution

## Decisions

### 1. Two phases per round: choose tools, then choose pages
The planner picks search vs wikipedia; the executor decides which hits deserve a full read, because that depends on results the planner never saw. Reading pages (not just snippets) is what makes findings specific and citable.

### 2. Round-robin page budget
Fetching the top-N hits globally lets one broad sub-question eat the whole budget. Round-robin by step guarantees breadth. **Alternative:** LLM picks pages. Rejected: extra call, extra latency, and the lexical prefilter is good enough to beat noise; noted as future work.

### 3. Deterministic follow-up, max one round
Switching tool/wording recovers most empty steps for zero LLM cost and is easy to test. More rounds give diminishing returns and unbounded latency.

### 4. Budget object
`Budget(max_calls, deadline_s).take() -> bool` under a lock, checked before every tool call, so parallel workers can't overshoot.

### 5. Interfaces (`src/research_agent/executor.py`)
- `Evidence` dataclass: `sources, rejected, uncovered_steps, tool_errors, follow_up_rounds, budget_exhausted, candidates_considered`
- `Executor(settings, tracer=None, cache=None, tools=None).run(plan) -> Evidence`
- Candidate sources keyed by canonical URL; a page found by two steps merges `step_ids`.
- Uses `sources.prefilter_hits`, `sources.score_source`, `sources.select_sources` from change 05.

## Risks / Trade-offs
- Parallel fetches can hit the same site several times; acceptable at ≤6 pages.
- Snippet-only sources are weak evidence; grounding penalises confidence when most cited sources are snippets.
