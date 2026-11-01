# Tasks

## 1. Cases and runner
- [x] 1.1 Add `evals/queries.yaml` with the 12 cases; verify: yaml loads and categories cover happy_path/edge/safety/failure
- [x] 1.2 Add `run_evals.py` with `check()`, per-case faults, crash handling, JSON + Markdown reports, `--ids`; verify: `python evals/run_evals.py --ids empty arithmetic` passes and writes reports

## 2. Baseline
- [ ] 2.1 Add `baseline.py` and `--baseline`; verify: run on `fictional-entities` and see both answers in the JSON

## 3. Run it
- [x] 3.1 Run the full suite on the real model, keep the result files; verify: results committed under `evals/results/` and summarised in `docs/EVALUATION.md`
