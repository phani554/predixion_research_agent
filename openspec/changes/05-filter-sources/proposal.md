# Proposal: filter sources

## Why
The brief asks for "filtering of noisy or weak information" and flags "low-quality or irrelevant sources" and "prompt injection awareness". Search results include login walls, SEO farms, off-topic pages, duplicates, and occasionally text written to manipulate AI readers. Everything that reaches the synthesizer becomes a potential claim, so filtering is our first hallucination defence.

## What Changes
- Deterministic scoring of each candidate: `score = 0.5·relevance + 0.3·domain_quality + 0.2·content_quality` (minus 0.3 for suspected injection).
- Relevance = share of the sub-question's content words found in the page (stopwords removed).
- Domain quality tiers: high (.gov/.edu/.ac.in, wikipedia, arxiv, github, docs./developer./engineering. hosts), low (medium, reddit, blog platforms), blocked before fetch (pinterest, facebook, instagram, tiktok, x/twitter, linkedin, youtube, quora, scribd, slideshare).
- Flags: `thin_content` (<300 chars), `snippet_only`, `prompt_injection_suspected`.
- Prompt-injection detection by pattern; matching sentences are stripped from content and snippet before any LLM sees them.
- Selection: drop relevance < 0.1 or score < 0.25, max 2 sources per domain, max 8 total, assign ids S1..Sn by score. Every rejection is kept with a reason.

## Capabilities
### New Capabilities
- `source-filtering`: deciding which retrieved content is trustworthy and relevant enough to use.

## Impact
New `sources.py` (pure functions, no I/O). The executor (next change) uses it; rejected sources will appear in the run JSON.

## Out of scope
LLM re-ranking, embedding similarity, fact cross-checking between sources, a learned injection classifier.
