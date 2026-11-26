---
name: tars-task
description: >-
  Start a new TARS coding task with implicit-accept sweeps, active-task parking,
  tagged learning recall, and objective rework-cost gating (fast-track vs
  gated). Use when the user invokes /tars-task or /task, or starts a new
  implementation task under TARS.
---

# TARS Task (`/tars-task` / `/task`)

Triage and initialize a task under `~/.tars/` (`%USERPROFILE%\.tars\` on Windows) without creating any state files inside the project repository. If a TARS CLI or MCP tool is present in your toolset, call it for hashing, state updates, and Git checks; otherwise use terminal and filesystem tools directly.

## Step 0: Resolve TARS Root & Project ID

1. **Determine repo root (or fallback `cwd`):**
   ```bash
   REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
   FOLDER_NAME=$(basename "$REPO_ROOT")
   HASH_INPUT=$(git -C "$REPO_ROOT" config --get remote.origin.url 2>/dev/null || printf '%s' "$REPO_ROOT")
   ```
   *(If `remote.origin.url` is empty, `HASH_INPUT` falls back to `$REPO_ROOT`.)*

2. **Compute the 6-char lowercase SHA-256 prefix** (use whichever runtime is available):
   - **Linux:** `printf '%s' "$HASH_INPUT" | sha256sum | cut -c1-6`
   - **macOS:** `printf '%s' "$HASH_INPUT" | shasum -a 256 | cut -c1-6`
   - **Cross-platform Python:** `python3 -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:6])" "$HASH_INPUT"`
   - **Windows PowerShell:**
     ```powershell
     $bytes = [System.Text.Encoding]::UTF8.GetBytes($hashInput)
     $hash = ([System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") }) -join ""
     $shortHash = $hash.Substring(0, 6)
     ```

3. **Auto-initialize missing storage** (`TARS_ROOT="${HOME}/.tars"`, or `"$env:USERPROFILE\.tars"` on Windows):
   `PROJECT_DIR="$TARS_ROOT/projects/${FOLDER_NAME}_${SHORT_HASH}"`
   Ensure these exist:
   - `$TARS_ROOT/config.yaml` (if missing, create with `version: 1` and `decay_lambda: 0.003`)
   - `$TARS_ROOT/global/learning/_index.md` (if missing, create with header `# Global Learnings Index`)
   - `$PROJECT_DIR/learning/_index.md` (if missing, create with header `# Project Learnings Index`)
   - `$PROJECT_DIR/scratchpad/` and `$PROJECT_DIR/tasks/`
   - `$PROJECT_DIR/meta.yaml` (if missing, create with `repo_path`, `remote_url`, and `active_task_id: null`)

---

## Step 1: Implicit Accept Sweep

Scan all folders in `$PROJECT_DIR/scratchpad/` whose `task.md` has `status: paused`:

1. Read `base_commit` and `touched_files` from `task.md`. Skip tasks where `touched_files` is empty (`[]`).
2. Check if those files are clean in the working tree and committed since `base_commit`:
   ```bash
   git -C "$REPO_ROOT" status --porcelain -- <touched_files...>
   git -C "$REPO_ROOT" log --oneline "<base_commit>..HEAD" -- <touched_files...>
   ```
3. If `git status --porcelain` returns **no output** for those files AND `git log` shows **at least one commit** since `base_commit`, automatically run the **`tars-accept`** archival workflow on that paused task (recording `implicit_accept: true` in `outcome.md`) before proceeding.

---

## Step 2: Park Any Currently Active Task

Check `meta.yaml` (`active_task_id`) and any `task.md` under `$PROJECT_DIR/scratchpad/` with `status: active`:
- Update its `status` to `paused` and set `updated` to today's `YYYY-MM-DD` date.
- Do **not** delete or archive it.

---

## Step 3: Recall Learnings

1. Read `$TARS_ROOT/global/learning/_index.md` and `$PROJECT_DIR/learning/_index.md`.
2. Index lines have the format `ID | score | tags | one-line summary`.
3. Recall rules:
   - **Active (`score >= 0.45`):** Load the full learning markdown file if any tag matches the task domain, language, or request.
   - **Probation (`0.25 <= score < 0.45`):** Load **only** on an exact tag match with the task.
   - **Precedence:** Project-local rules (`P*`) override global rules (`L*`) if they conflict.
4. Collect the IDs of loaded rules into `applied_learnings`.

---

## Step 4: Evaluate the Objective Rework-Cost Gate

Check the task against **all four objective triggers** (do not rely on subjective confidence):

1. **File Spread:** Estimated edits touch **more than 3 files**.
2. **Critical Surfaces:** Modifies database schemas, authentication/security, CI/CD pipelines, build configs, or public/external APIs.
3. **Destructive Scope:** Deletes **more than 50 lines** of code or adds/removes third-party dependencies.
4. **Irreversibility:** Performs operations that cannot be trivially reverted with `git checkout` / `git reset`.

- If **NO** triggers match: `gate: fast-track` (`gate_triggers: []`).
- If **ONE OR MORE** triggers match: `gate: gated` (`gate_triggers: [<matched triggers>]`).

---

## Step 5: Initialize Task Directory

1. Build `<YYYY-MM-DD>_<kebab-slug>` from today's date and a short 2–5 word kebab-case slug. If that folder already exists in `scratchpad/` or `tasks/`, append `-2`, `-3`, etc.
2. Record `BASE_COMMIT=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "none")`.
3. Create `$PROJECT_DIR/scratchpad/<task-id>/task.md`:

```markdown
---
id: 2026-11-26_add-login-validation
status: active
created: 2026-11-26
updated: 2026-11-26
base_commit: <HEAD-sha>
gate: fast-track        # fast-track | gated
gate_triggers: []       # e.g. [file_spread, critical_surfaces]
applied_learnings: []   # e.g. [L002, P001]
contradicted_learnings: []
rework_count: 0
touched_files: []
---
# Task: <Short Title>

## Prompt
<Raw user task description>

## Rework Log
```

4. Update `$PROJECT_DIR/meta.yaml` to set `active_task_id: <task-id>`.

---

## Step 6: Execute or Gate

### Mode A: `fast-track` (No triggers hit)
1. **Skip `plan.md`** — implement the solution immediately.
2. After editing, update `touched_files` (workspace-relative paths) and `updated` in `task.md`.
3. End your response with:
   - What changed (concise summary of modified files/behavior)
   - **1–3 key assumptions** made so the user can correct them via `/tars-rework` (or follow-up).

### Mode B: `gated` (One or more triggers hit)
1. **Do NOT edit repository files yet.**
2. Write a concise **3–5 bullet high-level plan** to `$PROJECT_DIR/scratchpad/<task-id>/plan.md` (plus at most **2 clarifying questions** if requirements are ambiguous).
3. Present the triggered gate rule(s), the 3–5 bullet plan (and any clarifying questions), and ask the user for a quick `go` before proceeding.

---

## Verification

Before concluding:
- Confirm `git status` inside `$REPO_ROOT` shows **zero** `.tars` files, scratchpads, or memory artifacts inside the repository.
- Confirm `$PROJECT_DIR/scratchpad/<task-id>/task.md` and `$PROJECT_DIR/meta.yaml` (`active_task_id`) reflect the active task state.
