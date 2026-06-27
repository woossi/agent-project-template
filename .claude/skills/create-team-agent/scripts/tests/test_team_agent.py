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
    """Minimal team root: shared .claude subtrees, AGENTS.md, .project/team.json."""
    claude = root / ".claude"
    for sub in ("hooks", "policies", "skills"):
        (claude / sub).mkdir(parents=True, exist_ok=True)
    # two shared skills so per-skill wiring has something to link
    for sk in ("write-task", "team-inbox"):
        (claude / "skills" / sk).mkdir(parents=True, exist_ok=True)
        (claude / "skills" / sk / "SKILL.md").write_text(f"# 스킬: {sk}", encoding="utf-8")
    (claude / "skills" / "skills.md").write_text("# index", encoding="utf-8")  # generated file, not a skill
    (claude / "settings.json").write_text("{}", encoding="utf-8")
    (claude / "CLAUDE.md").write_text("# shared", encoding="utf-8")
    (root / "AGENTS.md").write_text("# contract", encoding="utf-8")
    team = root / ".project"
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

    def test_skills_wired_per_skill_not_whole_dir(self):
        ta.create_agent(self.root, "worker-2")
        skills = self.root / "agents/worker-2/.claude/skills"
        # the skills dir itself is REAL (not a whole-dir symlink) so it can hold private skills
        self.assertFalse(skills.is_symlink())
        self.assertTrue(skills.is_dir())
        # each shared skill is an individual symlink to the single source
        for sk in ("write-task", "team-inbox"):
            link = skills / sk
            self.assertTrue(link.is_symlink())
            self.assertEqual(os.readlink(link), f"../../../../.claude/skills/{sk}")
            self.assertEqual(link.resolve(), (self.root / ".claude/skills" / sk).resolve())
        # generated index file is not linked as a skill
        self.assertFalse((skills / "skills.md").exists())

    def test_private_skill_preserved_and_shared_still_linked(self):
        ta.create_agent(self.root, "worker-2")
        skills = self.root / "agents/worker-2/.claude/skills"
        # author a PRIVATE skill (real dir) isolated to this agent
        (skills / "my-private-skill").mkdir()
        (skills / "my-private-skill" / "SKILL.md").write_text("# 스킬: my-private-skill", encoding="utf-8")
        # add a NEW shared skill at the root, then re-wire
        (self.root / ".claude/skills/new-shared").mkdir()
        (self.root / ".claude/skills/new-shared/SKILL.md").write_text("# 스킬: new-shared", encoding="utf-8")
        # also place a real dir whose name COLLIDES with a shared skill (shadow case);
        # the first create wired it as a symlink, so unlink before making a real dir
        (skills / "team-inbox").unlink()
        (skills / "team-inbox").mkdir()
        (skills / "team-inbox" / "SKILL.md").write_text("# 스킬: team-inbox (private override)", encoding="utf-8")
        res = ta.create_agent(self.root, "worker-2", force=True)
        # pure-private real dir (no shared namesake) untouched and not reported
        self.assertFalse((skills / "my-private-skill").is_symlink())
        self.assertTrue((skills / "my-private-skill/SKILL.md").is_file())
        # shadowing private dir is kept (not clobbered back to a symlink) and reported
        self.assertFalse((skills / "team-inbox").is_symlink())
        self.assertEqual(res["symlinks"]["skills/team-inbox"], "private (kept)")
        # newly added shared skill got linked in on re-wire
        self.assertTrue((skills / "new-shared").is_symlink())

    def test_force_migrates_legacy_whole_dir_symlink(self):
        ta.create_agent(self.root, "worker-2")
        skills = self.root / "agents/worker-2/.claude/skills"
        # simulate the OLD scheme: replace per-skill dir with a whole-dir symlink
        import shutil
        shutil.rmtree(skills)
        os.symlink("../../../.claude/skills", skills)
        self.assertTrue(skills.is_symlink())
        # without force, migration is refused (reported, not performed)
        res_noforce = ta._wire_skills(self.root, self.root / "agents/worker-2/.claude", force=False)
        self.assertEqual(res_noforce["skills"], "whole-symlink (use --force to migrate)")
        self.assertTrue(skills.is_symlink())
        # with force, it becomes a real dir with per-skill symlinks
        ta.create_agent(self.root, "worker-2", force=True)
        self.assertFalse(skills.is_symlink())
        self.assertTrue((skills / "write-task").is_symlink())

    def test_roster_registration(self):
        res = ta.create_agent(self.root, "worker-2")
        self.assertTrue(res["roster_added"])
        members = json.loads((self.root / ".project/team.json").read_text(encoding="utf-8"))["members"]
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
        members = json.loads((self.root / ".project/team.json").read_text(encoding="utf-8"))["members"]
        self.assertEqual(members, ["orchestrator", "worker-2", "worker-3"])


class ListTests(_Case):
    def test_list_reports_drift(self):
        ta.create_agent(self.root, "worker-2")
        # roster has an extra member with no folder
        tf = self.root / ".project/team.json"
        data = json.loads(tf.read_text(encoding="utf-8"))
        data["members"].append("ghost")
        tf.write_text(json.dumps(data), encoding="utf-8")
        out = ta.list_agents(self.root)
        self.assertIn("worker-2", out["agent_folders"])
        self.assertIn("ghost", out["out_of_sync"])  # in roster, no folder


class SyncTests(_Case):
    def test_sync_reconciles_new_shared_skill(self):
        ta.create_agent(self.root, "worker-2")
        skills = self.root / "agents/worker-2/.claude/skills"
        # a new shared skill is added at the source after the agent existed
        (self.root / ".claude/skills/new-shared").mkdir()
        (self.root / ".claude/skills/new-shared/SKILL.md").write_text("# 스킬: new-shared", encoding="utf-8")
        self.assertFalse((skills / "new-shared").exists())
        out = ta.sync_agent(self.root, self.root / "agents/worker-2", "worker-2")
        self.assertEqual(out["wired"]["skills/new-shared"], "created")
        self.assertTrue((skills / "new-shared").is_symlink())

    def test_sync_prunes_stale_symlink(self):
        ta.create_agent(self.root, "worker-2")
        skills = self.root / "agents/worker-2/.claude/skills"
        self.assertTrue((skills / "team-inbox").is_symlink())
        import shutil
        shutil.rmtree(self.root / ".claude/skills/team-inbox")  # shared skill removed at source
        out = ta.sync_agent(self.root, self.root / "agents/worker-2", "worker-2")
        self.assertIn("team-inbox", out["pruned"])
        self.assertFalse((skills / "team-inbox").exists())
        self.assertTrue((skills / "write-task").is_symlink())  # live one kept

    def test_sync_keeps_private_dir(self):
        ta.create_agent(self.root, "worker-2")
        skills = self.root / "agents/worker-2/.claude/skills"
        (skills / "my-private").mkdir()
        (skills / "my-private/SKILL.md").write_text("# 스킬: my-private", encoding="utf-8")
        ta.sync_agent(self.root, self.root / "agents/worker-2", "worker-2")
        self.assertTrue((skills / "my-private").is_dir() and not (skills / "my-private").is_symlink())

    def test_sync_all_via_cli(self):
        ta.create_agent(self.root, "worker-2")
        ta.create_agent(self.root, "worker-3")
        (self.root / ".claude/skills/late-shared").mkdir()
        (self.root / ".claude/skills/late-shared/SKILL.md").write_text("# 스킬: late-shared", encoding="utf-8")
        rc = ta.main(["--team-root", str(self.root), "sync", "--all"])
        self.assertEqual(rc, 0)
        for n in ("worker-2", "worker-3"):
            self.assertTrue((self.root / f"agents/{n}/.claude/skills/late-shared").is_symlink())

    def test_sync_unknown_agent_errors(self):
        with self.assertRaises(ta.AgentError):
            ta.sync_agents(self.root, "ghost")


class CliTests(_Case):
    def test_cli_create_and_list(self):
        rc = ta.main(["--team-root", str(self.root), "create", "worker-2", "--role", "builder"])
        self.assertEqual(rc, 0)
        rc2 = ta.main(["--team-root", str(self.root), "list"])
        self.assertEqual(rc2, 0)


def build_governed_team_root(root: Path) -> None:
    """A team root WITH subteams + tiered governance, to exercise governance distribution.

    company owner = curator (data team lead too). Other team lead = lead-w (write).
    plain = plain-w (write). All five governance skills + one ordinary skill exist as
    shared root skills so the allowlist can include/exclude them.
    """
    build_fake_team_root(root)
    skills = root / ".claude" / "skills"
    for sk in ("team-init", "agent-clone-setup", "create-team-agent",
               "set-team-goal", "team-derive-author", "team-quality-ledger", "give-feedback"):
        (skills / sk).mkdir(parents=True, exist_ok=True)
        (skills / sk / "SKILL.md").write_text(f"# 스킬: {sk}", encoding="utf-8")
    team = root / ".project"
    (team / "team.json").write_text(json.dumps({
        "version": 1,
        "members": ["curator", "lead-w", "plain-w"],
        "subteams": [
            {"name": "data", "members": ["curator"], "orchestrator": "curator"},
            {"name": "write", "members": ["lead-w", "plain-w"], "orchestrator": "lead-w"},
        ],
    }), encoding="utf-8")
    (team / "policies").mkdir(parents=True, exist_ok=True)
    (team / "policies" / "team-promotion.json").write_text(json.dumps({
        "governance": {
            "mode": "tiered",
            "company_owner": "curator",
            "authoring_owner": "curator",
            "company_skills": ["team-init", "agent-clone-setup"],
            "team_skills": ["create-team-agent", "set-team-goal", "team-derive-author"],
        }
    }), encoding="utf-8")
    (root / "team-setup.json").write_text(json.dumps({
        "team": "research-umc",
        "members": ["curator", "lead-w", "plain-w"],
        "roles": {"curator": "data lead", "lead-w": "write lead", "plain-w": "writer"},
        "authoring_owner": "curator",
        "reminders_list": "umc",
        "subteams": [
            {"name": "data", "members": ["curator"], "orchestrator": "curator"},
            {"name": "write", "members": ["lead-w", "plain-w"], "orchestrator": "lead-w"},
        ],
    }), encoding="utf-8")


class GovernanceTierTests(unittest.TestCase):
    """(다) 거버넌스 팀장 분산: company owner / team lead / plain worker 별 권한."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        build_governed_team_root(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_company_owner_gets_everything(self):
        allowed = ta._allowed_shared_skills(self.root, "curator")
        for sk in ta.GOVERNANCE_COMPANY | ta.GOVERNANCE_TEAM:
            self.assertIn(sk, allowed, f"company owner should hold {sk}")
        self.assertIn("give-feedback", allowed)  # plus ordinary skills

    def test_team_lead_gets_team_tier_not_company_tier(self):
        allowed = ta._allowed_shared_skills(self.root, "lead-w")
        for sk in ta.GOVERNANCE_TEAM:
            self.assertIn(sk, allowed, f"team lead should hold TEAM-tier {sk}")
        for sk in ta.GOVERNANCE_COMPANY:
            self.assertNotIn(sk, allowed, f"team lead must NOT hold COMPANY-tier {sk}")
        self.assertIn("give-feedback", allowed)

    def test_plain_worker_gets_no_governance(self):
        allowed = ta._allowed_shared_skills(self.root, "plain-w")
        for sk in ta.GOVERNANCE_COMPANY | ta.GOVERNANCE_TEAM:
            self.assertNotIn(sk, allowed, f"plain worker must NOT hold {sk}")
        self.assertIn("give-feedback", allowed)  # ordinary skills still linked

    def test_lead_only_skill_distribution(self):
        # team-quality-ledger is LEAD-ONLY (not governance): leads + company owner get it,
        # plain workers do not.
        self.assertIn("team-quality-ledger", ta._allowed_shared_skills(self.root, "curator"))
        self.assertIn("team-quality-ledger", ta._allowed_shared_skills(self.root, "lead-w"))
        self.assertNotIn("team-quality-ledger", ta._allowed_shared_skills(self.root, "plain-w"))

    def test_lead_creates_in_own_team(self):
        res = ta.create_agent(self.root, "new-w", subteam="write", requester="lead-w")
        self.assertTrue(res["created"])
        self.assertEqual(res["subteam"], "write")
        self.assertTrue(res["subteam_added"])
        # placed under teams/write/ and registered in that subteam's members
        self.assertTrue((self.root / "teams/write/new-w/.claude/memory/memory.md").is_file())
        tj = json.loads((self.root / ".project/team.json").read_text(encoding="utf-8"))
        write_members = next(s["members"] for s in tj["subteams"] if s["name"] == "write")
        self.assertIn("new-w", write_members)
        self.assertIn("new-w", tj["members"])

    def test_subteam_create_updates_team_setup_and_workspace_policy(self):
        res = ta.create_agent(self.root, "new-w", subteam="write", requester="lead-w")
        self.assertTrue(res["subteam_added"])
        setup = json.loads((self.root / "team-setup.json").read_text(encoding="utf-8"))
        self.assertIn("new-w", setup["members"])
        write_members = next(s["members"] for s in setup["subteams"] if s["name"] == "write")
        self.assertIn("new-w", write_members)
        pol = json.loads((self.root / ".claude/policies/agent-workspace.json").read_text(encoding="utf-8"))
        self.assertIn("new-w", pol["agents"])
        self.assertIn("teams/write/new-w/**", pol["agents"]["plain-w"]["deny"])

    def test_lead_cannot_create_in_other_team(self):
        with self.assertRaises(ta.AgentError):
            ta.create_agent(self.root, "intruder", subteam="data", requester="lead-w")

    def test_plain_worker_cannot_create(self):
        with self.assertRaises(ta.AgentError):
            ta.create_agent(self.root, "x", subteam="write", requester="plain-w")

    def test_company_owner_may_create_cross_team(self):
        res = ta.create_agent(self.root, "any-w", subteam="write", requester="curator")
        self.assertTrue(res["created"])  # owner is allowed across teams

    def test_missing_identity_fails_closed_for_subteam_create(self):
        with self.assertRaises(ta.AgentError):
            ta.create_agent(self.root, "y", subteam="write", requester=None)

    def test_unknown_subteam_rejected(self):
        with self.assertRaises(ta.AgentError):
            ta.create_agent(self.root, "z", subteam="ghost", requester="lead-w")

    def test_flat_create_still_works_without_subteam(self):
        # No subteam => no own-team guard (back-compat with flat roots / existing tests).
        res = ta.create_agent(self.root, "flat-w")
        self.assertTrue(res["created"])
        self.assertIsNone(res["subteam"])


if __name__ == "__main__":
    unittest.main()
