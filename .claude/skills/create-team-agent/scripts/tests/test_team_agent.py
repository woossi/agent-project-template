#!/usr/bin/env python3
"""Tests for create-team-agent. CI-safe: builds a fake team root in a temp dir."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = REPO_ROOT / ".claude/skills/create-team-agent/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import team_agent as ta  # noqa: E402


def build_fake_team_root(root: Path) -> None:
    """Minimal team root: shared .claude subtrees, AGENTS.md, .team/team.json."""
    claude = root / ".claude"
    for sub in ("hooks", "policies", "skills"):
        (claude / sub).mkdir(parents=True, exist_ok=True)
    (claude / "settings.json").write_text("{}", encoding="utf-8")
    (claude / "CLAUDE.md").write_text("# shared", encoding="utf-8")
    (root / "AGENTS.md").write_text("# contract", encoding="utf-8")
    team = root / ".team"
    team.mkdir(parents=True, exist_ok=True)
    (team / "team.json").write_text(json.dumps({"version": 1, "members": ["orchestrator"]}), encoding="utf-8")


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        build_fake_team_root(self.root)

    def tearDown(self):
        self._tmp.cleanup()


class CreateTests(_Case):
    def test_scaffold_structure(self):
        res = ta.create_agent(self.root, "worker-2", role="builder")
        self.assertTrue(res["created"])
        a = self.root / "agents" / "worker-2"
        # private real dirs + seeds
        self.assertTrue((a / ".claude/memory/memory.md").is_file())
        self.assertTrue((a / ".claude/memory/user_preferences.md").is_file())
        self.assertTrue((a / ".claude/tasks/tasks.md").is_file())
        self.assertTrue((a / ".context").is_dir())
        self.assertIn("worker-2", (a / ".claude/memory/memory.md").read_text(encoding="utf-8"))
        # seeded word.json is valid json with empty terms
        wj = json.loads((a / ".claude/memory/word.json").read_text(encoding="utf-8"))
        self.assertEqual(wj["terms"], [])
        # role descriptor
        self.assertIn("builder", (a / "AGENT.md").read_text(encoding="utf-8"))

    def test_symlinks_point_to_shared(self):
        ta.create_agent(self.root, "worker-2")
        a = self.root / "agents" / "worker-2"
        self.assertTrue((a / ".claude/hooks").is_symlink())
        self.assertEqual(os.readlink(a / ".claude/hooks"), "../../../.claude/hooks")
        self.assertEqual(os.readlink(a / ".claude/settings.json"), "../../../.claude/settings.json")
        self.assertEqual(os.readlink(a / "AGENTS.md"), "../../AGENTS.md")
        # symlink resolves to the real shared dir
        self.assertEqual((a / ".claude/hooks").resolve(), (self.root / ".claude/hooks").resolve())

    def test_roster_registration(self):
        res = ta.create_agent(self.root, "worker-2")
        self.assertTrue(res["roster_added"])
        members = json.loads((self.root / ".team/team.json").read_text(encoding="utf-8"))["members"]
        self.assertIn("worker-2", members)
        self.assertIn("orchestrator", members)  # preserved

    def test_idempotent_without_force(self):
        ta.create_agent(self.root, "worker-2")
        again = ta.create_agent(self.root, "worker-2")
        self.assertFalse(again["created"])
        self.assertTrue(again["exists"])

    def test_force_rewires_without_clobbering_private(self):
        ta.create_agent(self.root, "worker-2")
        a = self.root / "agents" / "worker-2"
        # user edits private memory
        (a / ".claude/memory/memory.md").write_text("# edited private", encoding="utf-8")
        # break a symlink
        (a / ".claude/hooks").unlink()
        res = ta.create_agent(self.root, "worker-2", force=True)
        self.assertTrue(res["created"])
        self.assertEqual(res["symlinks"]["hooks"], "created")
        # private edit preserved (seeds not overwritten)
        self.assertEqual((a / ".claude/memory/memory.md").read_text(encoding="utf-8"), "# edited private")

    def test_missing_team_root_claude_errors(self):
        empty = self.root / "nope"
        empty.mkdir()
        with self.assertRaises(ta.AgentError):
            ta.create_agent(empty, "x")

    def test_roster_idempotent_second_create_other_agent(self):
        ta.create_agent(self.root, "worker-2")
        ta.create_agent(self.root, "worker-3")
        members = json.loads((self.root / ".team/team.json").read_text(encoding="utf-8"))["members"]
        self.assertEqual(members, ["orchestrator", "worker-2", "worker-3"])


class ListTests(_Case):
    def test_list_reports_drift(self):
        ta.create_agent(self.root, "worker-2")
        # roster has an extra member with no folder
        tf = self.root / ".team/team.json"
        data = json.loads(tf.read_text(encoding="utf-8"))
        data["members"].append("ghost")
        tf.write_text(json.dumps(data), encoding="utf-8")
        out = ta.list_agents(self.root)
        self.assertIn("worker-2", out["agent_folders"])
        self.assertIn("ghost", out["out_of_sync"])  # in roster, no folder


class CliTests(_Case):
    def test_cli_create_and_list(self):
        rc = ta.main(["--team-root", str(self.root), "create", "worker-2", "--role", "builder"])
        self.assertEqual(rc, 0)
        rc2 = ta.main(["--team-root", str(self.root), "list"])
        self.assertEqual(rc2, 0)


if __name__ == "__main__":
    unittest.main()
