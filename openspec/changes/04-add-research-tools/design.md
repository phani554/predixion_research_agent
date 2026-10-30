# Design: research tools

## Decisions

### 1. Plain functions + one runner
Each tool is `fn(**args, settings) -> ToolResult` and raises typed exceptions; `tools/base.run_tool()` owns timeouts, retries, caching, tracing and faults. **Why:** failure policy in one place; tools stay ~30 lines; tests can target either layer. **Alternative:** a Tool base class per tool with its own retry decorator. Rejected: duplicated policy.

### 2. Exceptions as the classification signal
`TransientToolError` (retry), `PermanentToolError` (don't), `BlockedError(PermanentToolError)` (our own policy refused). Unknown exceptions are treated as transient once.

### 3. Hard timeout via a thread pool
`future.result(timeout=tool_timeout_s + 2)`. Libraries (ddgs, DNS) don't always honour timeouts. The stuck thread keeps running in the background; acceptable for a CLI, noted as a limitation (an async rewrite would cancel properly).

### 4. Keyless search
`ddgs` metasearch, backends tried in order `google, yahoo, duckduckgo, brave, bing` because single engines block cloud IPs. **Alternative:** Tavily/Serper (better quality, needs a key, costs money). Rejected for a take-home that reviewers must run; swappable behind the same signature.

### 5. trafilatura for extraction
Best-in-class main-content extraction; we keep tables, drop comments, prefer precision.

### 6. Interfaces
- `tools/base.py`: `run_tool(name, fn, args, settings, tracer=None, cache=None) -> ToolResult`, exceptions above, `INJECTION_FIXTURE`
- `tools/web_search.py`: `web_search(query, *, settings, max_results=None)`
- `tools/wikipedia.py`: `wikipedia(query, *, settings)`
- `tools/fetch_page.py`: `fetch_page(url, *, settings)`
- `tools/url_safety.py`: `check_url(url)` raises `BlockedError`
- `tools/__init__.py`: `REGISTRY = {"web_search", "wikipedia", "fetch_page"}`, `PLANNER_TOOLS = ("web_search", "wikipedia")`
- `cache.py`: `Cache(directory, ttl_s).get(name, args) / .set(name, args, value)` — sha256 key, atomic write.
- Schemas: `SearchHit`, `ToolStatus`, `ToolResult` in `schemas.py`.

## Risks / Trade-offs
- DNS rebinding between check and fetch is not prevented (would need pinning the resolved IP). Documented.
- Metasearch scraping can break when engines change HTML; the multi-backend order and `empty` status contain it.
