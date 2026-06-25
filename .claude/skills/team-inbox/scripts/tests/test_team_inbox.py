#!/usr/bin/env python3
"""Tests for the team inbox channel. CI-safe: pure filesystem, no agents/osascript."""

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


class _StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = Path(self._tmp.name) / ".team"
        self.store.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def write_roster(self, members):
        (self.store / "team.json").write_text(json.dumps({"members": members}), encoding="utf-8")


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


class PostReadAckTests(_StoreCase):
    def test_targeted_post_then_read(self):
        res = ti.post(self.store, "alice", ["bob"], subject="hi", body="본문")
        self.assertEqual(res["delivered_to"], ["bob"])
        msgs = ti.read(self.store, "bob")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["from"], "alice")
        self.assertEqual(msgs[0]["body"], "본문")
        self.assertEqual(msgs[0]["_state"], "unread")
        # sender's own inbox stays empty
        self.assertEqual(ti.read(self.store, "alice"), [])

    def test_fanout_one_file_per_recipient(self):
        ti.post(self.store, "alice", ["bob", "carol"], subject="s", body="b")
        self.assertEqual(len(ti.read(self.store, "bob")), 1)
        self.assertEqual(len(ti.read(self.store, "carol")), 1)

    def test_dedupes_recipients(self):
        res = ti.post(self.store, "alice", ["bob", "bob"], subject="s", body="b")
        self.assertEqual(res["delivered_to"], ["bob"])

    def test_broadcast_excludes_self(self):
        self.write_roster(["alice", "bob", "carol"])
        res = ti.post(self.store, "alice", [], subject="s", body="b", broadcast=True)
        self.assertEqual(sorted(res["delivered_to"]), ["bob", "carol"])

    def test_broadcast_without_roster_errors(self):
        with self.assertRaises(ti.InboxError):
            ti.post(self.store, "alice", [], subject="s", body="b", broadcast=True)

    def test_read_orders_chronologically(self):
        ids = []
        for i in range(3):
            r = ti.post(
                self.store, "alice", ["bob"], subject=str(i), body="b",
                msgid_factory=lambda s, i=i: ti.new_msgid(s, clock=lambda: i + 1, rand=lambda: "z"),
            )
            ids.append(r["id"])
        got = [m["id"] for m in ti.read(self.store, "bob")]
        self.assertEqual(got, ids)

    def test_ack_moves_out_of_unread_and_is_idempotent(self):
        res = ti.post(self.store, "alice", ["bob"], subject="s", body="b")
        mid = res["id"]
        ack1 = ti.ack(self.store, "bob", mid)
        self.assertTrue(ack1["acked"])
        self.assertEqual(ti.read(self.store, "bob"), [])
        # consumed message still visible with --all
        allmsgs = ti.read(self.store, "bob", include_consumed=True)
        self.assertEqual(len(allmsgs), 1)
        self.assertEqual(allmsgs[0]["_state"], "read")
        # second ack is a no-op, not an error
        ack2 = ti.ack(self.store, "bob", mid)
        self.assertTrue(ack2["acked"])

    def test_ack_unknown_id_not_error(self):
        out = ti.ack(self.store, "bob", "does-not-exist")
        self.assertFalse(out["acked"])

    def test_no_recipient_errors(self):
        with self.assertRaises(ti.InboxError):
            ti.post(self.store, "alice", [], subject="s", body="b")


class IdentityTests(_StoreCase):
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


class CliTests(_StoreCase):
    def test_cli_post_read_round_trip(self):
        rc = ti.main(["--store", str(self.store), "post", "--from", "alice", "--to", "bob", "--subject", "s", "--body", "b"])
        self.assertEqual(rc, 0)
        msgs = ti.read(self.store, "bob")
        self.assertEqual(len(msgs), 1)

    def test_cli_missing_identity_returns_1(self):
        import os
        old = os.environ.pop("CLAUDE_AGENT_NAME", None)
        try:
            rc = ti.main(["--store", str(self.store), "read"])
            self.assertEqual(rc, 1)
        finally:
            if old is not None:
                os.environ["CLAUDE_AGENT_NAME"] = old


if __name__ == "__main__":
    unittest.main()
