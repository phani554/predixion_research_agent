# Spec Delta: research-execution

## Purpose
Runs a plan's tool calls under hard budgets, reads the best pages per sub-question, and recovers once from gaps.

## ADDED Requirements

### Requirement: Execute every plan step
The executor MUST run each plan step's chosen tool with the step's query, in parallel up to `parallelism` (4) workers, and collect results per step.

#### Scenario: Two-step plan
- **WHEN** a plan has a web_search step and a wikipedia step and both tools succeed
- **THEN** sources from both steps are candidates and no sub-question is reported uncovered

### Requirement: Read the most relevant pages for each sub-question
From web_search hits the executor MUST drop blocked domains, duplicate URLs (canonicalised) and non-HTML links, rank the rest per step by snippet relevance, and fetch pages round-robin across steps up to `max_pages_to_fetch` in total.

#### Scenario: One step has many hits, another has few
- **WHEN** step 1 has 6 relevant hits and step 2 has 2, with a 4-page limit
- **THEN** pages are fetched alternately: two for step 1 and two for step 2

### Requirement: Degrade instead of dropping on fetch failure
If fetching a page fails, the executor MUST keep the hit as a snippet-only source flagged `fetch_<status>` and record the tool error.

#### Scenario: Site returns 403
- **WHEN** fetch_page fails with HTTP 403
- **THEN** the hit remains a candidate with no content and a `fetch_error` flag, and the error appears in `Evidence.tool_errors`

### Requirement: Hard budget
The executor MUST NOT make more than `max_tool_calls` tool calls or keep calling tools after `run_deadline_s`. Calls refused by the budget MUST return an error result and set `budget_exhausted`.

#### Scenario: Budget of one call
- **WHEN** `max_tool_calls` is 1 and the plan needs more
- **THEN** exactly one tool call runs and `Evidence.budget_exhausted` is true

### Requirement: One bounded follow-up round
After the first round, any step with no candidate scoring at least `min_source_score` with relevance ≥ 0.1 MUST get one follow-up attempt: a wikipedia step becomes web_search on the sub-question; a web_search step re-searches using the sub-question wording (or wikipedia if identical). At most `max_follow_up_rounds` (1) rounds run. Steps still uncovered are reported in `Evidence.uncovered_steps`.

#### Scenario: Wikipedia finds nothing
- **WHEN** a wikipedia step returns empty
- **THEN** exactly one follow-up web_search runs for that sub-question and `follow_up_rounds == 1`

### Requirement: No evidence means no synthesis
If no source survives selection, the run MUST return `status: insufficient_evidence` with the tool errors in limitations and MUST NOT call the synthesizer.

#### Scenario: Every tool down
- **WHEN** search, wikipedia and fetch all fail
- **THEN** the answer is `insufficient_evidence` and the only LLM call made was the planner
