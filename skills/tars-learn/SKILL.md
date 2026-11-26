---
name: tars-learn
description: >-
  Store, deduplicate, supersede, decay-score, and index a personal global or
  project-local TARS learning rule under ~/.tars/ using scripts/tars.py. Use
  when the user invokes /tars-learn or automatically from /tars-rework when a
  reusable non-secret rule is discovered.
---

# TARS Learn (`/tars-learn`)

Persist personal, machine-local rules as atomic Markdown files under `~/.tars/` (`%USERPROFILE%\.tars\` on Windows) using `scripts/tars.py` for ID allocation, decay math, and `_index.md` generation.

---

## Step 0: Secret & Precedence Guard

- **Never store secrets:** Before writing anything to `~/.tars/`, verify the rule contains **no** API keys, tokens, passwords, private keys, connection strings with credentials, or PII. If present, refuse to store the raw secret and ask the user to redact or generalize it into a safe pattern.
- **Instruction Precedence:** Remind yourself (and note if relevant) that repository instructions (`AGENTS.md`, `.github/copilot-instructions.md`, `CLAUDE.md`) always outrank personal learned rules, and a learned rule can never disable an approval gate.

---

## Step 1: Classify Scope

Resolve `$TARS_ROOT` and `$PROJECT_DIR` via:
```bash
python3 <plugin-root>/scripts/tars.py project-id --repo . --json
```
- **Global (`L<NNN>_<slug>.md` in `$TARS_ROOT/global/learning/`):** Personal style, CLI habits, cross-repo preferences.
- **Project-local (`P<NNN>_<slug>.md` in `$PROJECT_DIR/learning/`):** Repo architecture, domain rules, testing/build conventions.
- **Default to `project`** when uncertain.

---

## Step 2: Deduplicate, Supersede & Write

1. Read the target `_index.md` and scan existing `*.md` rules in that directory.
2. Choose one action:
   - **Refine in place:** Update the existing file's wording/tags and set `last_used` to today (`YYYY-MM-DD`).
   - **Supersede an older rule `<OLD_ID>`:**
     1. Allocate the replacement ID:
        ```bash
        python3 <plugin-root>/scripts/tars.py next-id --dir "<learning-dir>" --prefix <L|P>
        ```
     2. Write the new rule file with `supersedes: <OLD_ID>`, `applied_count: 0`, `accepted_count: 0`, `rework_count: 0`, `score: 0.50`, `status: active`.
     3. Update the older `<OLD_ID>` file to `status: deprecated` and `superseded_by: <NEW_ID>` (keep the file on disk for audit).
   - **Create new rule:**
     1. Allocate the next ID via `scripts/tars.py next-id --dir "<learning-dir>" --prefix <L|P>` (scans all files including `deprecated` so IDs are never reused).
     2. Write `<ID>_<kebab-slug>.md` using this exact schema:

```yaml
---
id: P001
scope: project           # global | project
tags: [python, testing]
status: active           # active | probation | deprecated
created: 2026-11-26
last_used: 2026-11-26
applied_count: 0
accepted_count: 0
rework_count: 0
score: 0.50
supersedes: null
---
# Concise Rule Title
One-to-three sentence actionable rule stating what to do and when.
```

*(New rules start neutral at `applied_count: 0`, `accepted_count: 0`, `score: 0.50`.)*

---

## Step 3: Recalculate Decay & Rebuild `_index.md`

Run `scripts/tars.py` to refresh decay scores and regenerate `_index.md` deterministically:

```bash
python3 <plugin-root>/scripts/tars.py rebuild-index --dir "<learning-dir>" --write --json
```

---

## Step 4: Report

Confirm the learning `ID`, `scope`, `score` (`0.50` for new rules), `status`, `supersedes` (if replacing an older rule), and a 1-line summary.

---

## Verification

- Confirm the new/updated `<ID>_<slug>.md` contains zero secrets, starts at `applied_count: 0` / `accepted_count: 0` / `score: 0.50` (if new), and `_index.md` was rebuilt by `scripts/tars.py`.
- Confirm zero `.tars` files exist inside the repository.
