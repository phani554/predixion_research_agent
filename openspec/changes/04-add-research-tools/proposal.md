# Proposal: add research tools

## Why
The brief requires at least two tools and "tool selection based on the task". Tools are also where most production failures happen: slow sites, rate limits, 403s, huge pages, and URLs chosen by strangers (SSRF). One shared runner handles timeouts, retries, caching and fault injection so the three tools stay tiny and the failure behaviour is identical and testable.

## What Changes
- `web_search(query)` → ranked `SearchHit`s via the `ddgs` metasearch library (no API key), trying several backends in order because individual engines rate-limit datacenter IPs.
- `wikipedia(query)` → summary of the best-matching English article (MediaWiki search + REST summary).
- `fetch_page(url)` → main readable text via httpx + trafilatura, content-type allow-list, 2 MB download cap, 6,000-char text cap, SSRF guard (public http/https hosts only).
- `run_tool(name, fn, args, settings, tracer, cache)`: hard timeout, bounded retries with exponential backoff for transient errors only, permanent errors not retried, every outcome returned as a `ToolResult` with a status (`ok | empty | error | timeout | blocked`) instead of an exception.
- A 24 h file cache for successful tool results; fault injection via `RA_FAULTS` / `--fault` (`<tool>:timeout`, `<tool>:error`, `fetch_page:injection`).

## Capabilities
### New Capabilities
- `research-tools`: the tools the agent can use and how their failures are contained.

## Impact
New `tools/` package and `cache.py`; Settings gains tool budgets.

## Out of scope
Paid search APIs (Tavily/Serper/Bing) — the interface allows swapping one in; JavaScript rendering; PDF extraction; login-walled sites.
