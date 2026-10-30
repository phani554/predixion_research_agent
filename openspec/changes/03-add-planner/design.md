# Design: planner

## Decisions

### 1. Planner-executor, single agent
One planning call, then code executes. **Why:** the brief says a clean single-agent design beats an overbuilt one; a plan object is easy to show, trace and test. **Alternative:** ReAct loop where the model picks the next tool after every observation. Rejected for v1: unbounded calls, harder to evaluate. **Alternative:** multi-agent. Rejected: complexity without benefit at this scope.

### 2. Two planner tools only
`web_search` (default: current, comparative, opinionated info) and `wikipedia` (stable background). `fetch_page` is chosen by the executor, not the planner, because whether to read a page depends on search results the planner hasn't seen.

### 3. Prompt contract
System prompt lists tools with when-to-use, rules (short search-engine queries, at most 1-2 wikipedia steps, list assumptions about ambiguous words like "top"), out-of-scope criteria, and the JSON schema. User message is only the question.

### 4. Code enforces what the prompt asks
Models ignore instructions sometimes, so `normalise_plan()` re-applies caps, dedupe and numbering. An in-scope plan with zero steps falls back.

### 5. Interfaces (`src/research_agent/planner.py`)
- `make_plan(question, llm, settings, tracer=None) -> ResearchPlan`
- `normalise_plan(plan, question, settings) -> ResearchPlan`
- `fallback_plan(question, reason="") -> ResearchPlan`
- Models in `schemas.py`: `Intent`, `ToolName`, `PlanStep`, `ResearchPlan` (unique step ids validator).

## Risks / Trade-offs
- Steps can't depend on each other (step 3 can't use the names found in step 1). Mitigated by the executor's follow-up round; full re-planning is future work.
- The planner may inject its own prior knowledge into queries (e.g. naming products). Acceptable: queries only steer retrieval; claims must still come from sources.
