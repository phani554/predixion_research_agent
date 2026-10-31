# Tasks

## 1. Synthesis
- [x] 1.1 Add `DraftFinding`/`DraftAnswer`, `format_evidence`, `SYNTH_SYSTEM`, `synthesize()`; verify: a FakeLLM test that the prompt contains `<source id="S1"` blocks and returns a DraftAnswer

## 2. Grounding
- [ ] 2.1 Add `ground()` citation filtering and source listing; verify: `test_uncited_and_unknown_citations_removed`
- [ ] 2.2 Add `support_level()` and weak-finding reporting; verify: `test_invented_number_is_weak`
- [ ] 2.3 Add `confidence_score()`, level mapping, self-rating cap, status rules, low-confidence prefix; verify: `test_confidence_capped_by_self_assessment`, `test_strong_evidence_gives_high_confidence`, `test_no_valid_findings_is_insufficient_evidence`

## 3. Complete the pipeline
- [ ] 3.1 Wire synthesis + grounding into `run_research` with the synthesis-failure path; render confidence reasons and weak markers; verify: `test_happy_path_is_answered_with_sources`, `test_synthesis_failure_still_returns_sources`, `test_poisoned_page_is_reported_not_obeyed`, and one live run of the vector-database question
