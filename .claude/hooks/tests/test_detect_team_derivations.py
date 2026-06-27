#!/usr/bin/env python3
"""Tests for the team-tier derivation detector. CI-safe: temp team root."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / ".claude/hooks"
sys.path.insert(0, str(HOOKS_DIR))

import detect_team_derivations as dtd  # noqa: E402


def append_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as h:
        for r in records:
            h.write(json.dumps(r, ensure_ascii=False) + "\n")


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".project/policies").mkdir(parents=True)
        policy = dict(dtd.DEFAULTS)
        policy["governance"] = {"mode": "owner-authors", "authoring_owner": "orchestrator"}
        (self.root / ".project/policies/team-derivation.json").write_text(json.dumps(policy), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def signals(self, agent: str, records: list[dict]):
        append_jsonl(self.root / "agents" / agent / ".context/memory-log/signals.jsonl", records)

    def team_signals(self, agent: str, records: list[dict]):
        append_jsonl(self.root / "agents" / agent / ".context/memory-log/team-signals.jsonl", records)

    def memory_md(self, agent: str, text: str):
        p = self.root / "agents" / agent / ".claude/memory/memory.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def team_word(self, terms: list[str]):
        (self.root / ".project/word.json").write_text(
            json.dumps({"terms": [{"term": t} for t in terms]}), encoding="utf-8"
        )

    def evaluate(self):
        return dtd.evaluate(self.root, dtd.load_policy(self.root))


class TermTests(_Case):
    def test_two_agents_recorded_same_term_qualifies(self):
        self.signals("worker-1", [{"kind": "term", "key": "LISA"}])
        self.signals("worker-2", [{"kind": "term", "key": "LISA"}])
        res = self.evaluate()
        self.assertEqual(len(res["term"]), 1)
        self.assertEqual(res["term"][0]["key"], "LISA")
        self.assertEqual(res["term"][0]["distinct_agents"], 2)

    def test_one_agent_term_does_not_qualify(self):
        self.signals("worker-1", [{"kind": "term", "key": "LISA"}, {"kind": "term", "key": "LISA"}])
        self.assertEqual(self.evaluate()["term"], [])

    def test_skip_if_in_team_word(self):
        self.team_word(["lisa"])
        self.signals("worker-1", [{"kind": "term", "key": "LISA"}])
        self.signals("worker-2", [{"kind": "term", "key": "LISA"}])
        self.assertEqual(self.evaluate()["term"], [])


class ShareMarkerTests(_Case):
    def test_single_agent_share_marker_qualifies_immediately(self):
        self.memory_md("worker-1", "## 2026-06-25 - 결정\n\nFact: ...\nShare: memory\n")
        res = self.evaluate()
        self.assertEqual(len(res["memory"]), 1)
        self.assertTrue(res["memory"][0]["explicit"])
        self.assertEqual(res["memory"][0]["key"], "결정")  # title used when no detail

    def test_share_term_with_detail(self):
        self.memory_md("worker-1", "## 2026-06-25 - 용어 메모\n\nShare: term: RAG\n")
        res = self.evaluate()
        self.assertTrue(any(c["key"] == "RAG" and c["explicit"] for c in res["term"]))

    def test_explicit_overrides_present_check_false(self):
        # Even one agent: explicit Share qualifies (not gated by distinct-agent count).
        self.memory_md("worker-1", "## 2026-06-25 - 선호\n\nShare: preference: korean-output\n")
        res = self.evaluate()
        self.assertTrue(any(c["key"] == "korean-output" for c in res["preference"]))


class MemoryKindTests(_Case):
    def test_two_agents_team_signal_memory(self):
        self.team_signals("worker-1", [{"kind": "memory", "key": "use-jxa-for-reminders"}])
        self.team_signals("worker-2", [{"kind": "memory", "key": "use-jxa-for-reminders"}])
        res = self.evaluate()
        # team-signals carry explicit=False by default here -> needs distinct agents
        self.assertTrue(any(c["key"] == "use-jxa-for-reminders" for c in res["memory"]))


class DecisionTests(_Case):
    def test_decline_stops_surfacing_and_hash_filename(self):
        self.signals("worker-1", [{"kind": "term", "key": "LISA"}])
        self.signals("worker-2", [{"kind": "term", "key": "LISA"}])
        self.assertEqual(len(self.evaluate()["term"]), 1)
        rc = dtd.run_resolve([
            "--kind", "term", "--key", "LISA", "--decision", "decline",
            "--by", "orchestrator", "--project-root", str(self.root),
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(self.evaluate()["term"], [])
        files = list((self.root / ".project/derivations/decisions").glob("term__LISA__*.json"))
        self.assertEqual(len(files), 1)

    def test_non_owner_cannot_resolve(self):
        self.signals("worker-1", [{"kind": "term", "key": "LISA"}])
        self.signals("worker-2", [{"kind": "term", "key": "LISA"}])
        rc = dtd.run_resolve([
            "--kind", "term", "--key", "LISA", "--decision", "decline",
            "--by", "worker-1", "--project-root", str(self.root),
        ])
        self.assertEqual(rc, 1)
        self.assertFalse((self.root / ".project/derivations/decisions").exists())

    def test_slug_colliding_keys_both_persist(self):
        dtd.run_resolve(["--kind", "memory", "--key", "a b", "--decision", "decline", "--by", "orchestrator", "--project-root", str(self.root)])
        dtd.run_resolve(["--kind", "memory", "--key", "a-b", "--decision", "promote", "--by", "orchestrator", "--project-root", str(self.root)])
        ddir = self.root / ".project/derivations/decisions"
        self.assertEqual(len(list(ddir.glob("memory__*.json"))), 2)
        decided = dtd.load_team_decisions(ddir)
        self.assertEqual(decided["memory"]["a b"]["decision"], "decline")
        self.assertEqual(decided["memory"]["a-b"]["decision"], "promote")


class RecordAndSafetyTests(_Case):
    def test_record_team_signal_writes_to_agent_context(self):
        adir = self.root / "agents/worker-1"
        adir.mkdir(parents=True)
        rc = dtd.run_record_team_signal([
            "--kind", "memory", "--key", "k", "--note", "n", "--agent", "worker-1",
            "--project-root", str(adir),
        ])
        self.assertEqual(rc, 0)
        f = adir / ".context/memory-log/team-signals.jsonl"
        self.assertTrue(f.exists())
        rec = json.loads(f.read_text(encoding="utf-8").strip())
        self.assertEqual(rec["kind"], "memory")
        self.assertTrue(rec["explicit"])

    def test_find_team_root_none_when_no_team(self):
        with TemporaryDirectory() as d:
            self.assertIsNone(dtd.find_team_root(Path(d)))

    def test_evaluate_non_team_dir_creates_no_skeleton(self):
        with TemporaryDirectory() as d:
            rc = dtd.main(["evaluate", "--project-root", d, "--check"])
            self.assertEqual(rc, 0)
            self.assertFalse((Path(d) / ".project").exists())

    def test_hook_swallows_bad_stdin(self):
        self.assertEqual(dtd.main([]), 0)


class CaseFoldTests(_Case):
    def test_mixed_case_term_across_agents_groups_as_one(self):
        self.signals("worker-1", [{"kind": "term", "key": "LISA"}])
        self.signals("worker-2", [{"kind": "term", "key": "lisa"}])
        res = self.evaluate()
        self.assertEqual(len(res["term"]), 1)
        self.assertEqual(res["term"][0]["distinct_agents"], 2)

    def test_mis_cased_resolve_closes_candidate(self):
        self.signals("worker-1", [{"kind": "term", "key": "LISA"}])
        self.signals("worker-2", [{"kind": "term", "key": "LISA"}])
        self.assertEqual(len(self.evaluate()["term"]), 1)
        dtd.run_resolve(["--kind", "term", "--key", "lisa", "--decision", "decline", "--by", "orchestrator", "--project-root", str(self.root)])
        self.assertEqual(self.evaluate()["term"], [])  # lowercase resolve closes "LISA" candidate


class ExplicitHygieneTests(_Case):
    def test_per_agent_signal_explicit_field_is_ignored(self):
        # A polluted per-agent observation claiming explicit must NOT bypass the gate.
        self.signals("worker-1", [{"kind": "term", "key": "X", "explicit": True}])
        self.assertEqual(self.evaluate()["term"], [])  # one agent, explicit stripped on ingest

    def test_single_recorded_team_signal_explicit_qualifies(self):
        adir = self.root / "agents/worker-1"
        adir.mkdir(parents=True)
        rc = dtd.run_record_team_signal([
            "--kind", "memory", "--key", "decide-x", "--agent", "worker-1", "--project-root", str(adir),
        ])
        self.assertEqual(rc, 0)
        res = self.evaluate()
        self.assertTrue(any(c["key"] == "decide-x" and c["explicit"] for c in res["memory"]))


if __name__ == "__main__":
    unittest.main()
