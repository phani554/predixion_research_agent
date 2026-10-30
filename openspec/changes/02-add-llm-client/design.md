# Design: LLM client

## Decisions

### 1. Orchestrate tools in code, use the LLM only for "think" steps
The LLM plans and synthesises; Python decides when and how tools run. **Why:** deterministic budgets, retries and safety checks live in code we can test; the model can't loop or call tools we didn't allow. **Alternative:** native function-calling ReAct loop. Rejected for v1: harder to bound cost/latency and to test; noted as future work.

### 2. OpenAI-compatible protocol
One SDK reaches Gemini (free tier, `https://generativelanguage.googleapis.com/v1beta/openai/`), OpenAI, Groq, Ollama/vLLM. Swapping providers is an env change.

### 3. Schema in the prompt + JSON mode + Pydantic validation
Providers differ in native JSON-schema support, so we paste `Model.model_json_schema()` into the system prompt (`schema_hint(Model)`), ask for `response_format={"type":"json_object"}` when supported, and validate ourselves. `extract_json()` takes the substring from the first `{` to the last `}` after stripping code fences.

### 4. Exactly one repair
Most malformed replies are fixed by showing the model its error once. A second repair rarely helps and doubles cost/latency, so callers get `StructuredOutputError` and decide a fallback (planner → fallback plan; synthesis → error answer with sources).

### 5. Interfaces (`src/research_agent/llm.py`)
- `LLMResponse(text, prompt_tokens=0, completion_tokens=0)` dataclass
- `LLMClient.complete(messages, *, json_mode=True, purpose="") -> LLMResponse`
- `OpenAICompatLLM(base_url, api_key, model, timeout_s=60, max_retries=2, json_mode=True, min_interval_s=0, max_tokens=4096, extra_body=None)`
- `FakeLLM(script: dict[purpose, list[str|Exception] | Callable[[messages], str]])`, `.calls: list[(purpose, messages)]`
- `FaultyLLM(inner, faults: set[str])`
- `extract_json(text) -> str`, `schema_hint(Model) -> str`
- `structured(llm, messages, Model, *, tracer=None, purpose="") -> Model`
- Exceptions: `LLMError`, `StructuredOutputError`

### 6. Throttle inside the client
A lock + `min_interval_s` spacing. Free tiers (Gemini Flash free RPM) otherwise fail mid-run. `extra_body` passes provider knobs such as `{"reasoning_effort": "low"}`.

## Risks / Trade-offs
- JSON mode unsupported on some providers → `LLM_JSON_MODE=0`; prompt + extraction still work.
- Reasoning models can spend the token budget thinking and return empty content → `max_tokens` setting, `reasoning_effort` via `LLM_EXTRA_BODY`, and the repair path.
