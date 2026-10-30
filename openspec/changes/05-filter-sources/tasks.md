# Tasks

## 1. Helpers
- [ ] 1.1 Add `domain_of`, `canonical_url`, `terms`, `relevance`, `domain_quality` and the domain lists; verify: small unit tests for each

## 2. Prefilter and scoring
- [ ] 2.1 Add `prefilter_hits`; verify: `test_prefilter_drops_blocked_domains_and_duplicates`
- [ ] 2.2 Add injection patterns, `detect_injection`, `strip_injection` and `score_source`; verify: `test_injection_is_flagged_stripped_and_penalised`

## 3. Selection
- [ ] 3.1 Add `select_sources`; verify: `test_irrelevant_and_domain_cap`
