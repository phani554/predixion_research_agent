# Tasks

## 1. Models
- [x] 1.1 Add `Intent`, `ToolName`, `PlanStep`, `ResearchPlan` (unique-id validator) to `schemas.py`; verify: `test_plan_rejects_duplicate_step_ids`, `test_plan_rejects_unknown_tool`

## 2. Planner
- [x] 2.1 Add `PLANNER_SYSTEM` prompt and `make_plan()` using `structured()`; verify: `test_valid_plan_is_used`
- [x] 2.2 Add `normalise_plan()`; verify: `test_duplicate_queries_removed_and_steps_capped`, `test_out_of_scope_has_no_steps`
- [x] 2.3 Add `fallback_plan()` and wire it for StructuredOutputError/LLMError; verify: a test that malformed-twice yields `is_fallback` with 2 steps, and one for LLMError

## 3. Wire into the run
- [x] 3.1 Call the planner from `run_research`; return `out_of_scope` without tools; show the plan with `--verbose`; verify: an agent test for out_of_scope and a manual run printing the plan
