# Spec Delta: evaluation

## Purpose
Measures agent behaviour on real queries and injected failures with repeatable, behavioural checks and a non-agentic baseline.

## ADDED Requirements

### Requirement: Case file
`evals/queries.yaml` MUST contain at least 10 cases, each with `id`, `category`, `question`, optional `faults`, and an `expect` block. It MUST cover: at least 3 happy paths from the brief's example queries, a hallucination-bait case, an out-of-scope case, an invalid-input case, a prompt-injection case, and at least two injected-failure cases.

#### Scenario: Coverage of categories
- **WHEN** the case file is loaded
- **THEN** categories include happy_path, edge, safety and failure

### Requirement: Behavioural checks
The runner MUST evaluate each case's expectations and the universal invariants (every finding has ≥1 citation; every cited id is in `sources`), and a case passes only if all checks pass. An exception from the agent MUST count as a failed case, not crash the suite.

#### Scenario: Hallucination bait
- **WHEN** the fictional-entities case runs
- **THEN** it passes only if confidence is not high and the limitations or short answer admit missing evidence

#### Scenario: Agent crash
- **WHEN** the agent raises for one case
- **THEN** that case is FAIL with reason "crashed: ..." and the remaining cases still run

### Requirement: Reports
The runner MUST print one PASS/FAIL line per case and write a JSON file with the full answers and a Markdown table (id, category, pass, status, confidence, findings (weak), sources, latency, tool failures, notes) under `evals/results/`.

#### Scenario: Subset run
- **WHEN** `python evals/run_evals.py --ids empty arithmetic` is run
- **THEN** exactly two cases run and both report files are written

### Requirement: Non-agentic baseline
With `--baseline`, for each case without faults the runner MUST also call a single-prompt, no-tools baseline and store its answer next to the agent's, so the evaluation document can compare citations and abstention behaviour.

#### Scenario: Baseline on fictional entities
- **WHEN** the baseline answers the fictional-entities question
- **THEN** its output is stored under `baseline` for that case, whatever it says
