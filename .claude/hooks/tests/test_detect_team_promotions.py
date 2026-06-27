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
        policy = dict(dtp.DEFAULTS)
        policy["governance"] = {
            "mode": "tiered",
            "company_owner": "orchestrator",
            "authoring_owner": "orchestrator",
        }
        (self.root / ".project/policies/team-promotion.json").write_text(
            json.dumps(policy), encoding="utf-8"
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

    # --- inbox handoff helpers (C-work trigger: recurrence of a HANDOFF STRUCTURE) ---
    def roster(self, members: list[str], subteams: list[dict]):
        """Write team.json so classify_edge can map workers -> subteams.

        ``subteams`` is a list of {"name", "members"} dicts. A worker's folder is also
        seeded (empty task-log) so worker_dirs() discovers it for load diagnosis.
        """
        (self.root / ".project").mkdir(parents=True, exist_ok=True)
        (self.root / ".project/team.json").write_text(json.dumps({
            "version": 1, "members": members, "subteams": subteams,
        }), encoding="utf-8")
        for st in subteams:
            for m in st["members"]:
                d = self.root / "teams" / st["name"] / m / ".context/task-log"
                d.mkdir(parents=True, exist_ok=True)

    def handoff(self, frm: str, to: str, n: int, *, base_ts: int = 1_000):
        """Write ``n`` inbox messages from ``frm`` to ``to`` (each a distinct ts so edge_ts
        records >=2 occasions -> 'recurring'). Lands in the recipient's individual inbox,
        which inbox_edges fans out over recipients[]."""
        box = self.root / ".project/inbox" / to
        box.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            ts = base_ts + i
            mid = f"{ts:020d}__{frm}__{i:08x}"
            (box / f"{mid}.json").write_text(json.dumps({
                "id": mid, "from": frm, "to": to, "recipients": [to],
                "to_team": None, "claimed_by": None, "sender_team": None,
                "subject": "s", "body": "b", "reply_to": None, "ts_ns": ts,
            }), encoding="utf-8")

    def evaluate(self):
        policy = dtp.load_policy(self.root)
        return dtp.evaluate(self.root, policy)


class TeamSkillTests(_Case):
    # C-work trigger: a recurring INTRA-team HANDOFF STRUCTURE (not a task signature).
    # team_skill fires when same-subteam workers hand off >= min_intra_handoffs (default 8)
    # times across >= 2 workers.
    def _two_worker_intra_team(self):
        self.roster(
            members=["worker-1", "worker-2"],
            subteams=[{"name": "data", "members": ["worker-1", "worker-2"]}],
        )

    def test_intra_team_handoffs_qualify(self):
        self._two_worker_intra_team()
        self.handoff("worker-1", "worker-2", 5)
        self.handoff("worker-2", "worker-1", 5)  # 10 intra total, 2 workers
        res = self.evaluate()
        self.assertEqual(len(res["team_skill"]), 1)
        c = res["team_skill"][0]
        self.assertEqual(c["team"], "data")
        self.assertEqual(c["key"], "data")
        self.assertEqual(c["distinct_agents"], 2)
        self.assertEqual(sorted(c["agents"]), ["worker-1", "worker-2"])
        self.assertGreaterEqual(c["intra_handoffs"], 8)

    def test_sparse_intra_does_not_qualify(self):
        # below min_intra_handoffs -> no team_skill (the team is just quiet)
        self._two_worker_intra_team()
        self.handoff("worker-1", "worker-2", 2)
        self.assertEqual(self.evaluate()["team_skill"], [])

    def test_single_worker_cannot_make_intra_edge(self):
        # one worker can't hand off to itself across a team boundary -> never a team_skill
        self.roster(members=["solo"], subteams=[{"name": "scout", "members": ["solo"]}])
        self.handoff("solo", "solo", 10)
        self.assertEqual(self.evaluate()["team_skill"], [])

    def test_skip_if_team_skill_exists(self):
        self._two_worker_intra_team()
        # a team skill already frozen for this subteam -> do not re-surface
        sk = self.root / "teams" / "data" / ".claude" / "skills" / "data-flow"
        sk.mkdir(parents=True, exist_ok=True)
        (sk / "SKILL.md").write_text("# data-flow", encoding="utf-8")
        self.handoff("worker-1", "worker-2", 5)
        self.handoff("worker-2", "worker-1", 5)
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


def seed_intra_team_skill(case: _Case):
    """Make exactly one team_skill candidate keyed on subteam 'data' (the new trigger)."""
    case.roster(members=["worker-1", "worker-2"],
                subteams=[{"name": "data", "members": ["worker-1", "worker-2"]}])
    case.handoff("worker-1", "worker-2", 5)
    case.handoff("worker-2", "worker-1", 5)


class DecisionTests(_Case):
    def test_decline_stops_surfacing(self):
        seed_intra_team_skill(self)
        self.assertEqual(len(self.evaluate()["team_skill"]), 1)
        rc = dtp.run_resolve([
            "--kind", "team_skill", "--key", "data", "--decision", "decline",
            "--reason", "not reusable", "--by", "orchestrator", "--project-root", str(self.root),
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(self.evaluate()["team_skill"], [])
        # decision is one immutable file per (kind,key); filename carries a key hash.
        ddir = self.root / ".project/promotions/decisions"
        files = list(ddir.glob("team_skill__data__*.json"))
        self.assertEqual(len(files), 1)
        rec = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(rec["decision"], "decline")
        self.assertEqual(rec["by"], "orchestrator")
        self.assertIn("ts_ns", rec)

    def test_non_owner_cannot_resolve(self):
        seed_intra_team_skill(self)
        rc = dtp.run_resolve([
            "--kind", "team_skill", "--key", "data", "--decision", "decline",
            "--reason", "not reusable", "--by", "worker-1", "--project-root", str(self.root),
        ])
        self.assertEqual(rc, 1)
        self.assertFalse((self.root / ".project/promotions/decisions").exists())


class RootAndShardTests(_Case):
    def test_find_team_root_from_agent_subdir(self):
        (self.root / "agents/worker-1/.claude").mkdir(parents=True)
        found = dtp.find_team_root(self.root / "agents/worker-1")
        self.assertEqual(found, self.root.resolve())

    def test_find_team_root_from_self(self):
        self.assertEqual(dtp.find_team_root(self.root), self.root.resolve())

    def test_shard_written_per_runner(self):
        seed_intra_team_skill(self)
        policy = dtp.load_policy(self.root)
        dtp.write_candidates_shard(self.root, policy, self.evaluate(), "worker-1")
        shard = self.root / ".project/promotions/candidates/worker-1.json"
        self.assertTrue(shard.exists())
        data = json.loads(shard.read_text(encoding="utf-8"))
        self.assertEqual(len(data["team_skill"]), 1)

    def test_unregistered_runner_folds_into_team_bucket(self):
        """A CLAUDE_AGENT_NAME typo must not mint a ghost shard next to real workers."""
        seed_intra_team_skill(self)  # roster = worker-1, worker-2
        policy = dtp.load_policy(self.root)
        path = dtp.write_candidates_shard(self.root, policy, self.evaluate(), "worker-socut")
        cand_dir = self.root / ".project/promotions/candidates"
        self.assertFalse((cand_dir / "worker-socut.json").exists())  # no ghost
        self.assertEqual(path, cand_dir / "team.json")  # folded into shared bucket

    def test_orchestrator_is_a_valid_runner(self):
        """The company coordinator is registered even though it is not a subteam member."""
        seed_intra_team_skill(self)
        policy = dtp.load_policy(self.root)
        path = dtp.write_candidates_shard(self.root, policy, self.evaluate(), "orchestrator")
        self.assertEqual(path, self.root / ".project/promotions/candidates/orchestrator.json")

    def test_empty_roster_is_fail_open(self):
        """An unreadable/empty roster must not block a legitimate runner (no guard)."""
        # no roster() call -> no team.json members
        (self.root / ".project").mkdir(parents=True, exist_ok=True)
        self.assertEqual(dtp._validated_runner(self.root, "anyone"), "anyone")


class CliTests(_Case):
    def test_evaluate_check_exit_1_when_pending(self):
        seed_intra_team_skill(self)
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
            "--reason", "x", "--by", "orchestrator", "--project-root", str(self.root),
        ])
        r2 = dtp.run_resolve([
            "--kind", "team_agent", "--key", "a_b+c", "--decision", "promote",
            "--reason", "y", "--by", "orchestrator", "--project-root", str(self.root),
        ])
        self.assertEqual((r1, r2), (0, 0))
        ddir = self.root / ".project/promotions/decisions"
        files = sorted(p.name for p in ddir.glob("*.json"))
        self.assertEqual(len(files), 2, f"colliding keys collapsed to one file: {files}")
        decided = dtp.load_team_decisions(ddir)
        self.assertEqual(decided["team_agent"]["a+b+c"]["decision"], "decline")
        self.assertEqual(decided["team_agent"]["a_b+c"]["decision"], "promote")

    def test_same_key_twice_overwrites_last_writer_wins(self):
        dtp.run_resolve(["--kind", "team_skill", "--key", "k", "--decision", "decline", "--by", "orchestrator", "--project-root", str(self.root)])
        dtp.run_resolve(["--kind", "team_skill", "--key", "k", "--decision", "promote", "--by", "orchestrator", "--project-root", str(self.root)])
        ddir = self.root / ".project/promotions/decisions"
        self.assertEqual(len(list(ddir.glob("team_skill__*.json"))), 1)  # same key -> one file
        self.assertEqual(dtp.load_team_decisions(ddir)["team_skill"]["k"]["decision"], "promote")

    def test_promote_also_stops_surfacing(self):
        seed_intra_team_skill(self)
        self.assertEqual(len(self.evaluate()["team_skill"]), 1)
        dtp.run_resolve(["--kind", "team_skill", "--key", "data", "--decision", "promote", "--by", "orchestrator", "--project-root", str(self.root)])
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
