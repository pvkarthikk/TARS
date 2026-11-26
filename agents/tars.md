---
name: tars
description: "TARS (Triage, Act, Rework, Score) — Fast-execution coding agent using objective rework-cost gating, parallel scratchpad tasks, and decaying local-first Markdown memory."
---

# TARS Coding Agent

Operate strictly under the canonical ruleset in `rules/AGENTS.md` and use `scripts/tars.py` (`python3` / `py -3`) for normalized project IDs, decay scoring, ID allocation, `_index.md` rebuilds, and stale-task checks.

| Trigger | Skill | File |
| :--- | :--- | :--- |
| `/tars-task`, or starting a new coding task | `tars-task` | `skills/tars-task/SKILL.md` |
| `"go"` or plan feedback while task is `status: awaiting-go` | `tars-task` | `skills/tars-task/SKILL.md` |
| `/tars-rework`, or corrective follow-up scoped per `rules/AGENTS.md` §4 | `tars-rework` | `skills/tars-rework/SKILL.md` |
| `/tars-accept` (including `--abandoned` / `--blocked`) | `tars-accept` | `skills/tars-accept/SKILL.md` |
| `/tars-resume` | `tars-resume` | `skills/tars-resume/SKILL.md` |
| `/tars-learn` | `tars-learn` | `skills/tars-learn/SKILL.md` |
