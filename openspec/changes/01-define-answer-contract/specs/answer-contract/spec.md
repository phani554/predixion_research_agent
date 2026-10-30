# Spec Delta: answer-contract

## Purpose
Defines what the agent accepts and the structured, source-cited answer every run returns, including honest refusals.

## ADDED Requirements

### Requirement: Every run returns a FinalAnswer
The system MUST return a `FinalAnswer` for every input, including invalid input and internal failures. It MUST contain: `question`, `status`, `short_answer`, `key_findings`, `sources`, `confidence`, `confidence_score` (0..1), `confidence_reasons`, `limitations`, `assumptions`, `next_steps`.

#### Scenario: Valid question before the pipeline exists
- **WHEN** the CLI is run with a valid research question
- **THEN** it prints a FinalAnswer whose `status` is `error` and whose limitations say the pipeline is not implemented, and it does not crash

#### Scenario: Unexpected exception inside the pipeline
- **WHEN** any stage raises an unexpected exception
- **THEN** the run still returns a FinalAnswer with `status: error` and the error summarised in `limitations`

### Requirement: Findings must cite sources
Each item in `key_findings` MUST carry at least one source id, and the model MUST reject a finding with an empty `source_ids` list.

#### Scenario: Uncited finding
- **WHEN** a `Finding` is constructed with `source_ids=[]`
- **THEN** validation fails

### Requirement: Input guard
The system MUST reject a question that is empty or shorter than `min_question_chars` (8), or longer than `max_question_chars` (500), with `status: invalid_input`, without calling any LLM or tool. Whitespace MUST be normalised before checking.

#### Scenario: Blank question
- **WHEN** the question is `"   "`
- **THEN** the answer has `status: invalid_input` and zero LLM or tool calls were made

#### Scenario: Over-long question
- **WHEN** the question has 600 characters
- **THEN** the answer has `status: invalid_input` and the short answer says to shorten it

### Requirement: Machine- and human-readable output
The CLI MUST print Markdown by default and the FinalAnswer JSON with `--json`, and MUST save the full run (answer, plan, sources, metrics) as JSON under `outputs/<run_id>.json`. The exit code MUST be 0 for `answered`/`partial` and 2 otherwise.

#### Scenario: JSON output
- **WHEN** the CLI is run with `--json`
- **THEN** stdout parses as JSON and validates against `FinalAnswer`

### Requirement: Central configuration
All budgets, limits, timeouts and the LLM endpoint MUST come from `Settings`, loaded from environment variables with an optional `.env` file. Existing environment variables MUST win over `.env`.

#### Scenario: Env overrides .env
- **WHEN** `LLM_MODEL` is set both in the environment and in `.env`
- **THEN** `Settings.from_env().llm_model` equals the environment value
