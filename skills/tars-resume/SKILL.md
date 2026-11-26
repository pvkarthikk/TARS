---
name: tars-resume
description: >-
  List paused TARS scratchpad tasks or switch back to a paused task by slug,
  parking any active task and restoring full task context. Use when the user
  invokes /tars-resume or /resume.
---

# TARS Resume (`/tars-resume` / `/resume`)

List or switch between parallel in-flight tasks stored in `~/.tars/projects/<id>/scratchpad/`.

---

## Step 1: Scan Scratchpad

1. Resolve `$PROJECT_DIR` (`~/.tars/projects/<folder-name>_<6-char-hash>` or `%USERPROFILE%\.tars\...`).
2. Read every `task.md` in `$PROJECT_DIR/scratchpad/*/`.
   - Note which task (if any) currently has `status: active` (or is referenced by `active_task_id` in `meta.yaml`).
   - Collect all tasks with `status: paused`.

---

## Step 2: List Mode (No Slug Provided)

If the user invoked `/tars-resume` (or `/resume`) with no `[task-slug]`:
- Show the currently active task (if any) in one line.
- Display a concise Markdown table of all `paused` tasks:

| Task Slug | Updated | Rework | Touched Files | Summary |
| :--- | :--- | :--- | :--- | :--- |
| `2026-11-26_fix-auth` | 2026-11-26 | 1 | 2 | <Title / 1-line summary> |

- If there are no paused tasks, tell the user and stop.
- Otherwise, tell the user they can run `/tars-resume <task-slug>` to switch to one.

---

## Step 3: Switch Mode (`task-slug` Provided)

1. Match `<task-slug>` against folders in `$PROJECT_DIR/scratchpad/`:
   - Prefer an exact folder name match (`<YYYY-MM-DD>_<slug>`) or exact slug suffix match.
   - Otherwise match an unambiguous substring. If multiple tasks match, list them and ask the user which one to resume. If none match, say so and list available paused tasks.
2. **Park Current Active Task:** If another task is currently `active` (different from the selected task), set its `status: paused` and `updated: <YYYY-MM-DD>` in its `task.md`.
3. **Activate Selected Task:**
   - Set `status: active` and `updated: <YYYY-MM-DD>` in the selected task's `task.md`.
   - Update `active_task_id: <selected-task-id>` in `$PROJECT_DIR/meta.yaml`.
4. **Reload Context:**
   - Read the selected task's `task.md`, `plan.md` (if present), and list any files in `artifacts/` (if present).
   - Inspect `git -C "$REPO_ROOT" status --short` (and compare against `base_commit` / `touched_files`).
5. **Report:** Summarize where work left off (original prompt, gate mode, rework count, touched files, current git status, and the immediate next step).

---

## Verification

- Confirm only the resumed task has `status: active` across `$PROJECT_DIR/scratchpad/*/task.md`.
- Confirm `$PROJECT_DIR/meta.yaml` sets `active_task_id` to the resumed task directory name.
