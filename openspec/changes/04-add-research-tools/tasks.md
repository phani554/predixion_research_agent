# Tasks

## 1. Runner
- [x] 1.1 Add `ToolStatus`, `ToolResult`, `SearchHit` schemas and `tools/base.py` with exceptions + `run_tool` (timeout, bounded backoff retries, status mapping); verify: `test_transient_error_is_retried`, `test_retries_are_bounded`, `test_permanent_error_not_retried`, `test_hard_timeout`

## 2. Tools
- [x] 2.1 Add `web_search` with backend fallback; verify: a `live` test returning ≥1 hit and a unit test for the all-empty case
- [x] 2.2 Add `url_safety.check_url` and `fetch_page`; verify: `test_private_and_non_http_urls_blocked` and a `live` fetch of a known article
- [x] 2.3 Add `wikipedia`; verify: a `live` test for "retrieval augmented generation"

## 3. Cache and faults
- [x] 3.1 Add `cache.py` and cache use in `run_tool` (ok results only); verify: `test_cache_hit_skips_call`
- [x] 3.2 Add fault injection from `Settings.faults`; verify: `test_fault_injection_and_failure_counted`
