#!/usr/bin/env python3
"""Tests for the TEAM-only inbox channel. CI-safe: pure filesystem, no agents/osascript.

Model (2026-06-27 재설계): every message goes to a TEAM mailbox living in the team folder
(teams/<team>/.claude/inbox/). No individual address, no broadcast. Members claim; one wins.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = REPO_ROOT / ".claude/skills/team-inbox/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import team_inbox as ti  # noqa: E402


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".project").mkdir(parents=True)
        (self.root / ".project" / "team.json").write_text(json.dumps({
            "members": ["dc", "de", "ir", "mw", "ms"],
            "subteams": [
                {"name": "data", "members": ["dc", "de", "ir"]},
                {"name": "write", "members": ["mw", "ms"]},
            ],
        }), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()


class MsgidTests(unittest.TestCase):
    def test_sortable_and_unique(self):
        ids = [ti.new_msgid("a", clock=lambda: 5, rand=lambda: f"{i:08d}") for i in range(3)]
        self.assertTrue(all(m.startswith("00000000000000000005__a__") for m in ids))
        self.assertEqual(len(set(ids)), 3)

    def test_sorts_by_time_prefix(self):
        early = ti.new_msgid("a", clock=lambda: 1, rand=lambda: "x")
        late = ti.new_msgid("a", clock=lambda: 2, rand=lambda: "x")
        self.assertLess(early, late)

    def test_unsafe_sender_sanitized(self):
        mid = ti.new_msgid("a/b c", clock=lambda: 1, rand=lambda: "x")
        self.assertNotIn("/", mid)
        self.assertNotIn(" ", mid)


class RosterTests(_Case):
    def test_team_of_and_is_team(self):
        self.assertEqual(ti.team_of(self.root, "de"), "data")
        self.assertEqual(ti.team_of(self.root, "mw"), "write")
        self.assertIsNone(ti.team_of(self.root, "nobody"))
        self.assertTrue(ti.is_team(self.root, "data"))
        self.assertTrue(ti.is_team(self.root, "orchestrator"))  # virtual mailbox
        self.assertFalse(ti.is_team(self.root, "dc"))  # a worker is not a team

    def test_mailbox_dir_locations(self):
        # team mailbox lives in the team folder (same tier as memory/skills/tasks)
        self.assertEqual(ti.mailbox_dir(self.root, "data"),
                         self.root / "teams" / "data" / ".claude" / "inbox")
        # orchestrator is a virtual team mailbox outside any team folder
        self.assertEqual(ti.mailbox_dir(self.root, "orchestrator"),
                         self.root / "teams" / ".orchestrator" / "inbox")


class PostTests(_Case):
    def test_post_to_team_single_copy_in_team_folder(self):
        res = ti.post(self.root, "mw", to_team="data", subject="s", body="b")
        self.assertEqual(res["delivered_to_team"], "data")
        box = self.root / "teams" / "data" / ".claude" / "inbox"
        files = list(box.glob("*.json"))
        self.assertEqual(len(files), 1)  # 팀당 1부
        msg = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(msg["to_team"], "data")
        self.assertEqual(msg["sender_team"], "write")
        self.assertIsNone(msg["claimed_by"])
        self.assertEqual(sorted(msg["recipients"]), ["dc", "de", "ir"])

    def test_post_unknown_team_raises(self):
        with self.assertRaises(ti.InboxError):
            ti.post(self.root, "mw", to_team="ghost", subject="s", body="b")

    def test_post_to_orchestrator_virtual_mailbox(self):
        res = ti.post(self.root, "ms", to_team="orchestrator", subject="보고", body="b")
        self.assertEqual(res["delivered_to_team"], "orchestrator")
        box = self.root / "teams" / ".orchestrator" / "inbox"
        self.assertEqual(len(list(box.glob("*.json"))), 1)

    def test_quality_fields_attach(self):
        gate = {"axes": ["A", "E"], "kind": "manuscript"}
        ti.post(self.root, "ms", to_team="write", subject="작업", body="b", quality_gate=gate)
        msg = ti.read_team(self.root, "write")[0]
        self.assertEqual(msg["quality_gate"], gate)
        self.assertIsNone(msg["verdict"])

    def test_post_orders_chronologically(self):
        ids = []
        for i in range(3):
            r = ti.post(self.root, "mw", to_team="data", subject=str(i), body="b",
                        msgid_factory=lambda s, i=i: ti.new_msgid(s, clock=lambda: i + 1, rand=lambda: "z"))
            ids.append(r["id"])
        got = [m["id"] for m in ti.read_team(self.root, "data")]
        self.assertEqual(got, ids)


class ClaimAckTests(_Case):
    def test_claim_is_exclusive(self):
        mid = ti.post(self.root, "mw", to_team="data", subject="s", body="b")["id"]
        r1 = ti.claim(self.root, "data", mid, "dc")
        r2 = ti.claim(self.root, "data", mid, "de")
        self.assertTrue(r1["claimed"])
        self.assertFalse(r2["claimed"])
        self.assertEqual(r2["claimed_by"], "dc")

    def test_read_team_states(self):
        mid = ti.post(self.root, "mw", to_team="data", subject="s", body="b")["id"]
        self.assertEqual(len(ti.read_team(self.root, "data")), 1)  # unclaimed
        ti.claim(self.root, "data", mid, "dc")
        self.assertEqual(len(ti.read_team(self.root, "data")), 0)  # no longer unclaimed
        claimed = ti.read_team(self.root, "data", include_claimed=True)
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0]["_state"], "claimed")

    def test_ack_consumes_claimed(self):
        mid = ti.post(self.root, "mw", to_team="data", subject="s", body="b")["id"]
        ti.claim(self.root, "data", mid, "dc")
        out = ti.ack(self.root, "data", mid, agent="dc")
        self.assertTrue(out["acked"])
        consumed = ti.read_team(self.root, "data", include_consumed=True)
        self.assertEqual(len(consumed), 1)
        self.assertEqual(consumed[0]["_state"], "consumed")

    def test_ack_unknown_is_idempotent(self):
        out = ti.ack(self.root, "data", "does-not-exist", agent="dc")
        self.assertFalse(out["acked"])

    def test_claim_then_ack_full_cycle(self):
        mid = ti.post(self.root, "ms", to_team="data", subject="task", body="b")["id"]
        self.assertTrue(ti.claim(self.root, "data", mid, "de")["claimed"])
        self.assertTrue(ti.ack(self.root, "data", mid, agent="de")["acked"])
        # gone from unclaimed + claimed, present in consumed
        self.assertEqual(ti.read_team(self.root, "data"), [])
        self.assertEqual(len(ti.read_team(self.root, "data", include_consumed=True)), 1)


class IdentityTests(_Case):
    def test_identity_from_env(self):
        import os
        os.environ["CLAUDE_AGENT_NAME"] = "fromenv"
        try:
            self.assertEqual(ti.resolve_identity(None), "fromenv")
        finally:
            del os.environ["CLAUDE_AGENT_NAME"]

    def test_identity_missing_errors(self):
        import os
        old = os.environ.pop("CLAUDE_AGENT_NAME", None)
        try:
            with self.assertRaises(ti.InboxError):
                ti.resolve_identity(None)
        finally:
            if old is not None:
                os.environ["CLAUDE_AGENT_NAME"] = old


class CliTests(_Case):
    def _argv(self, *a):
        return ["--root", str(self.root), *a]

    def test_cli_post_read_round_trip(self):
        rc = ti.main(self._argv("post", "--from", "mw", "--to-team", "data",
                                "--subject", "s", "--body", "b"))
        self.assertEqual(rc, 0)
        self.assertEqual(len(ti.read_team(self.root, "data")), 1)

    def test_cli_read_defaults_to_own_team(self):
        ti.post(self.root, "mw", to_team="data", subject="s", body="b")
        rc = ti.main(self._argv("read", "--as", "de"))  # de is in data
        self.assertEqual(rc, 0)

    def test_cli_claim_and_ack(self):
        mid = ti.post(self.root, "mw", to_team="data", subject="s", body="b")["id"]
        rc1 = ti.main(self._argv("claim", "--team", "data", "--as", "dc", "--id", mid))
        rc2 = ti.main(self._argv("ack", "--team", "data", "--as", "dc", "--id", mid))
        self.assertEqual((rc1, rc2), (0, 0))
        self.assertEqual(len(ti.read_team(self.root, "data", include_consumed=True)), 1)

    def test_cli_bad_verdict_json_rejected(self):
        rc = ti.main(self._argv("post", "--from", "mw", "--to-team", "data",
                                "--subject", "s", "--body", "b", "--verdict", "not-json"))
        self.assertEqual(rc, 1)

    def test_cli_post_requires_to_team(self):
        # --to-team is required; argparse exits non-zero (SystemExit) without it
        with self.assertRaises(SystemExit):
            ti.main(self._argv("post", "--from", "mw", "--subject", "s", "--body", "b"))


class AnchorTests(_Case):
    def test_find_team_root_from_subdir(self):
        deep = self.root / "teams" / "data" / "de"
        deep.mkdir(parents=True)
        self.assertEqual(ti.find_team_root(deep), self.root.resolve())


if __name__ == "__main__":
    unittest.main()
