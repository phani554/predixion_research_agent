---
trigger: always_on
description: How tests are written and run
---
- Every task in `tasks.md` ends with a verification step; write or update the pytest test that proves it in the same task.
- Tests are offline and deterministic: `FakeLLM` (scripted replies per purpose) and fake tool functions with the real signatures.
- Name tests after the spec scenario they prove, e.g. `test_malformed_twice_falls_back`.
- Failure paths get tests too: timeout, retry exhaustion, malformed LLM output, blocked URL, injected instructions, empty results.
- `pytest -q` must be green before a task is marked done.
- Never modify `acceptance/`; if an acceptance check fails, fix the code or raise a spec question.
