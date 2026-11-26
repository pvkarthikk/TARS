---
name: tars-rework
description: >-
  Apply corrective follow-ups on an active TARS scratchpad task, run post-edit
  validation, increment rework_count, run strict blame isolation via
  scripts/tars.py, and capture reusable learnings. Use when the user invokes
  /tars-rework or sends a scoped corrective follow-up on the current active task.
---

# TARS Rework (`/tars-rework`)

Apply a correction to an `active` task, validate the change, isolate blame accurately, and capture reusable rules without polluting the repository.

## Scoped Auto-Detection Rule

Even without `/tars-rework`, automatically treat a message as rework **ONLY IF**:
1. The current task in `meta.yaml` / `scratchpad/` has `status: active` (and has not been untouched for 7+ days), **AND**
2. Either that task was created/resumed in **this conversation**, **OR** the user's message explicitly names at least one file in its `touched_files`.

If neither condition holds (for example, an older active task from another session with no matching file name), **ask the user** before treating the request as `/tars-rework`.

**Plan-Edit Guard:** If the current task has `status: awaiting-go`, route plan feedback to **`tars-task` (Mode B2)** to update `plan.md` — **do NOT increment `rework_count`**.

---

## Step 1: Load Active Task & Check Staleness

1. Resolve `$PROJECT_DIR` and run stale sweep first:
   ```bash
   python3 <plugin-root>/scripts/tars.py project-id --repo . --json
   python3 <plugin-root>/scripts/tars.py status --project-dir "$PROJECT_DIR" --stale-days 7 --pause-stale --json
   ```
2. Read `active_task_id` from `$PROJECT_DIR/meta.yaml` and open `$PROJECT_DIR/scratchpad/<active_task_id>/task.md` (plus `plan.md` if present).
   - If the task was just auto-paused for staleness or no `active` task exists, inform the user and offer `/tars-resume` or `/tars-task`.
   - If `status: awaiting-go`, switch to `tars-task` Mode B2 without incrementing `rework_count`.

---

## Step 2: Patch, Validate & Record

1. **Apply fix safely:** Obey repo instruction precedence (`AGENTS.md`, `.github/copilot-instructions.md`, `CLAUDE.md`) and safety boundaries (ask before security/auth edits or deleting non-trivial work; never run `git reset`, `git checkout --`, `git restore`, `git clean`, `git stash`, `git rebase`, or `git push --force`; never touch `pre_existing_changes` unexpectedly).
2. **Mandatory Post-Edit Validation:** Discover commands from repo docs/configs and run **format → lint → build → focused tests**. Record each result (`passed` | `failed` | `skipped`) under `validation:` in `task.md`. **Never report a skipped check as passed.**
3. **Update `task.md`:**
   - Increment `rework_count` by `1`.
   - Merge newly modified repo-relative paths into `touched_files` (deduplicated).
   - Update `validation:` and `updated: <YYYY-MM-DD>`.
   - Append a concise entry under `## Rework Log`, e.g., `- 2026-11-26 (rework #1): <summary>`.
4. Include a `Validation:` summary line in your response.

---

## Step 3: Blame Isolation

Inspect every ID in `applied_learnings` in `task.md`:

- **Strict Blame Rule:** Penalize a rule **ONLY** if the user's correction **explicitly contradicts** that rule's text. Never penalize for unrelated LLM logic bugs, missed edge cases, or one-off requirement changes.

For each explicitly contradicted rule:
1. Add its ID (if missing) to `contradicted_learnings` in `task.md`.
2. Increment `applied_count` (+1) and `rework_count` (+1) (leave `accepted_count` unchanged), set `last_used` to today (`YYYY-MM-DD`), and calculate the new score & status:
   ```bash
   python3 <plugin-root>/scripts/tars.py score --applied <new_applied> --accepted <accepted> --last-used <YYYY-MM-DD> --json
   ```
3. Write updated `applied_count`, `rework_count`, `last_used`, `score`, and `status` to that rule file, then rebuild its scope's `_index.md`:
   ```bash
   python3 <plugin-root>/scripts/tars.py rebuild-index --dir "<learning-dir>" --write --json
   ```

---

## Step 4: Capture Reusable Learning (If Applicable)

If the correction expresses a reusable preference, convention, or architectural rule (and contains no secrets), invoke **`tars-learn`** to store or supersede the rule, and summarize what was learned in 1 line.

---

## Verification

- Confirm `rework_count`, `validation:`, and `touched_files` are updated in `task.md`, and `Validation:` is included in the reply without marking skipped checks as passed.
- Confirm zero `.tars` files exist inside the repository.
