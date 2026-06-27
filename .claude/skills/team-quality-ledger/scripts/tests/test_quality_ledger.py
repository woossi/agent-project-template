#!/usr/bin/env python3
"""Tests for the team quality ledger. CI-safe: pure filesystem, deterministic clock."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = REPO_ROOT / ".claude/skills/team-quality-ledger/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import quality_ledger as ql  # noqa: E402


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        team = self.root / ".project"
        team.mkdir(parents=True)
        (team / "team.json").write_text(json.dumps({
            "version": 1,
            "members": ["lead-w", "writer-w"],
            "subteams": [
                {"name": "write", "members": ["lead-w", "writer-w"], "orchestrator": "lead-w"},
            ],
        }), encoding="utf-8")
        # the lead's folder must exist for ledger writes (created lazily anyway)
        (self.root / "teams" / "write" / "lead-w" / ".context").mkdir(parents=True)
        self._n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def _clock(self):
        # monotonically increasing, deterministic
        self._n += 1
        return self._n

    def rec(self, result, *, worker="writer-w", kind="intro"):
        return ql.record(self.root, "write", worker=worker, kind=kind,
                         result=result, clock=self._clock)


class CountingTests(_Case):
    def test_pass_only_resets_partial_and_fail_count(self):
        # Q1: PASS resets; PARTIAL and FAIL both count as failures.
        self.rec("FAIL")
        self.rec("PARTIAL")
        sigs = ql.signal(self.root, "write")
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0]["consecutive_failures"], 2)
        self.assertEqual(sigs[0]["recommend"], "spawn_specialized_worker")
        self.assertEqual(sigs[0]["last_results"], ["FAIL", "PARTIAL"])

    def test_pass_between_breaks_the_run(self):
        self.rec("FAIL")
        self.rec("PASS")   # reset
        self.rec("FAIL")
        sigs = ql.signal(self.root, "write")
        self.assertEqual(sigs, [])  # only 1 trailing failure

    def test_single_failure_no_signal(self):
        self.rec("PARTIAL")
        self.assertEqual(ql.signal(self.root, "write"), [])

    def test_three_in_a_row_still_signals(self):
        self.rec("FAIL"); self.rec("PARTIAL"); self.rec("FAIL")
        sigs = ql.signal(self.root, "write")
        self.assertEqual(sigs[0]["consecutive_failures"], 3)

    def test_per_key_isolation(self):
        # different (worker, kind) keys count independently
        self.rec("FAIL", kind="intro")
        self.rec("FAIL", kind="methods")
        sigs = ql.signal(self.root, "write")
        self.assertEqual(sigs, [])  # each key only at 1
        self.rec("FAIL", kind="intro")
        sigs = ql.signal(self.root, "write")
        self.assertEqual([(s["worker"], s["kind"]) for s in sigs], [("writer-w", "intro")])

    def test_is_failure_helper(self):
        self.assertFalse(ql.is_failure("PASS"))
        self.assertTrue(ql.is_failure("PARTIAL"))
        self.assertTrue(ql.is_failure("FAIL"))


class AntiThrashTests(_Case):
    def test_spawned_mark_downgrades_to_rebalance(self):
        self.rec("FAIL"); self.rec("FAIL")
        ql.mark_spawned(self.root, "write", worker="writer-w", kind="intro", clock=self._clock)
        # mark_spawned appends a PASS marker -> the trailing run is now broken too,
        # but a fresh failure after spawning re-triggers as a REBALANCE recommendation.
        self.rec("FAIL"); self.rec("FAIL")
        sigs = ql.signal(self.root, "write")
        self.assertEqual(len(sigs), 1)
        self.assertTrue(sigs[0]["already_spawned"])
        self.assertEqual(sigs[0]["recommend"], "rebalance")


class ValidationTests(_Case):
    def test_bad_result_rejected(self):
        with self.assertRaises(ql.LedgerError):
            ql.record(self.root, "write", worker="w", kind="k", result="MAYBE")

    def test_unknown_team_no_lead(self):
        with self.assertRaises(ql.LedgerError):
            ql.ledger_path(self.root, "ghost")

    def test_ledger_path_is_lead_private_folder(self):
        p = ql.ledger_path(self.root, "write")
        self.assertEqual(p.parts[-4:], ("write", "lead-w", ".context", "quality-ledger.jsonl"))


class CliTests(_Case):
    def test_cli_record_then_signal(self):
        rc1 = ql.main(["--team-root", str(self.root), "--team", "write", "record",
                       "--worker", "writer-w", "--kind", "intro", "--result", "fail"])
        rc2 = ql.main(["--team-root", str(self.root), "--team", "write", "record",
                       "--worker", "writer-w", "--kind", "intro", "--result", "partial"])
        self.assertEqual((rc1, rc2), (0, 0))
        recs = ql._read_all(ql.ledger_path(self.root, "write"))
        sigs = ql.signal(self.root, "write")
        self.assertEqual(len(recs), 2)
        self.assertEqual(sigs[0]["consecutive_failures"], 2)

    def test_cli_team_inferred_from_env(self):
        import os
        os.environ["CLAUDE_AGENT_NAME"] = "lead-w"
        try:
            rc = ql.main(["--team-root", str(self.root), "record",
                          "--worker", "writer-w", "--kind", "k", "--result", "pass"])
            self.assertEqual(rc, 0)
        finally:
            del os.environ["CLAUDE_AGENT_NAME"]


if __name__ == "__main__":
    unittest.main()
