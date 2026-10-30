# Tasks

## 1. Round execution
- [ ] 1.1 Add `Evidence`, `Budget`, `Executor.run` running plan steps in parallel and turning wikipedia results into candidates; verify: `test_happy_path_collects_ranked_sources` (with fake tools)
- [ ] 1.2 Add fetch-target selection (round-robin) and snippet fallback on fetch failure; verify: `test_failed_fetch_degrades_to_snippet`

## 2. Limits and recovery
- [ ] 2.1 Enforce the budget and deadline; verify: `test_budget_is_enforced`
- [ ] 2.2 Add the coverage check and one follow-up round with tool/wording switch; verify: `test_follow_up_round_switches_tool_for_uncovered_step`

## 3. Wire into the run
- [ ] 3.1 Call the executor from `run_research`; return insufficient_evidence without synthesis when no sources; verify: `test_all_tools_failing_yields_no_sources`, `test_tools_all_down_skips_synthesis`
