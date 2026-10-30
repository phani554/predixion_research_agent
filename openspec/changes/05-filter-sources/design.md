# Design: source filtering

## Decisions

### 1. Deterministic, explainable scoring
Lexical relevance + domain tier + content length. Cheap (no tokens), fast, unit-testable, and every rejection has a human-readable reason that shows up in the run JSON and the demo. **Alternative:** LLM or embedding re-ranker. Better semantics, but costs a call per run and is harder to test; listed as future work, to be measured against this baseline with the eval suite.

### 2. Weights 0.5 / 0.3 / 0.2
Relevance dominates because an authoritative but off-topic page is useless; domain quality breaks ties between similar pages. Tuned by eye on live runs; the eval suite is how we'd tune them properly.

### 3. Strip, don't drop, injected sources
A page with one malicious line may still hold useful facts. We remove the offending sentences, penalise the score, flag it, and the final answer tells the user. Defence in depth: the synthesizer prompt also says source text is data.

### 4. Domain cap 2 and total cap 8
Diversity beats depth for confidence, and 8 × 2,500 chars keeps the synthesis prompt around 6-7k tokens (cost/latency).

### 5. Interfaces (`src/research_agent/sources.py`)
- `domain_of(url)`, `canonical_url(url)`, `domain_quality(domain) -> float`, `terms(text) -> set[str]`, `relevance(query, doc) -> float`
- `detect_injection(text) -> bool`, `strip_injection(text) -> str`
- `prefilter_hits(hits: list[(step_id, SearchHit)], query_by_step) -> (kept: list[(step_id, hit, rel)], rejected)`
- `score_source(src, query_text) -> Source`
- `select_sources(candidates, settings) -> (chosen, rejected)`
- Schemas: `Source`, `RejectedSource`.

## Risks / Trade-offs
- Lexical relevance misses synonyms ("LLM" vs "language model"); threshold kept low (0.1).
- Pattern-based injection detection is bypassable by paraphrase; it's one layer, not the defence.
- Domain lists are opinionated; they live in one place and are easy to change.
