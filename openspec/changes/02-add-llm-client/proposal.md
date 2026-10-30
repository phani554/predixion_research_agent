# Proposal: add an LLM client with validated structured output

## Why
Planning and synthesis both need the LLM to return data we can act on, not prose. LLMs routinely return malformed JSON, wrap it in prose or code fences, or drop required fields. Free tiers rate-limit hard. Without one disciplined place for this, every caller would re-invent parsing and retries, and tests would need a live model.

## What Changes
- An `LLMClient` protocol with one method `complete(messages, json_mode, purpose) -> LLMResponse(text, prompt_tokens, completion_tokens)`.
- `OpenAICompatLLM`: works with any OpenAI-compatible endpoint (Gemini, OpenAI, Groq, local vLLM) via `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL`; temperature 0; JSON mode when supported; request timeout; bounded SDK retries; optional client-side throttle for free-tier RPM limits; provider errors normalised to `LLMError`.
- `structured(llm, messages, Model, tracer, purpose) -> Model`: extract JSON (fences/prose tolerated), validate with Pydantic, **one** repair round-trip that feeds the validation error back, then `StructuredOutputError`.
- `FakeLLM` (scripted replies per purpose) for offline tests, and `FaultyLLM` to inject `llm:malformed` / `llm:down` for demos and evals.

## Capabilities
### New Capabilities
- `llm-client`: provider-agnostic LLM access with validated structured output.

## Impact
New `llm.py`; `Settings` gains LLM fields; tests use FakeLLM from here on.

## Out of scope
Streaming, function-calling/tool-calling APIs (we orchestrate tools in code), multi-provider routing, prompt caching.
