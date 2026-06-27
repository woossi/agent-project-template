#!/usr/bin/env python3
"""Tests for the team-ops detector. CI-safe: temp team root, no real mailboxes."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / ".claude/hooks"
sys.path.insert(0, str(HOOKS_DIR))

import detect_team_ops as dto  # noqa: E402


class _Case(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".project/policies").mkdir(parents=True)
        self._write_team(
            members=["data-lead", "data-curator", "review-lead", "quality-reviewer"],
            subteams=[
                {"name": "data", "orchestrator": "data-lead",
                 "members": ["data-lead", "data-curator"], "reminders_list": "umc-data"},
                {"name": "review", "orchestrator": "review-lead",
                 "members": ["review-lead", "quality-reviewer"], "reminders_list": "umc-review"},
            ],
        )
        (self.root / ".project/policies/team-promotion.json").write_text(
            json.dumps({"governance": {"company_owner": "orchestrator"}}), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_team(self, members, subteams) -> None:
        (self.root / ".project").mkdir(parents=True, exist_ok=True)
        (self.root / ".project/team.json").write_text(
            json.dumps({"members": members, "subteams": subteams}), encoding="utf-8"
        )

    def _mail(self, team: str, *, unclaimed: int = 0, claimed: int = 0) -> None:
        box = self.root / "teams" / team / ".claude" / "inbox"
        box.mkdir(parents=True, exist_ok=True)
        for i in range(unclaimed):
            (box / f"0000{i}__sender__{i}.json").write_text("{}", encoding="utf-8")
        cdir = box / dto.CLAIMED_DIRNAME
        cdir.mkdir(parents=True, exist_ok=True)
        for i in range(claimed):
            (cdir / f"lead__0000{i}__x.json").write_text("{}", encoding="utf-8")

    def _ledger(self, team: str, lead: str, records: list[dict]) -> None:
        p = self.root / "teams" / team / lead / ".context" / "quality-ledger.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


class ScopeTests(_Case):
    def test_lead_sees_only_own_team(self) -> None:
        teams = dto._teams_for(self.root, "data-lead")
        self.assertEqual(teams, ["data"])

    def test_worker_sees_nothing(self) -> None:
        self.assertEqual(dto._teams_for(self.root, "data-curator"), [])

    def test_typo_identity_sees_nothing(self) -> None:
        self.assertEqual(dto._teams_for(self.root, "data-leed"), [])

    def test_owner_sees_all_teams_plus_virtual_mailbox(self) -> None:
        teams = dto._teams_for(self.root, "orchestrator")
        self.assertIn("data", teams)
        self.assertIn("review", teams)
        self.assertIn(dto.ORCHESTRATOR_TEAM, teams)


class CensusTests(_Case):
    def test_mailbox_census_counts_unclaimed_and_claimed(self) -> None:
        self._mail("data", unclaimed=3, claimed=2)
        mb = dto.inspect_mailbox(self.root, "data")
        self.assertEqual(mb["unclaimed"], 3)
        self.assertEqual(mb["claimed_pending_ack"], 2)

    def test_empty_mailbox_is_zero(self) -> None:
        mb = dto.inspect_mailbox(self.root, "data")
        self.assertEqual(mb, {"unclaimed": 0, "claimed_pending_ack": 0})

    def test_quality_signal_on_two_consecutive_non_pass(self) -> None:
        # PARTIAL and FAIL both count; PASS resets.
        self._ledger("data", "data-lead", [
            {"worker": "data-curator", "kind": "codebook", "result": "pass"},
            {"worker": "data-curator", "kind": "codebook", "result": "partial"},
            {"worker": "data-curator", "kind": "codebook", "result": "fail"},
        ])
        sig = dto.inspect_quality(self.root, "data", "data-lead")
        self.assertEqual(len(sig), 1)
        self.assertEqual(sig[0]["consecutive_failures"], 2)

    def test_pass_resets_the_run(self) -> None:
        self._ledger("data", "data-lead", [
            {"worker": "w", "kind": "k", "result": "fail"},
            {"worker": "w", "kind": "k", "result": "fail"},
            {"worker": "w", "kind": "k", "result": "pass"},
        ])
        self.assertEqual(dto.inspect_quality(self.root, "data", "data-lead"), [])

    def test_spawned_key_is_suppressed(self) -> None:
        self._ledger("data", "data-lead", [
            {"worker": "w", "kind": "k", "result": "fail"},
            {"worker": "w", "kind": "k", "result": "fail"},
            {"op": "mark-spawned", "worker": "w", "kind": "k"},
        ])
        self.assertEqual(dto.inspect_quality(self.root, "data", "data-lead"), [])


class SurfaceTests(_Case):
    def test_no_pending_means_no_output(self) -> None:
        report = dto.gather(self.root, "data-lead")
        self.assertFalse(dto._has_pending(report))

    def test_pending_renders_korean_summary(self) -> None:
        self._mail("data", unclaimed=4, claimed=5)
        report = dto.gather(self.root, "data-lead")
        self.assertTrue(dto._has_pending(report))
        text = dto.format_surface(report)
        self.assertIn("data", text)
        self.assertIn("미처리", text)


if __name__ == "__main__":
    unittest.main()
