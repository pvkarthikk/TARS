---
name: tars-rework
description: >-
  Handle corrective follow-ups on an active TARS scratchpad task, apply the fix,
  increment rework_count, run blame isolation on applied_learnings, and capture
  reusable learnings. Use when the user invokes /tars-rework or /rework, or
  sends a corrective follow-up while a TARS task is active.
---

# TARS Rework (`/tars-rework` / `/rework`)

Apply a user correction to the active task, isolate blame accurately, and capture reusable rules without polluting the repository.

**Auto-Detection Trigger:** Even if the user does not type `/tars-rework` or `/rework`, automatically follow this workflow whenever a `scratchpad` task is currently `active` in `meta.yaml` and the user sends a corrective follow-up (e.g., *"No, use X instead of Y"*, *"Don't do it that way"*, *"Fix this"*).

---

## Step 1: Load Active Task

1. Resolve `$PROJECT_DIR` (`~/.tars/projects/<folder-name>_<6-char-hash>` or `%USERPROFILE%\.tars\...`).
2. Read `active_task_id` from `$PROJECT_DIR/meta.yaml`.
   - If `active_task_id` is `null` or missing, scan `$PROJECT_DIR/scratchpad/*/task.md` for `status: active`.
   - If no active task exists, tell the user there is no active TARS task and apply the fix normally or offer `/tars-task`.
3. Read `$PROJECT_DIR/scratchpad/<active_task_id>/task.md` (and `plan.md` if present).

---

## Step 2: Patch & Record

1. Apply the requested fix to the codebase (if a gated task has not yet been approved for editing, update `plan.md` instead and re-confirm `go`).
2. Update `$PROJECT_DIR/scratchpad/<active_task_id>/task.md`:
   - Increment `rework_count` by `1`.
   - Update `touched_files` (deduplicated list of repository-relative paths modified across the task).
   - Set `updated` to today's `YYYY-MM-DD` date.
   - Append a concise entry under `## Rework Log`, e.g. `- 2026-11-26 (rework #1): <short summary of correction>`.

---

## Step 3: Blame Isolation

Inspect every learning ID listed in `applied_learnings` in `task.md` (read each rule file from `~/.tars/global/learning/` or `$PROJECT_DIR/learning/`):

- **Strict Blame Rule:** Penalize a learning **ONLY** if the user's correction **explicitly contradicts** that specific rule's text.
- **Do NOT penalize** learnings for unrelated LLM logic bugs, typos, missed edge cases, or one-off requirement changes.

For each **explicitly contradicted** learning:
1. Append its ID (if not already present) to `contradicted_learnings` in `task.md`.
2. Update the learning file's YAML frontmatter:
   - Increment `applied_count` by `1` (do **not** increment `accepted_count`).
   - Increment `rework_count` by `1`.
   - Set `last_used` to today (`YYYY-MM-DD`, so `delta_t = 0`).
   - Recalculate `score = round(((accepted_count + 1) / (applied_count + 2)) * exp(-0.003 * 0), 2)`.
   - Update `status`:
     - `score >= 0.45` -> `active`
     - `0.25 <= score < 0.45` -> `probation`
     - `score < 0.25` -> `deprecated`
3. Rebuild that scope's `_index.md` (`global/learning/_index.md` or `projects/<id>/learning/_index.md`) keeping one line per `active` or `probation` rule: `ID | score | tags | one-line summary`.

---

## Step 4: Capture Reusable Learning (If Applicable)

Evaluate whether the correction represents a reusable preference, convention, or architectural rule (rather than a one-off bug fix):
- If **yes**, invoke the **`tars-learn`** workflow to create or update the rule (and mark any directly superseded learning as `status: deprecated`).
- Mention what was learned in **1 concise line** in your reply.

---

## Verification

- Confirm `rework_count` incremented and `touched_files` updated in `task.md`.
- Confirm any contradicted learning's updated score/status and rebuilt `_index.md` match the formula.
- Confirm zero `.tars` state files exist inside the repository.
