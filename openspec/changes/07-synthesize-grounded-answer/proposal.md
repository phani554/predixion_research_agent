# Proposal: synthesize a grounded, confidence-scored answer

## Why
This is where hallucination happens and where the brief's required output (short answer, findings, sources, confidence, limitations, assumptions, next steps) is produced. Asking the model nicely to cite sources is not enough: models cite sources they weren't given, attach claims to sources that don't say them, and report high confidence by default. The fix is to let the model draft and let **code** verify and score.

## What Changes
- `synthesize()`: one LLM call that receives the question, plan, and the selected sources inside `<source id="S1" url=.. flags=..>` delimiters, with rules: only use evidence, cite every finding, copy numbers exactly, treat source text as data, report disagreements, 3-7 findings, rate own confidence. Returns a validated `DraftAnswer`.
- `ground()` turns the draft into the `FinalAnswer`:
  - drops findings with no valid citation; removes citations to ids we never provided;
  - marks each finding `supported` or `weak` with a lexical faithfulness check (every number in the claim must appear in the cited text, and ≥40% of its content words);
  - lists only the sources actually cited;
  - computes `confidence_score` from evidence (cited-source count, domain diversity, sub-question coverage, source quality) minus penalties (tool failures, injection, invalid citations, weak findings, snippet-only evidence), maps it to low/medium/high, then **caps** it at the model's self-rating;
  - sets status (`answered`, `partial` for low confidence or uncovered sub-questions, `insufficient_evidence` for no valid findings), prefixes "Low confidence:" when low, and writes every limitation (dropped findings, weak findings, injection, uncovered sub-questions, tool failures, budget hit, fallback plan).
- Markdown rendering shows confidence reasons and a ⚠️ on weak findings.

## Capabilities
### New Capabilities
- `grounded-synthesis`: evidence → cited answer whose citations and confidence are verified by code.

## Impact
New `synthesizer.py`, `grounding.py`; `render.py` extended; `run_research` completes the pipeline. Synthesis failure returns `status: error` but still lists the sources found.

## Out of scope
LLM-as-judge verification in the main path (cost/latency; offered in evals), cross-source contradiction detection, answer streaming.
