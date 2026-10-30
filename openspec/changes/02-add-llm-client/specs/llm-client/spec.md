# Spec Delta: llm-client

## Purpose
Gives every module provider-agnostic LLM access that returns validated structured data or a clear error, never raw text.

## ADDED Requirements

### Requirement: Validated structured output
`structured()` MUST return an instance of the requested Pydantic model or raise. It MUST never return unvalidated data. It MUST accept JSON wrapped in markdown code fences or surrounded by prose.

#### Scenario: JSON inside a code fence
- **WHEN** the model replies "Here you go: ```json {...valid...} ```"
- **THEN** `structured()` returns the validated model

### Requirement: One repair attempt, then give up
On invalid output the system MUST make exactly one repair call that includes the previous reply and the validation error, and if that also fails MUST raise `StructuredOutputError`. It MUST NOT loop further.

#### Scenario: Bad then good
- **WHEN** the first reply is not JSON and the second is valid
- **THEN** the validated model is returned, exactly 2 calls were made, and the second call contains the error text

#### Scenario: Bad twice
- **WHEN** both replies are invalid
- **THEN** `StructuredOutputError` is raised after exactly 2 calls

### Requirement: Provider-agnostic client
The real client MUST talk to any OpenAI-compatible endpoint configured by `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, use temperature 0, request JSON mode when `LLM_JSON_MODE` is not `0`, apply a request timeout, and convert every provider exception to `LLMError`. If `LLM_MODEL` is empty it MUST raise `LLMError` at construction.

#### Scenario: Provider down
- **WHEN** the provider raises a connection or HTTP error
- **THEN** the caller receives `LLMError`, not a provider-specific exception

### Requirement: Rate-limit friendliness
When `LLM_MIN_INTERVAL_S` > 0 the client MUST space consecutive requests to the same endpoint at least that many seconds apart, across all client instances in the process. On a rate-limit error (HTTP 429 or a "limit reached" message) it MUST wait the provider's "retry after" time (default 5 s, max 35 s) and retry once before raising `LLMError`.

#### Scenario: Rate limited once
- **WHEN** the provider answers "Free limit reached: retry after 7s" and then succeeds
- **THEN** the client waits about 8 s, retries once, and returns the reply

#### Scenario: Throttled calls
- **WHEN** two calls are made with `LLM_MIN_INTERVAL_S=1`
- **THEN** the second request starts at least 1 second after the first finished

### Requirement: Usage accounting
Each call MUST record prompt and completion tokens on the tracer when one is given, and invalid replies MUST be recorded with the validation error and a short preview of the raw text.

#### Scenario: Tokens counted
- **WHEN** two structured calls succeed with a tracer
- **THEN** the tracer metrics show 2 LLM calls and the summed token counts

### Requirement: Test doubles and fault injection
`FakeLLM` MUST return scripted replies per `purpose` in order (or from a callable) and record calls. `FaultyLLM` MUST make the first reply per purpose malformed under `llm:malformed`, and raise `LLMError` under `llm:down`.

#### Scenario: Injected malformed output is recovered
- **WHEN** `llm:malformed` is active and the inner model is healthy
- **THEN** `structured()` still returns a valid model via the repair call
