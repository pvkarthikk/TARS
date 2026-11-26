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

- **Optimistic Execution:** Routine, low-blast-radius tasks bypass upfront planning and go straight to working code, reporting changes plus 1–3 key assumptions at the end.
- **Objective Rework-Cost Gate:** Replaces subjective planning guesses with 4 objective triggers (`> 3` files touched, critical surfaces, `> 50` deleted lines or dependency changes, or non-git-revertible actions).
- **Parallel Scratchpad Tasks:** Park active tasks, switch context with `/tars-resume`, and automatically sweep & archive cleanly committed paused tasks.
- **Decaying Local-First Markdown Memory:** Stores atomic global (`L*`) and project-local (`P*`) rules with Bayesian-smoothed success scoring and exponential time decay (`e^(-0.003 * delta_t)`).
- **Zero Repo Pollution:** Never creates `.tars`, scratchpads, or memory artifacts inside your project repository. All state stays under `~/.tars/` (`%USERPROFILE%\.tars\` on Windows).

---

## Supported Harnesses

| Harness | Manifest | Agent / Always-On Rules | Skills |
| :--- | :--- | :--- | :--- |
| **Antigravity** (CLI, App, IDE) | `plugin.json` | `rules/AGENTS.md` + `agents/tars.md` | `skills/tars-*/SKILL.md` |
| **GitHub Copilot** (VS Code & CLI) | `plugin.json` (`$schema` Agent Plugins 1.0) | `com.github.copilot/agents/tars.agent.md` + `com.github.copilot/rules/tars.instructions.md` | `skills/tars-*/SKILL.md` |
| **Claude Code** | `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` | `agents/tars.md` | `skills/tars-*/SKILL.md` |

---

## Commands & Skills

All harnesses share the same 5 canonical skills under `skills/` (invoked with your harness prefix such as `/tars-task` or `/tars:tars-task`, or shorthand `/task` when the `tars` agent or rules are active):

| Skill / Command | Shorthand | Description |
| :--- | :--- | :--- |
| `tars-task <description>` | `/task <description>` | Run implicit-accept sweep, park active task, recall matching learnings, evaluate the rework-cost gate, and execute or propose a concise plan. |
| `tars-rework <correction>` | `/rework <correction>` | Auto-detected on corrective follow-ups while a task is active. Patches code, increments `rework_count`, isolates blame on contradicted rules, and captures new learnings. |
| `tars-accept` | `/accept` | Rewards non-contradicted `applied_learnings`, writes `outcome.md`, archives the task to `tasks/`, and clears `active_task_id`. |
| `tars-resume [task-slug]` | `/resume [task-slug]` | Lists `paused` scratchpad tasks (or switches back to the specified slug) and restores context. |
| `tars-learn <rule>` | `/learn <rule>` | Classifies global vs. project-local scope, deduplicates or supersedes existing rules, recalculates decay scores, and rebuilds `_index.md`. |

---

## Installation & Usage

### Antigravity

- **CLI:**
  ```sh
  agy plugin install https://github.com/pvkarthikk/TARS
  ```
- **App / IDE (manual symlink or clone):**
  ```sh
  ln -s /path/to/TARS ~/.gemini/config/plugins/tars
  ```
Rules in `rules/AGENTS.md` apply automatically; invoke `/tars-task`, `/tars-rework`, `/tars-accept`, `/tars-resume`, and `/tars-learn`.

### Claude Code

```sh
claude plugin marketplace add pvkarthikk/TARS
claude plugin install tars@tars
```

Invoke `/tars:tars-task`, `/tars:tars-rework`, `/tars:tars-accept`, `/tars:tars-resume`, or `/tars:tars-learn`, or launch the TARS agent directly with:

```sh
claude --agent tars:tars
```

### GitHub Copilot (VS Code & Copilot CLI)

- **Copilot CLI:**
  ```sh
  copilot plugin install pvkarthikk/TARS
  ```
  Or test directly from a local checkout:
  ```sh
  copilot --plugin-dir ./TARS --agent tars:tars
  ```
- **VS Code:** Install via the **Agent Customizations / Plugins** view (Agent Plugins 1.0 format). `com.github.copilot/rules/tars.instructions.md` applies automatically, or select the `@tars` agent and invoke `/tars:tars-*` skills.

---

## Local Storage & Decay Scoring

All runtime state is stored strictly outside project repositories under `~/.tars/` (Linux/macOS) or `%USERPROFILE%\.tars\` (Windows):

```text
~/.tars/
├── config.yaml
├── global/
│   └── learning/
│       ├── _index.md
│       └── L<NNN>_<slug>.md
└── projects/
    └── <folder-name>_<6-char-hash>/
        ├── meta.yaml             # repo_path, remote_url, active_task_id
        ├── learning/             # Project-local rules (override global on conflict)
        │   ├── _index.md
        │   └── P<NNN>_<slug>.md
        ├── scratchpad/           # In-flight tasks (active | paused)
        │   └── <YYYY-MM-DD>_<slug>/
        │       ├── task.md
        │       ├── plan.md       # Only created if Rework-Cost Gate triggers
        │       └── artifacts/
        └── tasks/                # Archived, accepted tasks
            └── <YYYY-MM-DD>_<slug>/
                ├── task.md
                └── outcome.md
```

**Decay Scoring Formula:**

$$\text{score} = \left(\frac{\text{accepted\_count} + 1}{\text{applied\_count} + 2}\right) \times e^{-0.003 \times \Delta t}$$

- `score >= 0.45`: `active` (recalled on tag match)
- `0.25 <= score < 0.45`: `probation` (loaded only on exact tag match)
- `score < 0.25` or superseded: `deprecated` (removed from `_index.md`, retained on disk for audit)

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
├── rules/
│   └── AGENTS.md
└── skills/
    ├── tars-accept/SKILL.md
    ├── tars-learn/SKILL.md
    ├── tars-resume/SKILL.md
    ├── tars-rework/SKILL.md
    └── tars-task/SKILL.md
```

---

## License

Licensed under the [Apache License 2.0](LICENSE).
