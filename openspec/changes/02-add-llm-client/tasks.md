# Tasks

## 1. Interface and test double
- [x] 1.1 Add `LLMResponse`, `LLMClient` protocol, `LLMError`, `StructuredOutputError`, `FakeLLM`; verify: a unit test that FakeLLM returns scripted replies in order and records calls

## 2. Structured output
- [x] 2.1 Add `extract_json` and `schema_hint`; verify: `test_extract_json_from_fenced_reply`
- [x] 2.2 Add `structured()` with exactly one repair; verify: `test_repair_after_one_bad_reply`, `test_gives_up_after_repair_fails`

## 3. Real client
- [x] 3.1 Add `OpenAICompatLLM` (temperature 0, JSON mode flag, timeout, error normalisation, throttle, max_tokens, extra_body) and the Settings fields; verify: a `@pytest.mark.live` smoke test returning `{"ok": true}` and a unit test for the throttle using a stub client

## 4. Faults and accounting
- [x] 4.1 Add a minimal in-memory `Tracer` in `tracing.py` (`span()` context manager, `event()`, `record_llm()`, `record_tool()`, `metrics`), token accounting in `structured()`, and `FaultyLLM`; verify: `test_injected_malformed_fault_is_recovered` and a test that two calls are counted
