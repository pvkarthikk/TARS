<p align="center">
  <img src="assets/logo.svg" width="96" height="96" alt="TARS logo">
</p>

<h1 align="center">TARS</h1>

<p align="center">
  <strong>Triage · Act · Rework · Score</strong><br>
  Fast-execution coding agent plugin for <strong>Antigravity</strong>, <strong>GitHub Copilot (VS Code &amp; CLI)</strong>, and <strong>Claude Code</strong> using objective rework-cost gating, parallel scratchpad tasks, and decaying local-first Markdown memory.
</p>

---

## Key Capabilities

- **Optimistic Execution:** Routine, low-blast-radius tasks bypass upfront planning (`gate: fast-track`) and go straight to working code, validation, and 1–3 key assumptions.
- **Objective Rework-Cost Gate:** Replaces subjective planning guesses with 4 objective triggers (`> 3` files touched, critical surfaces, `> 50` deleted lines or dependency changes, or non-git-revertible actions). Gated tasks enter `status: awaiting-go` until you confirm `go`.
- **Mandatory Post-Edit Validation & Working-Tree Guard:** Snapshots `pre_existing_changes` via `git status --short`, forbids destructive Git commands (`reset`, `checkout --`, `restore`, `clean`, `stash`, `rebase`, force-push), and runs **format → lint → build → focused tests** after edits without ever claiming skipped checks passed.
- **Parallel Scratchpad Tasks:** Park active tasks, auto-pause stale active tasks after 7 days of inactivity, switch context with `/tars-resume`, and close tasks as `accepted`, `abandoned`, or `blocked` via `/tars-accept`.
- **Personal Decaying Memory (`~/.tars/`):** Stores atomic global (`L*`) and project-local (`P*`) rules starting at `0.50` (`applied_count: 0, accepted_count: 0`) with exponential decay (`e^(-0.003 * delta_t)`), refreshed deterministically by `scripts/tars.py`. Learned rules are **personal and machine-local** — never shared through Git — and repository instruction files (`AGENTS.md`, `.github/copilot-instructions.md`, `CLAUDE.md`) always outrank them.
- **Zero Repo Pollution:** Never creates `.tars`, scratchpads, or memory artifacts inside your project repository.

---

## Supported Harnesses

`rules/AGENTS.md` is the **single canonical rules file**; agent and Copilot instruction files are short pointers to `rules/AGENTS.md` and `scripts/tars.py`.

| Harness | Manifest | Rules / Agent Pointer | Skills |
| :--- | :--- | :--- | :--- |
| **Antigravity** (CLI, App, IDE) | `plugin.json` (`"agents"`, `"skills"`) | `rules/AGENTS.md` + `agents/tars.md` | `skills/tars-*/SKILL.md` |
| **GitHub Copilot** (VS Code & CLI) | `plugin.json` (`"agents": "com.github.copilot/agents/"`, `"skills": "skills/"`) | `com.github.copilot/agents/tars.agent.md` + `com.github.copilot/rules/tars.instructions.md` | `skills/tars-*/SKILL.md` |
| **Claude Code** | `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` | `agents/tars.md` | `skills/tars-*/SKILL.md` |

---

## Commands & Skills (`/tars-*` Only)

TARS uses `/tars-*` commands exclusively (no bare `/task`, `/rework`, `/accept`, `/resume`, or `/learn` shorthands) so commands never collide with built-in host commands such as `/resume` or `/learn`.

| Command | Description |
| :--- | :--- |
| `/tars-task <description>` | Run stale-task auto-pause, suggest `/tars-accept` for cleanly committed paused tasks, refresh decay indexes, evaluate the rework-cost gate, snapshot `pre_existing_changes`, and execute or enter `status: awaiting-go` (also handles `"go"` and plan edits). |
| `/tars-rework <correction>` | Scoped auto-detection (only for an `active` task from this conversation or naming its `touched_files`; plan edits before `"go"` route to `/tars-task` without incrementing `rework_count`). Patches, validates, runs strict blame isolation, and captures reusable rules. |
| `/tars-accept [task-slug] [--abandoned \| --blocked]` | Explicitly close a scratchpad task (`accepted`, `abandoned`, or `blocked`). Only `accepted` rewards non-contradicted learnings. Writes `outcome.md` (with `validation`, `first_pass`, `gate`, `gate_triggers`) and archives to `tasks/`. |
| `/tars-resume [task-slug]` | Auto-pauses stale active tasks (`>= 7` days), lists paused tasks (flagging stale ones older than `stale_days`), or switches back to `[task-slug]` and restores context. |
| `/tars-learn <rule>` | Rejects secrets/PII, classifies `global` vs. `project` scope, deduplicates or supersedes via `supersedes:` / `superseded_by:`, initializes new rules at `0.50`, and rebuilds `_index.md` via `scripts/tars.py`. |

---

## Installation & Usage

### Antigravity

- **CLI:**
  ```sh
  agy plugin install https://github.com/pvkarthikk/TARS
  ```
- **App / IDE (local symlink):**
  ```sh
  ln -s /path/to/TARS ~/.gemini/config/plugins/tars
  ```
Invoke `/tars-task`, `/tars-rework`, `/tars-accept`, `/tars-resume`, and `/tars-learn`.

### Claude Code

```sh
claude plugin marketplace add pvkarthikk/TARS
claude plugin install tars@tars
```

Invoke `/tars:tars-task`, `/tars:tars-rework`, `/tars:tars-accept`, `/tars:tars-resume`, or `/tars:tars-learn`, or launch the TARS agent directly:

```sh
claude --agent tars:tars
```

### GitHub Copilot (VS Code & Copilot CLI)

- **Copilot CLI:**
  ```sh
  copilot plugin install pvkarthikk/TARS
  ```
  Or load from a local checkout:
  ```sh
  copilot --plugin-dir ./TARS --agent tars:tars
  ```
- **VS Code:** Install via **Agent Customizations / Plugins**, select `@tars`, and invoke `/tars:tars-*` skills. `com.github.copilot/rules/tars.instructions.md` is a short pointer (not injected via `applyTo: "**"`).

### Windows Usage (PowerShell)

On Windows, all personal TARS state lives under `%USERPROFILE%\.tars\` (`$env:USERPROFILE\.tars\`):

- **Link locally for Antigravity via Directory Junction:**
  ```powershell
  New-Item -ItemType Junction -Path "$env:USERPROFILE\.gemini\config\plugins\tars" -Target "C:\path\to\TARS"
  ```
- **Run helper script & tests with the Python Launcher:**
  ```powershell
  py -3 scripts\tars.py project-id --repo . --json
  py -3 -m unittest discover -s tests -v
  ```

---

## Local Storage, URL Normalization & Decay Scoring

All runtime state is personal, machine-local, and stored strictly outside project repositories under `~/.tars/` (Linux/macOS) or `%USERPROFILE%\.tars\` (Windows):

```text
~/.tars/
├── config.yaml                   # version: 1, decay_lambda: 0.003, stale_days: 7
├── global/
│   └── learning/
│       ├── _index.md
│       └── L<NNN>_<slug>.md
└── projects/
    └── <folder-name>_<6-char-hash>/
        ├── meta.yaml             # repo_path, remote_url, active_task_id
        ├── learning/             # Personal project rules (repo instructions outrank these)
        │   ├── _index.md
        │   └── P<NNN>_<slug>.md
        ├── scratchpad/           # In-flight tasks (active | awaiting-go | paused)
        │   └── <YYYY-MM-DD>_<slug>/
        │       ├── task.md
        │       ├── plan.md       # Only created when Rework-Cost Gate triggers
        │       └── artifacts/
        └── tasks/                # Closed tasks (accepted | abandoned | blocked)
            └── <YYYY-MM-DD>_<slug>/
                ├── task.md
                └── outcome.md
```

**Normalized Project ID:** `scripts/tars.py` normalizes the `origin` remote URL before SHA-256 hashing (dropping scheme and `user@`, converting `git@host:path` to `host/path`, lowercasing host, stripping trailing `/` and `.git`), so HTTPS, `.git`, and SSH URLs resolve to the same `<folder-name>_<6-char-hash>`, warning if `meta.yaml`'s stored `repo_path` differs.

**Decay Scoring Formula:**

$$\text{score} = \left(\frac{\text{accepted\_count} + 1}{\text{applied\_count} + 2}\right) \times e^{-0.003 \times \Delta t}$$

- New rules start at `applied_count: 0`, `accepted_count: 0` (`score: 0.50`).
- `score >= 0.45`: `active` (recalled on tag match)
- `0.25 <= score < 0.45`: `probation` (loaded only on exact tag match)
- `score < 0.25` or superseded (`superseded_by:`): `deprecated` (removed from `_index.md`, retained on disk for audit)

---

## Validation

Run the test suite, helper CLI, and harness validators locally:

```sh
# 1. Unit, CLI, and structural invariant tests (Python stdlib only)
python3 -m unittest discover -s tests -v

# 2. Deterministic project ID check
python3 scripts/tars.py project-id --repo . --json

# 3. Antigravity plugin validator (note: 1 expected warning on Copilot's "agents" field)
agy plugin validate .

# 4. Copilot CLI discovery check (run where GitHub Copilot CLI is installed)
copilot --plugin-dir . --agent tars:tars
```

---

## Plugin Repository Layout

```text
TARS/
├── plugin.json
├── README.md
├── LICENSE
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── agents/
│   └── tars.md
├── assets/
│   └── logo.svg
├── com.github.copilot/
│   ├── agents/
│   │   └── tars.agent.md
│   └── rules/
│       └── tars.instructions.md
├── evals/
│   ├── tars-accept/trigger_eval.json
│   ├── tars-learn/trigger_eval.json
│   ├── tars-resume/trigger_eval.json
│   ├── tars-rework/trigger_eval.json
│   └── tars-task/trigger_eval.json
├── rules/
│   └── AGENTS.md
├── scripts/
│   └── tars.py
├── skills/
│   ├── tars-accept/SKILL.md
│   ├── tars-learn/SKILL.md
│   ├── tars-resume/SKILL.md
│   ├── tars-rework/SKILL.md
│   └── tars-task/SKILL.md
└── tests/
    └── test_tars.py
```

---

## License

Licensed under the [Apache License 2.0](LICENSE).
