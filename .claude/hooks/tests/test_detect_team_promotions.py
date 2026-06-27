#!/usr/bin/env python3
"""Tests for the team-tier promotion detector. CI-safe: temp team root, no agents."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / ".claude/hooks"
sys.path.insert(0, str(HOOKS_DIR))

import detect_team_promotions as dtp  # noqa: E402


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".project/policies").mkdir(parents=True)
        (self.root / ".claude/skills").mkdir(parents=True)
        (self.root / ".claude/agents").mkdir(parents=True)
        # default policy
        (self.root / ".project/policies/team-promotion.json").write_text(
            json.dumps(dtp.DEFAULTS), encoding="utf-8"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def agent_tasks(self, agent: str, records: list[dict]):
        write_jsonl(self.root / "agents" / agent / ".context/task-log/tasks.jsonl", records)

    def agent_events(self, agent: str, records: list[dict]):
        write_jsonl(self.root / "agents" / agent / ".context/task-log/events.jsonl", records)

    def make_skill(self, name: str):
        d = self.root / ".claude/skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"# {name}", encoding="utf-8")

    def make_agent_doc(self, name: str, body: str):
        (self.root / ".claude/agents" / f"{name}.md").write_text(body, encoding="utf-8")

    def evaluate(self):
        policy = dtp.load_policy(self.root)
        return dtp.evaluate(self.root, policy)


class TeamSkillTests(_Case):
    def test_two_distinct_agents_qualifies(self):
        self.agent_tasks("worker-1", [{"signature": "shared-task", "objective": "do X"}])
        self.agent_tasks("worker-2", [{"signature": "shared-task", "objective": "do X too"}])
        res = self.evaluate()
        self.assertEqual(len(res["team_skill"]), 1)
        c = res["team_skill"][0]
        self.assertEqual(c["signature"], "shared-task")
        self.assertEqual(c["distinct_agents"], 2)
        self.assertEqual(sorted(c["agents"]), ["worker-1", "worker-2"])

    def test_one_agent_repeating_does_not_qualify(self):
        # The load-bearing distinction: same agent, three of its own records.
        self.agent_tasks("worker-1", [{"signature": "solo"} for _ in range(3)])
        res = self.evaluate()
        self.assertEqual(res["team_skill"], [])

    def test_folder_name_is_the_axis_not_the_stamp(self):
        # Even if a record carries a different 'agent' stamp, the folder is ground truth.
        self.agent_tasks("worker-1", [{"signature": "s", "agent": "spoof"}])
        self.agent_tasks("worker-2", [{"signature": "s", "agent": "spoof"}])
        res = self.evaluate()
        self.assertEqual(res["team_skill"][0]["distinct_agents"], 2)

    def test_skip_if_skill_exists(self):
        self.make_skill("shared-task")
        self.agent_tasks("worker-1", [{"signature": "shared-task"}])
        self.agent_tasks("worker-2", [{"signature": "shared-task"}])
        self.assertEqual(self.evaluate()["team_skill"], [])


class TeamAgentTests(_Case):
    def test_package_across_two_agents_from_tasks(self):
        self.agent_tasks("worker-1", [{"signature": "t1", "skills": ["bridge", "inbox"]}])
        self.agent_tasks("worker-2", [{"signature": "t2", "skills": ["bridge", "inbox"]}])
        res = self.evaluate()
        self.assertEqual(len(res["team_agent"]), 1)
        c = res["team_agent"][0]
        self.assertEqual(c["skills"], ["bridge", "inbox"])
        self.assertEqual(c["distinct_agents"], 2)

    def test_package_from_events_buckets_by_agent(self):
        self.agent_events("worker-1", [{"skill": "a"}, {"skill": "b"}])
        self.agent_events("worker-2", [{"skill": "a"}, {"skill": "b"}])
        res = self.evaluate()
        self.assertTrue(any(c["skills"] == ["a", "b"] for c in res["team_agent"]))

    def test_one_agent_package_does_not_qualify(self):
        self.agent_events("worker-1", [{"skill": "a"}, {"skill": "b"}])
        self.assertEqual(self.evaluate()["team_agent"], [])

    def test_skip_if_agent_exists(self):
        self.make_agent_doc("combo", "uses bridge and inbox together")
        self.agent_tasks("worker-1", [{"skills": ["bridge", "inbox"], "signature": "t"}])
        self.agent_tasks("worker-2", [{"skills": ["bridge", "inbox"], "signature": "t2"}])
        # signature differs so no team_skill; team_agent skipped because covered by agent doc
        self.assertEqual(self.evaluate()["team_agent"], [])


class DecisionTests(_Case):
    def test_decline_stops_surfacing(self):
        self.agent_tasks("worker-1", [{"signature": "shared"}])
        self.agent_tasks("worker-2", [{"signature": "shared"}])
        self.assertEqual(len(self.evaluate()["team_skill"]), 1)
        rc = dtp.run_resolve([
            "--kind", "team_skill", "--key", "shared", "--decision", "decline",
            "--reason", "not reusable", "--by", "orchestrator", "--project-root", str(self.root),
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(self.evaluate()["team_skill"], [])
        # decision is one immutable file per (kind,key); filename carries a key hash.
        ddir = self.root / ".project/promotions/decisions"
        files = list(ddir.glob("team_skill__shared__*.json"))
        self.assertEqual(len(files), 1)
        rec = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(rec["decision"], "decline")
        self.assertEqual(rec["by"], "orchestrator")
        self.assertIn("ts_ns", rec)


class RootAndShardTests(_Case):
    def test_find_team_root_from_agent_subdir(self):
        (self.root / "agents/worker-1/.claude").mkdir(parents=True)
        found = dtp.find_team_root(self.root / "agents/worker-1")
        self.assertEqual(found, self.root.resolve())

    def test_find_team_root_from_self(self):
        self.assertEqual(dtp.find_team_root(self.root), self.root.resolve())

    def test_shard_written_per_runner(self):
        self.agent_tasks("worker-1", [{"signature": "shared"}])
        self.agent_tasks("worker-2", [{"signature": "shared"}])
        policy = dtp.load_policy(self.root)
        dtp.write_candidates_shard(self.root, policy, self.evaluate(), "worker-1")
        shard = self.root / ".project/promotions/candidates/worker-1.json"
        self.assertTrue(shard.exists())
        data = json.loads(shard.read_text(encoding="utf-8"))
        self.assertEqual(len(data["team_skill"]), 1)


class CliTests(_Case):
    def test_evaluate_check_exit_1_when_pending(self):
        self.agent_tasks("worker-1", [{"signature": "shared"}])
        self.agent_tasks("worker-2", [{"signature": "shared"}])
        rc = dtp.main(["evaluate", "--project-root", str(self.root), "--check"])
        self.assertEqual(rc, 1)

    def test_evaluate_exit_0_when_none(self):
        rc = dtp.main(["evaluate", "--project-root", str(self.root), "--check"])
        self.assertEqual(rc, 0)

    def test_hook_swallows_bad_stdin(self):
        # run_hook with no/invalid stdin must not raise.
        rc = dtp.main([])  # reads stdin; in test it's empty -> JSONDecodeError -> 0
        self.assertEqual(rc, 0)


class DecisionCollisionTests(_Case):
    def test_slug_colliding_keys_both_persist(self):
        # Two distinct keys whose _safe() slug collides ('+' and '_' both -> '_').
        r1 = dtp.run_resolve([
            "--kind", "team_agent", "--key", "a+b+c", "--decision", "decline",
            "--reason", "x", "--project-root", str(self.root),
        ])
        r2 = dtp.run_resolve([
            "--kind", "team_agent", "--key", "a_b+c", "--decision", "promote",
            "--reason", "y", "--project-root", str(self.root),
        ])
        self.assertEqual((r1, r2), (0, 0))
        ddir = self.root / ".project/promotions/decisions"
        files = sorted(p.name for p in ddir.glob("*.json"))
        self.assertEqual(len(files), 2, f"colliding keys collapsed to one file: {files}")
        decided = dtp.load_team_decisions(ddir)
        self.assertEqual(decided["team_agent"]["a+b+c"]["decision"], "decline")
        self.assertEqual(decided["team_agent"]["a_b+c"]["decision"], "promote")

    def test_same_key_twice_overwrites_last_writer_wins(self):
        dtp.run_resolve(["--kind", "team_skill", "--key", "k", "--decision", "decline", "--project-root", str(self.root)])
        dtp.run_resolve(["--kind", "team_skill", "--key", "k", "--decision", "promote", "--project-root", str(self.root)])
        ddir = self.root / ".project/promotions/decisions"
        self.assertEqual(len(list(ddir.glob("team_skill__*.json"))), 1)  # same key -> one file
        self.assertEqual(dtp.load_team_decisions(ddir)["team_skill"]["k"]["decision"], "promote")

    def test_promote_also_stops_surfacing(self):
        self.agent_tasks("worker-1", [{"signature": "shared"}])
        self.agent_tasks("worker-2", [{"signature": "shared"}])
        self.assertEqual(len(self.evaluate()["team_skill"]), 1)
        dtp.run_resolve(["--kind", "team_skill", "--key", "shared", "--decision", "promote", "--project-root", str(self.root)])
        self.assertEqual(self.evaluate()["team_skill"], [])


class NoTeamSafetyTests(_Case):
    def test_find_team_root_none_when_no_team(self):
        with TemporaryDirectory() as d:
            self.assertIsNone(dtp.find_team_root(Path(d)))

    def test_evaluate_non_team_dir_creates_no_skeleton(self):
        with TemporaryDirectory() as d:
            rc = dtp.main(["evaluate", "--project-root", d, "--check"])
            self.assertEqual(rc, 0)
            self.assertFalse((Path(d) / ".project").exists())  # no fake skeleton minted

    def test_resolve_non_team_dir_returns_1_and_writes_nothing(self):
        with TemporaryDirectory() as d:
            rc = dtp.run_resolve(["--kind", "team_skill", "--key", "x", "--decision", "promote", "--project-root", d])
            self.assertEqual(rc, 1)
            self.assertFalse((Path(d) / ".project").exists())


class OneAgentPackageTaskPathTests(_Case):
    def test_one_agent_package_via_tasks_does_not_qualify(self):
        # Same agent, two task records each carrying the same skill bundle.
        self.agent_tasks("worker-1", [
            {"skills": ["a", "b"], "signature": "t1"},
            {"skills": ["a", "b"], "signature": "t2"},
        ])
        self.assertEqual(self.evaluate()["team_agent"], [])


if __name__ == "__main__":
    unittest.main()
