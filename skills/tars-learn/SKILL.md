---
name: tars-learn
description: >-
  Store, deduplicate, decay-score, and index a global or project-local TARS
  learning rule under ~/.tars/. Use when the user invokes /tars-learn or /learn
  (in TARS context), or automatically from tars-rework when a reusable rule is
  discovered.
---

# TARS Learn (`/tars-learn` / `/learn`)

Persist reusable rules as atomic Markdown files with exponential time-decay scoring, keeping all memory strictly outside the project repository.

---

## Step 1: Classify Scope

Decide whether the rule is **global** or **project-local**:
- **Global (`L<NNN>_<slug>.md` in `~/.tars/global/learning/`):** Personal coding style, communication preferences, CLI/tool habits, cross-repo conventions.
- **Project-local (`P<NNN>_<slug>.md` in `~/.tars/projects/<id>/learning/`):** Repo architecture, domain logic, framework patterns, API/testing conventions.
- **Default to `project`** whenever uncertain. Ensure the target learning directory and `_index.md` exist.

---

## Step 2: Deduplicate & Write

1. Scan the target scope's `_index.md` and existing `*.md` learning files (other than `_index.md`).
2. Choose one action:
   - **Refine in place:** If an existing learning covers the same rule, update its body/tags, set `last_used` to today (`YYYY-MM-DD`), and preserve or reset counts cleanly if appropriate.
   - **Supersede:** If the new rule replaces a conflicting older rule, update the older file to `status: deprecated` (keep the file on disk for audit) and create a new file for the replacement rule.
   - **Create new:** Scan **all** existing `L*.md` / `P*.md` files (including `deprecated` ones so IDs are never reused), take `max_id + 1` zero-padded to 3 digits (`L001`, `P001`, ...), and write `<ID>_<kebab-slug>.md`.

Use this exact YAML frontmatter schema:

```yaml
---
id: P001
scope: project           # global | project
tags: [python, testing]
status: active           # active | probation | deprecated
created: 2026-11-26
last_used: 2026-11-26
applied_count: 1
accepted_count: 1
rework_count: 0
score: 0.67
---
# Concise Rule Title
One-to-three sentence actionable rule stating what to do and when.
```

*(Note: for a brand-new learning with `applied_count: 1`, `accepted_count: 1`, and `delta_t = 0`, `((1 + 1) / (1 + 2)) * exp(0) = 2/3 ≈ 0.67`.)*

---

## Step 3: Recalculate Decay & Rebuild `_index.md`

For every non-superseded learning file in the target scope:
1. Compute `delta_t` = integer days elapsed since `last_used` (`today - last_used`).
2. Calculate:
   `score = round(((accepted_count + 1) / (applied_count + 2)) * exp(-0.003 * delta_t), 2)`
3. Update `status` according to thresholds:
   - `score >= 0.45`: `active`
   - `0.25 <= score < 0.45`: `probation`
   - `score < 0.25` (or explicitly superseded): `deprecated`
4. Rewrite `_index.md` in that learning directory sorted by descending `score`, then ascending `id`, with one line per `active` or `probation` learning:

```markdown
# Project Learnings Index
<!-- Format: ID | score | tags | one-line summary -->
P001 | 0.67 | [python, testing] | Concise one-line actionable summary.
```

*(Omit `deprecated` learnings from `_index.md`, while keeping their `.md` files on disk for audit.)*

---

## Step 4: Report

Confirm the learning `ID`, `scope`, `score`, `status`, and a 1-line summary of what was stored or updated.

---

## Verification

- Confirm the `<ID>_<slug>.md` file exists in `~/.tars/global/learning/` or `~/.tars/projects/<id>/learning/`.
- Confirm `_index.md` lists all `active` and `probation` rules with updated scores.
- Confirm zero `.tars` files exist inside the repository.
