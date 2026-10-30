# Spec Delta: research-planning

## Purpose
Turns a question into a small, validated research plan with one chosen tool per sub-question, degrading to a fallback plan instead of failing.

## ADDED Requirements

### Requirement: Plan with tool choice per step
For an in-scope question the system MUST produce a `ResearchPlan` with 1 to `max_plan_steps` (5) steps, each naming exactly one tool from the allow-list (`web_search`, `wikipedia`) and a search query of 2-200 characters.

#### Scenario: Comparison question
- **WHEN** the question is "Compare the top 3 open-source vector databases for a startup building RAG products"
- **THEN** the plan has intent `comparison`, at least 2 steps, and every step's tool is `web_search` or `wikipedia`

#### Scenario: Unknown tool from the model
- **WHEN** the model returns a step with tool `shell`
- **THEN** validation fails and the repair/fallback path is used; no step with an unknown tool is ever executed

### Requirement: Plan normalisation
The system MUST cap the steps at `max_plan_steps`, remove steps whose query duplicates an earlier one (case/whitespace-insensitive), and renumber step ids 1..n.

#### Scenario: Seven steps with duplicate queries
- **WHEN** the model returns 7 steps, 3 of them with the same query
- **THEN** the plan has at most 5 steps, all queries unique, ids 1..n

### Requirement: Fallback plan
If planning fails (`StructuredOutputError` or `LLMError`), the system MUST use a deterministic fallback plan (web_search for the question, plus a wikipedia step for background), mark `is_fallback=true`, and record the reason as an assumption. The run MUST continue.

#### Scenario: Malformed twice
- **WHEN** the planner model returns invalid JSON twice
- **THEN** the run continues with the 2-step fallback plan and the final answer lists "Planner failed" in limitations

#### Scenario: Provider down
- **WHEN** the planner call raises `LLMError`
- **THEN** the fallback plan is used

### Requirement: Out-of-scope handling
If the planner marks the question out of scope, the system MUST return `status: out_of_scope` with the reason, MUST NOT call any tool, and MUST NOT call the synthesizer.

#### Scenario: Arithmetic
- **WHEN** the question is "What is 17 multiplied by 23?"
- **THEN** the answer status is `out_of_scope` and zero tool calls were made

