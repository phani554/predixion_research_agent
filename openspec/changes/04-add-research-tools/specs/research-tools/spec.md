# Spec Delta: research-tools

## Purpose
Defines the tools the agent can use and guarantees their failures are contained, bounded, and visible.

## ADDED Requirements

### Requirement: Tools never raise into the agent
`run_tool` MUST return a `ToolResult` for every call, with `status` one of `ok`, `empty`, `error`, `timeout`, `blocked`, plus `attempts`, `latency_ms` and an `error` message when not ok.

#### Scenario: Library throws an unexpected exception
- **WHEN** a tool function raises `RuntimeError`
- **THEN** `run_tool` returns a ToolResult with status `error` and does not raise

### Requirement: Bounded retries for transient failures only
Transient failures (timeouts, HTTP 429, HTTP 5xx, connection errors) MUST be retried up to `tool_max_retries` (2) times with exponential backoff (0.5 s, 1 s, ...). Permanent failures (HTTP 4xx other than 429, unsupported content, blocked URL) MUST NOT be retried.

#### Scenario: Timeout then success
- **WHEN** the first attempt raises a transient timeout and the second succeeds
- **THEN** the result is `ok` with `attempts == 2`

#### Scenario: Always failing
- **WHEN** every attempt raises a transient error
- **THEN** exactly `tool_max_retries + 1` attempts are made and the status is `timeout` or `error`

#### Scenario: 404
- **WHEN** a page returns HTTP 404
- **THEN** exactly 1 attempt is made and the status is `error`

### Requirement: Hard timeout
A tool call MUST NOT block the run longer than `tool_timeout_s` (+2 s grace) per attempt, even if the underlying library ignores its own timeout.

#### Scenario: Hanging library
- **WHEN** a tool sleeps for 3 s with `tool_timeout_s=0.1` and no retries
- **THEN** the result status is `timeout`

### Requirement: SSRF guard on page fetches
`fetch_page` MUST only fetch `http`/`https` URLs whose host resolves to public addresses, refusing localhost, private, loopback, link-local (including cloud metadata 169.254.169.254), reserved and multicast addresses with status `blocked`.

#### Scenario: Internal URLs
- **WHEN** fetch_page is called with `http://127.0.0.1:8000/admin`, `file:///etc/passwd`, or `http://169.254.169.254/latest/meta-data`
- **THEN** each result has status `blocked` and no request is sent

### Requirement: Bounded page content
`fetch_page` MUST stop downloading after `max_download_bytes` (2 MB), reject non-HTML/non-text content types, extract main text without boilerplate, and truncate it to `page_char_limit` (6,000) characters. An empty extraction MUST be status `empty`.

#### Scenario: PDF link
- **WHEN** the URL returns `application/pdf`
- **THEN** the status is `error` with "unsupported content-type"

### Requirement: Search and encyclopedia tools
`web_search` MUST return up to `search_results_per_query` hits (title, url, snippet, rank), trying backends in order and returning `empty` (not `error`) when no backend finds anything. `wikipedia` MUST return the best article's title, canonical URL and summary, or `empty` when nothing matches, and MUST send a descriptive User-Agent.

#### Scenario: No results
- **WHEN** every search backend reports no results
- **THEN** web_search returns status `empty`

### Requirement: Cache and fault injection
Successful results MUST be cached on disk for `cache_ttl_s` (24 h) keyed by tool name + arguments; a cache hit MUST skip the call and set `cached=true`. Failed results MUST NOT be cached. When `RA_FAULTS` contains `<tool>:timeout` or `<tool>:error` the runner MUST simulate that failure; `fetch_page:injection` MUST prepend a prompt-injection paragraph to successful page content.

#### Scenario: Second identical call
- **WHEN** the same tool is called twice with the same args and caching on
- **THEN** the underlying function runs once and the second result has `cached=true`
