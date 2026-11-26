---
name: tars-accept
description: >-
  Accept and archive an active TARS scratchpad task, reward non-contradicted
  applied learnings with decay-adjusted scores, write outcome.md, move the
  folder to tasks/, and clear active_task_id. Use when the user invokes
  /tars-accept or /accept, or during an implicit-accept sweep.
---

# TARS Accept (`/tars-accept` / `/accept`)

Finalize an active (or swept paused) task, reward helpful learnings, write `outcome.md`, and archive the task folder from `scratchpad/` to `tasks/`.

---

## Step 1: Resolve Target Task

1. Resolve `$PROJECT_DIR` (`~/.tars/projects/<folder-name>_<6-char-hash>` or `%USERPROFILE%\.tars\...`).
2. Determine the target task directory:
   - **Explicit invocation (`/tars-accept` / `/accept`):** Read `active_task_id` from `$PROJECT_DIR/meta.yaml` (or find the single `status: active` folder in `scratchpad/`). If none is active, list any `paused` tasks and ask the user to `/tars-resume <slug>` first.
   - **Implicit-Accept Sweep (from `tars-task`):** Use the specified paused task directory and set `implicit_accept: true`.
3. Read `task.md` in `$PROJECT_DIR/scratchpad/<task-id>/`.

---

## Step 2: Reward Non-Contradicted Learnings

1. Compute the reward list: every ID in `applied_learnings` that is **not** in `contradicted_learnings`.
2. For each rewarded learning ID (located in `~/.tars/global/learning/` for `L*` or `$PROJECT_DIR/learning/` for `P*`):
   - Increment `applied_count` by `1`.
   - Increment `accepted_count` by `1`.
   - Set `last_used` to today (`YYYY-MM-DD`, so `delta_t = 0`).
   - Recalculate `score = round(((accepted_count + 1) / (applied_count + 2)) * exp(-0.003 * 0), 2)`.
   - Update `status` (`>= 0.45` `active`, `0.25 <= score < 0.45` `probation`, `< 0.25` `deprecated`).
3. For any scope (`global` and/or `project`) whose learnings were rewarded, refresh time-decay (`delta_t = days since last_used`) across all non-superseded learnings in that scope and rebuild its `_index.md` (`ID | score | tags | one-line summary`, keeping only `active` and `probation` entries).

---

## Step 3: Write `outcome.md`

1. Gather end commit and diff summary:
   ```bash
   git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "none"
   git -C "$REPO_ROOT" diff --stat "<base_commit>..HEAD" 2>/dev/null
   git -C "$REPO_ROOT" status --short
   ```
   *(Include working tree diff stats if changes are not yet committed.)*

2. Create `$PROJECT_DIR/scratchpad/<task-id>/outcome.md`:

```markdown
---
status: accepted
accepted_at: 2026-11-26
rework_count: 0
base_commit: <base-sha>
end_commit: <head-sha>
touched_files: []
rewarded_learnings: []
contradicted_learnings: []
implicit_accept: false
---
# Outcome: <Task Title>

## Diff Summary
- <Brief bullet summary of files changed and verified behavior>
```

---

## Step 4: Archive & Clear Active Pointer

1. Update `status: accepted` and `updated: <YYYY-MM-DD>` in `task.md`.
2. Move the task directory from `$PROJECT_DIR/scratchpad/<task-id>/` to `$PROJECT_DIR/tasks/<task-id>/`.
   - If `$PROJECT_DIR/tasks/<task-id>/` already exists, append `-2`, `-3`, etc. to the archived folder name.
3. Read `$PROJECT_DIR/meta.yaml`:
   - Set `active_task_id: null` **only if** `meta.yaml`'s `active_task_id` matches the archived `<task-id>`. (Do not clear another currently active task during an implicit-accept sweep of a paused task.)

---

## Verification

- Confirm `$PROJECT_DIR/scratchpad/<task-id>/` no longer exists and `$PROJECT_DIR/tasks/<task-id>/outcome.md` is present.
- Confirm `meta.yaml` `active_task_id` is `null` (for explicit accept) or unchanged (for sweep of a paused task).
- Confirm zero `.tars` files exist inside the repository.
