---
trigger: always_on
description: Commit discipline
---
- One task (or one spec artifact) per commit. Small, reviewable diffs.
- Conventional commits: `spec(<change>): ...`, `feat(<area>): ...`, `fix(<area>): ...`, `test(<area>): ...`, `docs: ...`, `chore: ...`.
- The commit body says what was decided and why, in one or two lines, when it is not obvious.
- Never commit `.env`, `runs/`, `outputs/`, `.cache/`.
