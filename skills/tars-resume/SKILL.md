---
name: tars-resume
description: >-
  List paused TARS scratchpad tasks (flagging stale ones older than N days) or
  switch back to a paused task by slug, parking any active task and restoring
  context. Use when the user invokes /tars-resume.
---

# TARS Resume (`/tars-resume`)

List paused tasks, auto-pause stale active tasks, flag stale paused tasks, and switch cleanly between in-flight scratchpad tasks under `~/.tars/projects/<id>/scratchpad/`.

---

## Step 1: Scan Scratchpad & Auto-Pause Stale Active Tasks

1. Resolve `$PROJECT_DIR` and inspect scratchpad status (with `--pause-stale`, default `stale_days: 7`, or configured `stale_days` from `~/.tars/config.yaml`):
   ```bash
   python3 <plugin-root>/scripts/tars.py project-id --repo . --json
   python3 <plugin-root>/scripts/tars.py status --project-dir "$PROJECT_DIR" --stale-days 7 --pause-stale --json
   ```
2. Note any tasks returned in `auto_paused` (active or `awaiting-go` tasks untouched for ≥ `stale_days` are automatically moved to `paused`) and `stale_paused` (paused tasks aged ≥ `stale_days`).

---

## Step 2: List Mode (No `[task-slug]` Provided)

When invoked as `/tars-resume` with no slug:
- Report any `auto_paused` tasks first.
- Show the current `active` or `awaiting-go` task (if any) in one line.
- Display all `paused` tasks in a table, flagging tasks where `stale == true`:

| Task Slug | Updated | Age | Rework | Touched | Flag | Summary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `2026-11-26_fix-auth` | 2026-11-26 | 0d | 1 | 2 | — | Fix token validation |
| `2026-11-15_old-refactor` | 2026-11-15 | 11d | 0 | 3 | `STALE (11d)` | Old API refactor |

- If there are no paused tasks, say so and stop.
- Tell the user they can switch via `/tars-resume <task-slug>` or close stale tasks via `/tars-accept <task-slug> --abandoned` (or `--blocked`).

---

## Step 3: Switch Mode (`[task-slug]` Provided)

1. Match `<task-slug>` against folders in `$PROJECT_DIR/scratchpad/` (exact name -> exact slug suffix -> unambiguous substring). If ambiguous or missing, list candidates and ask.
2. **Park Current Active Task:** If another task is currently `active` or `awaiting-go`, set its `task.md` to `status: paused` and `updated: <YYYY-MM-DD>`.
3. **Restore Selected Task:**
   - Determine restored status: if `plan.md` exists and `gate: gated` had not yet received `"go"`, restore `status: awaiting-go`; otherwise set `status: active`.
   - Set `updated: <YYYY-MM-DD>` in `task.md` and `active_task_id: <selected-task-id>` in `$PROJECT_DIR/meta.yaml`.
4. **Reload Context & Check Working Tree:**
   - Read `task.md`, `plan.md` (if present), and list `artifacts/` (if present).
   - Run `git status --short` and compare against `pre_existing_changes`, `base_commit`, and `touched_files`.
5. **Report:** Summarize where work left off, any `validation:` status, current `git status`, and the immediate next step (or ask for `go` if restored to `awaiting-go`).

---

## Verification

- Confirm at most one task has `status: active` or `status: awaiting-go` across `$PROJECT_DIR/scratchpad/*/task.md`, matching `active_task_id` in `meta.yaml`.
