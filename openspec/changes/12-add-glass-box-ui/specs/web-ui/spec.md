## ADDED Requirements

### Requirement: Live glass-box run
The UI SHALL start a run for a question and stream every trace record to the browser while the run executes.

#### Scenario: Live stages
- **WHEN** the user runs a question
- **THEN** each pipeline stage (guard, plan, search, read, filter, synthesize, ground, answer) shows idle, active, done, warning, failed or skipped as trace records arrive

#### Scenario: Blank input
- **WHEN** the question is blank
- **THEN** the stream ends with an `invalid_input` answer, guard shows failed and every other stage shows skipped

### Requirement: Replay saved runs
The UI SHALL replay any run in `runs/` using the same renderer, without network or LLM access.

#### Scenario: Replay
- **WHEN** a saved run is picked
- **THEN** its stages, timeline, plan, sources and answer are reconstructed from the JSONL trace and saved result

### Requirement: Safe configuration view
The server SHALL expose model, provider host, budgets and filter thresholds, and SHALL NOT expose the API key.

#### Scenario: No key leak
- **WHEN** `/api/config` is requested
- **THEN** the response contains budgets and does not contain `LLM_API_KEY`

#### Scenario: Unknown fault
- **WHEN** a run is requested with a fault outside the allow-list
- **THEN** the server returns 400
