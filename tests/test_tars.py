"""Unit, CLI, and structural invariant tests for the TARS plugin."""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import tars  # noqa: E402


class UrlNormalizationAndProjectIdTests(unittest.TestCase):
    def test_remote_variants_normalize_identically(self) -> None:
        variants = [
            "https://github.com/pvkarthikk/TARS",
            "https://github.com/pvkarthikk/TARS.git",
            "https://github.com/pvkarthikk/TARS/",
            "https://user@GitHub.com/pvkarthikk/TARS.git/",
            "https://user:token@github.com/pvkarthikk/TARS.git",
            "git@github.com:pvkarthikk/TARS.git",
            "git@GitHub.com:pvkarthikk/TARS",
            "ssh://git@GitHub.com/pvkarthikk/TARS.git",
            "ssh://git@GitHub.com:22/pvkarthikk/TARS.git/",
        ]
        normalized = {tars.normalize_remote_url(v) for v in variants}
        self.assertEqual(normalized, {"github.com/pvkarthikk/TARS"})

    def test_path_case_is_preserved_while_host_is_lowercased(self) -> None:
        self.assertEqual(
            tars.normalize_remote_url("HTTPS://GitHub.COM/OrgName/MyRepo.git"),
            "github.com/OrgName/MyRepo",
        )

    def test_compute_project_id_matches_across_remote_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "tars"
            repo.mkdir()
            id_https = tars.compute_project_id(
                repo, remote_url="https://github.com/pvkarthikk/TARS"
            )
            id_git = tars.compute_project_id(
                repo, remote_url="https://github.com/pvkarthikk/TARS.git/"
            )
            id_ssh = tars.compute_project_id(
                repo, remote_url="git@github.com:pvkarthikk/TARS.git"
            )
            self.assertEqual(id_https["project_id"], id_git["project_id"])
            self.assertEqual(id_https["project_id"], id_ssh["project_id"])
            self.assertRegex(id_https["project_id"], r"^tars_[0-9a-f]{6}$")

    def test_compute_project_id_falls_back_to_canonical_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "local-proj"
            repo.mkdir()
            res = tars.compute_project_id(repo, remote_url="")
            self.assertEqual(res["normalized_remote"], "")
            self.assertEqual(res["hash_input"], str(repo.resolve()).replace("\\", "/"))
            self.assertRegex(res["project_id"], r"^local-proj_[0-9a-f]{6}$")

    def test_resolve_project_warns_on_repo_path_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tars_root = tmp_path / ".tars"
            repo = tmp_path / "tars"
            repo.mkdir()
            info = tars.compute_project_id(
                repo, remote_url="https://github.com/pvkarthikk/TARS.git"
            )
            proj_dir = tars_root / "projects" / info["project_id"]
            proj_dir.mkdir(parents=True)
            (proj_dir / "meta.yaml").write_text(
                "repo_path: /some/other/checkout\nactive_task_id: null\n",
                encoding="utf-8",
            )
            resolved = tars.resolve_project(
                repo,
                remote_url="https://github.com/pvkarthikk/TARS.git",
                tars_root=tars_root,
            )
            self.assertIn("differs from current repo_root", resolved["warning"])


class ScoringAndStatusTests(unittest.TestCase):
    def test_new_rule_starts_at_half(self) -> None:
        res = tars.compute_score(0, 0, "2026-11-26", today="2026-11-26")
        self.assertEqual(res["score"], 0.50)
        self.assertEqual(res["status"], "active")

    def test_accepted_once_rule_score(self) -> None:
        res = tars.compute_score(1, 1, "2026-11-26", today="2026-11-26")
        self.assertEqual(res["score"], 0.67)
        self.assertEqual(res["status"], "active")

    def test_rework_penalty_score(self) -> None:
        # 2 applied, 0 accepted -> (0+1)/(2+2) = 0.25 -> probation
        res = tars.compute_score(2, 0, "2026-11-26", today="2026-11-26")
        self.assertEqual(res["score"], 0.25)
        self.assertEqual(res["status"], "probation")

        # 3 applied, 0 accepted -> 1/5 = 0.20 -> deprecated
        dep = tars.compute_score(3, 0, "2026-11-26", today="2026-11-26")
        self.assertEqual(dep["score"], 0.20)
        self.assertEqual(dep["status"], "deprecated")

    def test_threshold_boundaries_with_decay(self) -> None:
        # Base 0.50 decays below 0.45 once exp(-0.003 * dt) < 0.90 (~36 days)
        dt_active = math.floor(-math.log(0.45 / 0.50) / 0.003)  # 35 days -> ~0.4501
        res_active = tars.compute_score(0, 0, "2026-10-22", today="2026-11-26")
        self.assertEqual(res_active["delta_t"], dt_active)
        self.assertEqual(res_active["score"], 0.45)
        self.assertEqual(res_active["status"], "active")

        # 40 days -> 0.50 * exp(-0.12) = 0.44 -> probation
        res_prob = tars.compute_score(0, 0, "2026-10-17", today="2026-11-26")
        self.assertEqual(res_prob["score"], 0.44)
        self.assertEqual(res_prob["status"], "probation")

        # 231 days -> 0.50 * exp(-0.693) = 0.25 -> probation; 245 days -> 0.24 -> deprecated
        res_edge_prob = tars.compute_score(0, 0, "2026-04-09", today="2026-11-26")
        self.assertEqual(res_edge_prob["score"], 0.25)
        self.assertEqual(res_edge_prob["status"], "probation")

        res_dep = tars.compute_score(0, 0, "2026-03-26", today="2026-11-26")
        self.assertEqual(res_dep["score"], 0.24)
        self.assertEqual(res_dep["status"], "deprecated")

    def test_superseded_stays_deprecated(self) -> None:
        res = tars.compute_score(5, 5, "2026-11-26", today="2026-11-26", superseded=True)
        self.assertEqual(res["score"], 0.86)
        self.assertEqual(res["status"], "deprecated")


class IndexAndScratchpadTests(unittest.TestCase):
    def _write_rule(
        self,
        directory: Path,
        filename: str,
        rule_id: str,
        tags: list[str],
        applied: int,
        accepted: int,
        last_used: str,
        title: str,
        status: str = "active",
        extra: str = "",
    ) -> Path:
        score = tars.compute_score(applied, accepted, last_used, today=last_used)["score"]
        content = (
            f"---\n"
            f"id: {rule_id}\n"
            f"scope: project\n"
            f"tags: [{', '.join(tags)}]\n"
            f"status: {status}\n"
            f"created: {last_used}\n"
            f"last_used: {last_used}\n"
            f"applied_count: {applied}\n"
            f"accepted_count: {accepted}\n"
            f"rework_count: 0\n"
            f"score: {score:.2f}\n"
            f"{extra}"
            f"---\n"
            f"# {title}\n"
            f"Rule body text.\n"
        )
        path = directory / filename
        path.write_text(content, encoding="utf-8")
        return path

    def test_next_learning_id_skips_deprecated_and_starts_at_001(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ldir = Path(tmp) / "learning"
            self.assertEqual(tars.next_learning_id(ldir, "P"), "P001")
            ldir.mkdir()
            self._write_rule(
                ldir,
                "P001_old.md",
                "P001",
                ["python"],
                0,
                0,
                "2026-01-01",
                "Old rule",
                status="deprecated",
            )
            self._write_rule(
                ldir,
                "P003_newer.md",
                "P003",
                ["python"],
                1,
                1,
                "2026-11-26",
                "Newer rule",
            )
            self.assertEqual(tars.next_learning_id(ldir, "P"), "P004")

    def test_rebuild_index_sorts_refreshes_and_omits_deprecated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ldir = Path(tmp) / "learning"
            ldir.mkdir()
            self._write_rule(
                ldir, "P001_alpha.md", "P001", ["python"], 0, 0, "2026-10-17", "Alpha rule"
            )  # 40d -> 0.44 probation
            self._write_rule(
                ldir, "P002_beta.md", "P002", ["git"], 2, 2, "2026-11-26", "Beta rule"
            )  # 0.75 active
            sup = self._write_rule(
                ldir,
                "P003_superseded.md",
                "P003",
                ["git"],
                3,
                3,
                "2026-11-26",
                "Superseded rule",
                status="deprecated",
                extra="superseded_by: P002\n",
            )
            res = tars.rebuild_index(ldir, today="2026-11-26", write=True)
            self.assertEqual([e["id"] for e in res["entries"]], ["P002", "P001"])
            self.assertIn("P001_alpha.md", res["updated_files"])

            idx_text = (ldir / "_index.md").read_text(encoding="utf-8")
            self.assertIn("P002 | 0.75 | [git] | Beta rule", idx_text)
            self.assertIn("P001 | 0.44 | [python] | Alpha rule", idx_text)
            self.assertNotIn("P003", idx_text)
            # Superseded file stays on disk and remains deprecated
            fm_sup, _ = tars.parse_frontmatter(sup.read_text(encoding="utf-8"))
            self.assertEqual(fm_sup["status"], "deprecated")
            self.assertEqual(fm_sup["superseded_by"], "P002")

    def test_inspect_scratchpad_auto_pauses_and_flags_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "tars_000000"
            sp = proj / "scratchpad"
            (sp / "2026-11-10_old-active").mkdir(parents=True)
            (sp / "2026-11-15_old-paused").mkdir(parents=True)
            (sp / "2026-11-25_fresh-paused").mkdir(parents=True)

            (proj / "meta.yaml").write_text(
                "repo_path: /tmp/repo\nactive_task_id: 2026-11-10_old-active\n",
                encoding="utf-8",
            )
            (sp / "2026-11-10_old-active" / "task.md").write_text(
                "---\nid: 2026-11-10_old-active\nstatus: active\ncreated: 2026-11-10\nupdated: 2026-11-10\nrework_count: 0\ntouched_files: []\n---\n# Old active\n",
                encoding="utf-8",
            )
            (sp / "2026-11-15_old-paused" / "task.md").write_text(
                "---\nid: 2026-11-15_old-paused\nstatus: paused\ncreated: 2026-11-15\nupdated: 2026-11-15\nrework_count: 1\ntouched_files: [a.py]\n---\n# Old paused\n",
                encoding="utf-8",
            )
            (sp / "2026-11-25_fresh-paused" / "task.md").write_text(
                "---\nid: 2026-11-25_fresh-paused\nstatus: paused\ncreated: 2026-11-25\nupdated: 2026-11-25\nrework_count: 0\ntouched_files: []\n---\n# Fresh paused\n",
                encoding="utf-8",
            )

            res = tars.inspect_scratchpad(
                proj, stale_days=7, pause_stale=True, today="2026-11-26"
            )
            self.assertEqual(res["auto_paused"], ["2026-11-10_old-active"])
            self.assertIsNone(res["active_task_id"])
            self.assertIn("2026-11-10_old-active", res["stale_paused"])
            self.assertIn("2026-11-15_old-paused", res["stale_paused"])
            self.assertNotIn("2026-11-25_fresh-paused", res["stale_paused"])
            self.assertIn("active_task_id: null", (proj / "meta.yaml").read_text(encoding="utf-8"))


class CliTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "tars.py"), *args],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_cli_score_and_project_id(self) -> None:
        score_proc = self._run_cli(
            "score", "--applied", "0", "--accepted", "0", "--last-used", "2026-11-26", "--today", "2026-11-26", "--json"
        )
        score_data = json.loads(score_proc.stdout)
        self.assertEqual(score_data["score"], 0.50)
        self.assertEqual(score_data["status"], "active")

        proj_proc = self._run_cli(
            "project-id", "--repo", str(REPO_ROOT), "--remote", "git@github.com:pvkarthikk/TARS.git", "--json"
        )
        proj_data = json.loads(proj_proc.stdout)
        self.assertEqual(proj_data["normalized_remote"], "github.com/pvkarthikk/TARS")
        self.assertRegex(proj_data["project_id"], r"^tars_[0-9a-f]{6}$")


class PluginStructuralInvariantTests(unittest.TestCase):
    def test_manifests_are_valid_and_consistent(self) -> None:
        root_m = json.loads((REPO_ROOT / "plugin.json").read_text(encoding="utf-8"))
        claude_m = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        mp_m = json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual(root_m["name"], "tars")
        self.assertEqual(claude_m["name"], "tars")
        self.assertEqual(mp_m["plugins"][0]["name"], "tars")
        self.assertEqual(root_m["version"], claude_m["version"])
        self.assertEqual(root_m["agents"], "com.github.copilot/agents/")
        self.assertEqual(root_m["skills"], "skills/")

    def test_single_canonical_rules_and_short_pointers(self) -> None:
        rules_text = (REPO_ROOT / "rules" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertFalse(rules_text.startswith("---"))
        self.assertLess(len(rules_text.encode("utf-8")), 24000)

        instr = (REPO_ROOT / "com.github.copilot" / "rules" / "tars.instructions.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("applyTo:", instr)
        self.assertLessEqual(len(instr.splitlines()), 15)

        for rel in ("agents/tars.md", "com.github.copilot/agents/tars.agent.md"):
            txt = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertLessEqual(len(txt.splitlines()), 30)
            self.assertIn("rules/AGENTS.md", txt)
            self.assertIn("scripts/tars.py", txt)

    def test_no_legacy_short_commands_in_skills_or_pointers(self) -> None:
        short_cmd_re = re.compile(r"(?<![a-z0-9-/])/(?:task|rework|accept|resume|learn)(?![a-z0-9.-])")
        targets = [
            REPO_ROOT / "agents" / "tars.md",
            REPO_ROOT / "com.github.copilot" / "agents" / "tars.agent.md",
            REPO_ROOT / "com.github.copilot" / "rules" / "tars.instructions.md",
            REPO_ROOT / "rules" / "AGENTS.md",
            *(REPO_ROOT / "skills").glob("tars-*/SKILL.md"),
        ]
        for path in targets:
            txt = path.read_text(encoding="utf-8")
            matches = short_cmd_re.findall(txt)
            self.assertEqual(matches, [], f"Legacy short command found in {path}: {matches}")

    def test_eval_suites_exist_and_have_positive_and_negative_cases(self) -> None:
        skills = ["tars-task", "tars-rework", "tars-accept", "tars-resume", "tars-learn"]
        for skill in skills:
            eval_path = REPO_ROOT / "evals" / skill / "trigger_eval.json"
            self.assertTrue(eval_path.is_file(), f"Missing {eval_path}")
            data = json.loads(eval_path.read_text(encoding="utf-8"))
            self.assertEqual(data["skill"], skill)
            cases = data["cases"]
            self.assertTrue(any(c["should_trigger"] is True for c in cases))
            self.assertTrue(any(c["should_trigger"] is False for c in cases))


if __name__ == "__main__":
    unittest.main()
