# Proposal: orchestrate research execution

## Why
We have a plan and tools; now something has to run them sensibly. "Tool orchestration" and "cost and latency tradeoffs" are graded directly. Without hard budgets an agent can loop or fetch forever; without a coverage check it silently returns half an answer.

## What Changes
- An `Executor` that runs the plan's tool calls in parallel (bounded pool), under a run budget: `max_tool_calls` (12), `max_pages_to_fetch` (6), `run_deadline_s` (150).
- Fetch-target selection: search hits are prefiltered (blocked domains, duplicates, non-HTML) and ranked by snippet relevance, then picked **round-robin across sub-questions** so every sub-question gets at least one page read.
- A failed page read degrades to a snippet-only source instead of being lost.
- Coverage check after each round: a sub-question with no usable source triggers **at most one follow-up round** that switches strategy (sub-question wording instead of the query, or the other tool).
- An `Evidence` object handed to synthesis: selected sources (S1..Sn), rejected sources with reasons, uncovered sub-questions, tool errors, follow-up count, budget-exhausted flag.

## Capabilities
### New Capabilities
- `research-execution`: running a plan's tools under budgets and recovering from gaps.

## Impact
New `executor.py`; `agent.run_research` calls it and returns `insufficient_evidence` without calling synthesis when no source survives.

## Out of scope
LLM-driven re-planning, async/await rewrite, distributed execution.
