---
name: tars-accept
description: >-
  Explicitly close and archive a TARS scratchpad task as accepted, abandoned, or
  blocked, optionally rewarding non-contradicted learnings and recording
  validation, first_pass, and gate outcome metadata. Use when the user invokes
  /tars-accept (including --abandoned or --blocked).
---

# TARS Accept (`/tars-accept`)

Explicitly close a scratchpad task (`accepted`, `abandoned`, or `blocked`), write `outcome.md`, and archive the folder to `tasks/`. Tasks are **never** auto-accepted on commit.

---

## Step 1: Resolve Target Task & Closure Mode

1. Resolve `$PROJECT_DIR`:
   ```bash
   python3 <plugin-root>/scripts/tars.py project-id --repo . --json
   ```
2. Parse optional arguments:
   - `[task-slug]` — target a specific task in `$PROJECT_DIR/scratchpad/` (defaults to `active_task_id` in `meta.yaml`, or the single `active`/`awaiting-go` task). If none matches, list `paused` tasks and ask the user to specify a slug or `/tars-resume`.
   - `--abandoned [reason]` -> closure status `abandoned`
   - `--blocked [reason]` -> closure status `blocked`
   - Otherwise -> closure status `accepted`
3. Read `$PROJECT_DIR/scratchpad/<task-id>/task.md`.

---

## Step 2: Update Learnings (Accepted Only)

- **If `status == accepted`:**
  1. `rewarded_learnings` = IDs in `applied_learnings` not in `contradicted_learnings`.
  2. For each rewarded ID (in `~/.tars/global/learning/` for `L*` or `$PROJECT_DIR/learning/` for `P*`):
     - Increment `applied_count` (+1) and `accepted_count` (+1), and set `last_used` to today (`YYYY-MM-DD`).
  3. Rebuild each affected scope's index (refreshing decay across all rules in that scope):
     ```bash
     python3 <plugin-root>/scripts/tars.py rebuild-index --dir "<learning-dir>" --write --json
     ```
- **If `status` is `abandoned` or `blocked`:**
  - **Do NOT reward any learnings** (`rewarded_learnings: []`).
  - Ask for or record a brief `close_reason`. Never run `git reset`, `git checkout --`, `git restore`, `git clean`, or `git stash` to revert changes automatically.

---

## Step 3: Write `outcome.md`

Gather commit/diff metadata (`git rev-parse HEAD`, `git diff --stat <base_commit>..HEAD`, `git status --short`), compute `first_pass = (status == "accepted" and rework_count == 0)`, copy `gate`, `gate_triggers`, and `validation` from `task.md`, and write `$PROJECT_DIR/scratchpad/<task-id>/outcome.md`:

```markdown
---
status: accepted        # accepted | abandoned | blocked
closed_at: 2026-11-26
gate: fast-track        # fast-track | gated
gate_triggers: []
first_pass: true
rework_count: 0
validation:
  format: passed
  lint: passed
  build: skipped
  tests: passed
base_commit: <base-sha>
end_commit: <head-sha>
touched_files: []
rewarded_learnings: []
contradicted_learnings: []
close_reason: null
---
# Outcome: <Task Title>

## Summary
- <Diff summary, closure note, and validation results (never claim skipped checks passed)>
```

---

## Step 4: Archive & Clear Active Pointer

1. Set `status: <accepted|abandoned|blocked>` and `updated: <YYYY-MM-DD>` in `task.md`.
2. Move `$PROJECT_DIR/scratchpad/<task-id>/` to `$PROJECT_DIR/tasks/<task-id>/` (append `-2`, `-3` on collision).
3. Update `$PROJECT_DIR/meta.yaml`: set `active_task_id: null` **only if** `active_task_id` matched `<task-id>`.

---

## Verification

- Confirm `$PROJECT_DIR/tasks/<task-id>/outcome.md` records `status`, `validation`, `first_pass`, `gate`, and `gate_triggers`.
- Confirm `$PROJECT_DIR/scratchpad/<task-id>/` was moved out and `meta.yaml` `active_task_id` is updated cleanly.
- Confirm zero `.tars` files exist inside the repository.
