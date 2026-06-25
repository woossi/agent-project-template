#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".claude/hooks/update_agent_index.py"


class UpdateAgentIndexTest(unittest.TestCase):
    def make_root(self, root: Path) -> Path:
        agents_dir = root / ".claude/agents"
        agents_dir.mkdir(parents=True)
        index = agents_dir / "agents.md"
        index.write_text(
            "# Agent Index\n\n"
            "Project-scoped Claude subagents live in this directory.\n\n"
            "## Files\n\n"
            "| Path | Role |\n"
            "| --- | --- |\n"
            "| stale | stale |\n\n"
            "## Maintenance\n\n"
            "- Keep one subagent per Markdown file.\n",
            encoding="utf-8",
        )
        (agents_dir / "reviewer.md").write_text(
            "---\n"
            "name: reviewer\n"
            "description: Use when reviewing scoped changes.\n"
            "tools: Read\n"
            "---\n\n"
            "# Role\n"
            "Review scoped changes.\n",
            encoding="utf-8",
        )
        (agents_dir / "_draft.md").write_text(
            "---\nname: draft\ndescription: Ignore draft.\n---\n",
            encoding="utf-8",
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

    def test_updates_agent_index_and_check_detects_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = self.make_root(root)

            stale = self.run_script("--agents-dir", str(root / ".claude/agents"), "--check")
            self.assertEqual(stale.returncode, 1)
            self.assertIn("agent index is stale", stale.stderr)

            result = self.run_script("--agents-dir", str(root / ".claude/agents"))
            self.assertEqual(result.returncode, 0, result.stderr)

            text = index.read_text(encoding="utf-8")
            self.assertIn("`.claude/agents/reviewer.md`", text)
            self.assertIn("Use when reviewing scoped changes.", text)
            self.assertNotIn("_draft", text)
            self.assertIn("## Maintenance", text)

            current = self.run_script("--agents-dir", str(root / ".claude/agents"), "--check")
            self.assertEqual(current.returncode, 0, current.stderr)
            self.assertIn("agent index is current", current.stdout)

    def test_resolves_index_via_project_dir_not_cwd(self) -> None:
        """Regression: a PostToolUse hook runs with the shell cwd at any project
        subdirectory, so the index must be resolved from CLAUDE_PROJECT_DIR, not
        Path.cwd(). Run with no --agents-dir and cwd pointed elsewhere."""
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
        """As a hook (no --check) a missing index must exit 0 so it never blocks
        an unrelated tool call; under --check it is a contract failure."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)  # no .claude/agents/agents.md created

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
