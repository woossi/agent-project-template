#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".claude/hooks/update_skill_index.py"


class UpdateSkillIndexTest(unittest.TestCase):
    def make_root(self, root: Path) -> Path:
        skills_dir = root / ".claude/skills"
        skills_dir.mkdir(parents=True)
        index = skills_dir / "skills.md"
        index.write_text(
            "# Skills\n\n"
            "Reusable project skills live here.\n\n"
            "## Skill Index\n\n"
            "| Skill | Folder | Load rule |\n"
            "| --- | --- | --- |\n"
            "| stale | stale | stale |\n",
            encoding="utf-8",
        )
        sample = skills_dir / "write-task"
        sample.mkdir()
        (sample / "SKILL.md").write_text(
            "# Skill: write-task\n\nProcedure for the current task packet.\n",
            encoding="utf-8",
        )
        (skills_dir / "_draft").mkdir()
        (skills_dir / "_draft" / "SKILL.md").write_text(
            "# Skill: draft\n", encoding="utf-8"
        )
        return index

    def run_script(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        run_env = None
        if env is not None:
            run_env = {**os.environ, **env}
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
            env=run_env,
            cwd=cwd,
        )

    def test_updates_skill_index_and_check_detects_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = self.make_root(root)
            skills_dir = str(root / ".claude/skills")

            stale = self.run_script("--skills-dir", skills_dir, "--check")
            self.assertEqual(stale.returncode, 1)
            self.assertIn("skill index is stale", stale.stderr)

            result = self.run_script("--skills-dir", skills_dir)
            self.assertEqual(result.returncode, 0, result.stderr)

            text = index.read_text(encoding="utf-8")
            self.assertIn("write-task", text)
            self.assertIn("`write-task/`", text)
            self.assertNotIn("_draft", text)

            current = self.run_script("--skills-dir", skills_dir, "--check")
            self.assertEqual(current.returncode, 0, current.stderr)
            self.assertIn("skill index is current", current.stdout)

    def test_resolves_index_via_project_dir_not_cwd(self) -> None:
        """Regression: the index must be resolved from CLAUDE_PROJECT_DIR, not the
        shell cwd, which during a PostToolUse hook may be any project subdir."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_root(root)
            elsewhere = root / "subdir" / "deep"
            elsewhere.mkdir(parents=True)

            result = self.run_script(
                env={"CLAUDE_PROJECT_DIR": str(root)}, cwd=str(elsewhere)
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_index_is_non_blocking_as_hook_but_fails_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)  # no .claude/skills/skills.md created

            hook = self.run_script(env={"CLAUDE_PROJECT_DIR": str(root)}, cwd=str(root))
            self.assertEqual(hook.returncode, 0, hook.stderr)
            self.assertIn("skipping", hook.stderr)

            check = self.run_script(
                "--check", env={"CLAUDE_PROJECT_DIR": str(root)}, cwd=str(root)
            )
            self.assertEqual(check.returncode, 1)
            self.assertIn("does not exist", check.stderr)


if __name__ == "__main__":
    unittest.main()
