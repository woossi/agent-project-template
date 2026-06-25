#!/usr/bin/env python3
"""Tests for team-init (team-setup.json -> .team definition). CI-safe."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = REPO_ROOT / ".claude/skills/team-init/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import team_init as ti  # noqa: E402


def setup(**over):
    base = {"team": "research-umc", "members": ["orchestrator", "worker-1"], "reminders_list": "umc"}
    base.update(over)
    return base


class NormalizeTests(unittest.TestCase):
    def test_defaults_owner_to_first_member(self):
        s = ti.normalize_setup(setup())
        self.assertEqual(s["authoring_owner"], "orchestrator")
        self.assertEqual(s["min_distinct_agents"], 2)

    def test_missing_team_rejected(self):
        with self.assertRaises(ti.TeamInitError):
            ti.normalize_setup(setup(team=""))

    def test_missing_members_rejected(self):
        with self.assertRaises(ti.TeamInitError):
            ti.normalize_setup({"team": "t", "members": []})

    def test_owner_must_be_member(self):
        with self.assertRaises(ti.TeamInitError):
            ti.normalize_setup(setup(authoring_owner="ghost"))

    def test_bad_min_distinct_agents_rejected(self):
        with self.assertRaises(ti.TeamInitError):
            ti.normalize_setup(setup(min_distinct_agents="two"))

    def test_optional_reminders_list_none(self):
        s = ti.normalize_setup({"team": "t", "members": ["a"]})
        self.assertIsNone(s["reminders_list"])


class BuildTests(unittest.TestCase):
    def test_team_json(self):
        tj = ti.build_team_json(ti.normalize_setup(setup(roles={"orchestrator": "lead"})))
        self.assertEqual(tj["team"], "research-umc")
        self.assertEqual(tj["reminders_list"], "umc")
        self.assertEqual(tj["members"], ["orchestrator", "worker-1"])
        self.assertEqual(tj["roles"]["orchestrator"], "lead")
        self.assertEqual(tj["goals_dir"], ".team/goals")

    def test_min_distinct_agents_propagates(self):
        s = ti.normalize_setup(setup(min_distinct_agents=3))
        prom = ti.build_promotion_policy(s)
        der = ti.build_derivation_policy(s)
        self.assertEqual(prom["team_skill_promotion"]["min_distinct_agents"], 3)
        self.assertEqual(prom["team_agent_promotion"]["min_distinct_agents"], 3)
        self.assertEqual(der["term_derivation"]["min_distinct_agents"], 3)
        self.assertEqual(der["memory_derivation"]["min_distinct_agents"], 3)

    def test_owner_propagates_to_governance(self):
        s = ti.normalize_setup(setup(authoring_owner="worker-1"))
        self.assertEqual(ti.build_promotion_policy(s)["governance"]["authoring_owner"], "worker-1")
        self.assertEqual(ti.build_derivation_policy(s)["governance"]["authoring_owner"], "worker-1")


class InitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_init_writes_definition_and_dirs(self):
        res = ti.init_team(self.root, ti.normalize_setup(setup()))
        self.assertEqual(res["agents_created"], [])
        self.assertTrue((self.root / ".team/team.json").exists())
        self.assertTrue((self.root / ".team/policies/team-promotion.json").exists())
        self.assertTrue((self.root / ".team/policies/team-derivation.json").exists())
        self.assertTrue((self.root / ".team/goals/.gitkeep").exists())
        self.assertTrue((self.root / ".team/inbox/.gitkeep").exists())
        # written team.json is valid and bound
        tj = json.loads((self.root / ".team/team.json").read_text(encoding="utf-8"))
        self.assertEqual(tj["reminders_list"], "umc")

    def test_policies_are_valid_for_hooks(self):
        ti.init_team(self.root, ti.normalize_setup(setup(min_distinct_agents=2)))
        prom = json.loads((self.root / ".team/policies/team-promotion.json").read_text(encoding="utf-8"))
        # shape the detector relies on
        self.assertIn("team_skill_promotion", prom)
        self.assertIn("decisions_dir", prom["log"])

    def test_create_agents_via_injected_creator(self):
        orig = ti._create_members
        ti._create_members = lambda root, s: [{"name": m, "created": True} for m in s["members"]]
        try:
            res = ti.init_team(self.root, ti.normalize_setup(setup()), create_agents=True)
        finally:
            ti._create_members = orig
        self.assertEqual(res["agents_created"], ["orchestrator", "worker-1"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_cli_init_from_file_saves_input(self):
        inp = self.root / "in.json"
        inp.write_text(json.dumps(setup()), encoding="utf-8")
        rc = ti.main(["init", "--input", str(inp), "--team-root", str(self.root)])
        self.assertEqual(rc, 0)
        self.assertTrue((self.root / ".team/team.json").exists())
        self.assertTrue((self.root / "team-setup.json").exists())  # saved back

    def test_cli_no_save_input(self):
        inp = self.root / "in.json"
        inp.write_text(json.dumps(setup()), encoding="utf-8")
        rc = ti.main(["init", "--input", str(inp), "--team-root", str(self.root), "--no-save-input"])
        self.assertEqual(rc, 0)
        self.assertFalse((self.root / "team-setup.json").exists())

    def test_cli_invalid_returns_1(self):
        inp = self.root / "bad.json"
        inp.write_text(json.dumps({"team": "t"}), encoding="utf-8")  # no members
        rc = ti.main(["init", "--input", str(inp), "--team-root", str(self.root)])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
