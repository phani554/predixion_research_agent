# Design: grounded synthesis

## Decisions

### 1. Model drafts, code decides
The LLM writes `DraftAnswer` (short_answer, key_findings[{statement, source_ids}], limitations, assumptions, next_steps, self_confidence). Code produces the `FinalAnswer`. **Why:** the parts most prone to hallucination (citations, confidence) become deterministic and testable.

### 2. Lexical faithfulness check instead of an LLM judge
Numbers-must-appear plus 40% content-word overlap catches invented figures and entities at zero cost. It can't prove entailment (a paraphrase can fail, a negation can pass), so it only marks `weak`, never deletes. **Alternative:** LLM-as-judge per finding: more accurate, +1 call per run; kept for the eval harness / future work.

### 3. Confidence formula
Coverage and source count weigh most (0.3 each) because "how much of the question do independent sources back" is what a reader means by confidence. Coverage counts a sub-question as covered if a cited source was found for it. A pure model self-rating was rejected: models report high confidence by default.

### 4. Cap, never boost
`final = min(code_level, model_level)`: the model may know the evidence is shaky (contradictions) in ways the formula can't see, but it may not talk us into confidence the evidence doesn't support.

### 5. Interfaces
- `synthesizer.py`: `SYNTH_SYSTEM`, `format_evidence(sources) -> str`, `synthesize(question, plan, sources, llm, tracer=None) -> DraftAnswer`
- `grounding.py`: `ground(question, draft, plan, evidence) -> FinalAnswer`, `confidence_score(cited, findings, plan, evidence, dropped) -> (float, reasons)`, `support_level(statement, cited_text) -> "supported"|"weak"`; duplicate limitation/assumption lines removed.
- Schemas: `DraftFinding`, `DraftAnswer`; `Finding.support`.

## Risks / Trade-offs
- Weights are hand-tuned; the eval suite is where they'd be calibrated.
- Lexical checks are language-specific (English).
