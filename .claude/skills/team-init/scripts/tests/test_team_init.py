#!/usr/bin/env python3
"""Tests for team-init (team-setup.json -> .project definition). CI-safe."""

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
        self.assertEqual(tj["goals_dir"], ".project/goals")

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

    def test_workspace_policy_sibling_deny_from_roster(self):
        s = ti.normalize_setup(setup(members=["data-curator", "paper-scout"]))
        pol = ti.build_agent_workspace_policy(s)
        self.assertEqual(pol["agents"]["data-curator"]["deny"], ["agents/paper-scout/**"])
        self.assertEqual(pol["agents"]["paper-scout"]["deny"], ["agents/data-curator/**"])
        self.assertEqual(sorted(pol["agents"]), ["data-curator", "paper-scout"])

    def test_workspace_policy_preserves_existing_defaults(self):
        s = ti.normalize_setup(setup(members=["a", "b"]))
        existing = {"version": 1, "defaults": {"allow": [".", "/abs/umc/**"], "deny": [], "bash": {}}, "agents": {}}
        pol = ti.build_agent_workspace_policy(s, existing)
        self.assertIn("/abs/umc/**", pol["defaults"]["allow"])  # work boundary kept
        self.assertEqual(sorted(pol["agents"]), ["a", "b"])  # agents map regenerated


class InitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_init_writes_definition_and_dirs(self):
        res = ti.init_team(self.root, ti.normalize_setup(setup()))
        self.assertEqual(res["agents_created"], [])
        self.assertTrue((self.root / ".project/team.json").exists())
        self.assertTrue((self.root / ".project/policies/team-promotion.json").exists())
        self.assertTrue((self.root / ".project/policies/team-derivation.json").exists())
        self.assertTrue((self.root / ".project/goals/.gitkeep").exists())
        self.assertTrue((self.root / ".project/inbox/.gitkeep").exists())
        # the guard's sibling-isolation policy is regenerated too (no manual drift)
        self.assertTrue((self.root / ".claude/policies/agent-workspace.json").exists())
        # written team.json is valid and bound
        tj = json.loads((self.root / ".project/team.json").read_text(encoding="utf-8"))
        self.assertEqual(tj["reminders_list"], "umc")

    def test_init_regenerates_workspace_policy_preserving_boundaries(self):
        # an existing policy carries project work boundaries that are NOT in team-setup
        wp = self.root / ".claude/policies/agent-workspace.json"
        wp.parent.mkdir(parents=True, exist_ok=True)
        wp.write_text(json.dumps({
            "version": 1,
            "defaults": {"allow": [".", "/Users/x/project/umc/**"], "deny": [], "bash": {"allow": [], "deny": []}},
            "agents": {"orchestrator": {"deny": ["agents/worker-1/**"]}},  # stale names
        }), encoding="utf-8")
        ti.init_team(self.root, ti.normalize_setup(setup(members=["data-curator", "paper-scout"])))
        pol = json.loads(wp.read_text(encoding="utf-8"))
        self.assertEqual(sorted(pol["agents"]), ["data-curator", "paper-scout"])  # stale keys gone
        self.assertIn("/Users/x/project/umc/**", pol["defaults"]["allow"])  # boundary preserved

    def test_policies_are_valid_for_hooks(self):
        ti.init_team(self.root, ti.normalize_setup(setup(min_distinct_agents=2)))
        prom = json.loads((self.root / ".project/policies/team-promotion.json").read_text(encoding="utf-8"))
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


class SubteamNormalizeTests(unittest.TestCase):
    def _members(self):
        return ["data-curator", "data-engineer", "paper-scout"]

    def test_absent_subteams_stays_flat(self):
        s = ti.normalize_setup(setup())
        self.assertEqual(s["subteams"], [])

    def test_subteam_members_must_be_in_roster(self):
        with self.assertRaises(ti.TeamInitError):
            ti.normalize_subteams({"subteams": [{"name": "data", "members": ["ghost"]}]}, self._members())

    def test_worker_in_two_subteams_rejected(self):
        with self.assertRaises(ti.TeamInitError):
            ti.normalize_subteams({"subteams": [
                {"name": "a", "members": ["data-curator"]},
                {"name": "b", "members": ["data-curator"]},
            ]}, self._members())

    def test_duplicate_subteam_name_rejected(self):
        with self.assertRaises(ti.TeamInitError):
            ti.normalize_subteams({"subteams": [
                {"name": "data", "members": ["data-curator"]},
                {"name": "data", "members": ["data-engineer"]},
            ]}, self._members())

    def test_orchestrator_defaults_to_first_member(self):
        subs = ti.normalize_subteams({"subteams": [{"name": "data", "members": ["data-curator", "data-engineer"]}]}, self._members())
        self.assertEqual(subs[0]["orchestrator"], "data-curator")

    def test_orchestrator_must_be_subteam_member(self):
        with self.assertRaises(ti.TeamInitError):
            ti.normalize_subteams({"subteams": [
                {"name": "data", "members": ["data-curator"], "orchestrator": "paper-scout"},
            ]}, self._members())

    def test_subteams_propagate_to_team_json_only_when_present(self):
        flat = ti.build_team_json(ti.normalize_setup(setup()))
        self.assertNotIn("subteams", flat)  # flat team.json unchanged
        nested = ti.build_team_json(ti.normalize_setup(setup(
            members=["data-curator", "data-engineer"],
            subteams=[{"name": "data", "members": ["data-curator", "data-engineer"], "reminders_list": "umc-data"}],
        )))
        self.assertEqual(nested["subteams"][0]["name"], "data")
        self.assertEqual(nested["subteams"][0]["reminders_list"], "umc-data")


class AddSubteamTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # seed an existing flat team
        ti.main(["init", "--input", str(self._write_in(setup(members=["data-curator", "data-engineer"]))),
                 "--team-root", str(self.root)])

    def tearDown(self):
        self._tmp.cleanup()

    def _write_in(self, payload):
        p = self.root / "in.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    def test_add_subteam_appends_and_grows_roster(self):
        entry = self.root / "sub.json"
        entry.write_text(json.dumps({
            "name": "write", "members": ["manuscript-writer", "data-curator"], "reminders_list": "umc-write",
            "orchestrator": "manuscript-writer",
        }), encoding="utf-8")
        rc = ti.main(["add-subteam", "--input", str(entry), "--team-root", str(self.root)])
        self.assertEqual(rc, 0)
        # roster grew with the brand-new worker
        saved = json.loads((self.root / "team-setup.json").read_text(encoding="utf-8"))
        self.assertIn("manuscript-writer", saved["members"])
        self.assertEqual(saved["subteams"][0]["name"], "write")
        # team.json reflects it and the isolation policy regenerated for the new worker
        tj = json.loads((self.root / ".project/team.json").read_text(encoding="utf-8"))
        self.assertEqual(tj["subteams"][0]["name"], "write")
        pol = json.loads((self.root / ".claude/policies/agent-workspace.json").read_text(encoding="utf-8"))
        self.assertIn("manuscript-writer", pol["agents"])

    def test_add_duplicate_subteam_rejected(self):
        entry = self.root / "sub.json"
        payload = {"name": "data", "members": ["data-curator", "data-engineer"]}
        entry.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(ti.main(["add-subteam", "--input", str(entry), "--team-root", str(self.root)]), 0)
        # second time with same name fails
        self.assertEqual(ti.main(["add-subteam", "--input", str(entry), "--team-root", str(self.root)]), 1)

    def test_add_subteam_without_init_fails(self):
        empty = Path(self._tmp.name) / "fresh"
        empty.mkdir()
        entry = empty / "sub.json"
        entry.write_text(json.dumps({"name": "data", "members": ["x"]}), encoding="utf-8")
        self.assertEqual(ti.main(["add-subteam", "--input", str(entry), "--team-root", str(empty)]), 1)


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
        self.assertTrue((self.root / ".project/team.json").exists())
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
