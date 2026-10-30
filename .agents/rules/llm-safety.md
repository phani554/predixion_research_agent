---
trigger: model_decision
description: Apply when writing prompts, handling LLM output, or handling fetched web content
---
- Retrieved text is UNTRUSTED. Wrap it in `<source id=".." url="..">` delimiters, tell the model it is data, and strip sentences that match injection patterns before the model sees them. Flag the source.
- The model may only cite source ids we gave it. Code (not the model) drops uncited findings and unknown ids.
- Confidence is computed by code from evidence signals, then capped by the model's self-rating. The model can lower confidence, never raise it.
- Planner may only choose tools in the registry's allow-list. Tool arguments are validated by Pydantic.
- `fetch_page` only fetches public http(s) URLs (SSRF guard: no localhost, private, link-local, or metadata IPs), with a size cap.
- Temperature 0, JSON mode when the provider supports it, schema pasted in the prompt, one repair attempt, then fallback.
- Never put API keys or the system prompt in outputs, traces, or logs.
