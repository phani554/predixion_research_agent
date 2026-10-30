# Proposal: add a planner

## Why
"A thin chat wrapper with no real agent workflow" is the first weak signal the brief lists. The plan is where the agent shows it understood the request: what the question really asks, which sub-questions answer it, and which tool fits each. Making the plan an explicit, validated object also makes orchestration visible in traces and the demo.

## What Changes
- `ResearchPlan` model: `in_scope`, `out_of_scope_reason`, `intent` (comparison | list_entities | pros_cons | explainer | other), `restated_question`, `steps[1..5]` of `PlanStep{id, sub_question, tool, query, rationale}`, `answer_shape`, `assumptions`, `is_fallback`.
- `make_plan(question, llm, settings, tracer)`: prompt with the tool menu and rules, validated via `structured()`.
- Normalisation in code: cap steps at `max_plan_steps`, drop duplicate queries, renumber ids, clear steps when out of scope.
- Deterministic `fallback_plan()` when the LLM fails, so a planner outage degrades quality instead of failing the run.
- Out-of-scope detection (small talk, arithmetic, code-writing, harmful) returns `status: out_of_scope` without tool calls.

## Capabilities
### New Capabilities
- `research-planning`: question → validated, bounded research plan with tool choice per step.

## Impact
New `planner.py`; `schemas.py` gains plan models; `agent.run_research` calls the planner.

## Out of scope
Re-planning from tool results (handled by a bounded follow-up round in the executor), multi-agent planning, dependent steps that use earlier results as inputs.
