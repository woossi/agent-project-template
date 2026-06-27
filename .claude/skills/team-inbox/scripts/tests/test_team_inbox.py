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


class TeamMailboxCase(unittest.TestCase):
    """Team mailbox + atomic claim model (worker→team addressing)."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = Path(self._tmp.name) / ".team"
        self.store.mkdir(parents=True)
        (self.store / "team.json").write_text(json.dumps({
            "members": ["dc", "de", "ir", "mw"],
            "subteams": [
                {"name": "data", "members": ["dc", "de", "ir"]},
                {"name": "write", "members": ["mw"]},
            ],
        }), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_team_of_and_is_team(self):
        self.assertEqual(ti.team_of(self.store, "de"), "data")
        self.assertEqual(ti.team_of(self.store, "mw"), "write")
        self.assertIsNone(ti.team_of(self.store, "nobody"))
        self.assertTrue(ti.is_team(self.store, "data"))
        self.assertFalse(ti.is_team(self.store, "dc"))

    def test_post_to_team_single_copy(self):
        res = ti.post(self.store, "mw", [], subject="s", body="b", to_team="data")
        self.assertEqual(res["delivered_to_team"], "data")
        files = list((self.store / "inbox" / "data").glob("*.json"))
        self.assertEqual(len(files), 1)  # 팀당 1부 (fan-out 아님)
        msg = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(msg["to_team"], "data")
        self.assertEqual(msg["sender_team"], "write")
        self.assertIsNone(msg["claimed_by"])

    def test_post_unknown_team_raises(self):
        with self.assertRaises(ti.InboxError):
            ti.post(self.store, "mw", [], subject="s", body="b", to_team="ghost")

    def test_claim_is_exclusive(self):
        res = ti.post(self.store, "mw", [], subject="s", body="b", to_team="data")
        mid = res["id"]
        r1 = ti.claim(self.store, "data", mid, "dc")
        r2 = ti.claim(self.store, "data", mid, "de")
        self.assertTrue(r1["claimed"])
        self.assertFalse(r2["claimed"])  # 이미 dc가 가져감
        self.assertEqual(r2["claimed_by"], "dc")

    def test_read_team_states(self):
        res = ti.post(self.store, "mw", [], subject="s", body="b", to_team="data")
        mid = res["id"]
        self.assertEqual(len(ti.read_team(self.store, "data")), 1)  # unclaimed
        ti.claim(self.store, "data", mid, "dc")
        self.assertEqual(len(ti.read_team(self.store, "data")), 0)  # 더는 unclaimed 아님
        claimed = ti.read_team(self.store, "data", include_claimed=True)
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0]["_state"], "claimed")

    def test_ack_team_consumes_claimed(self):
        res = ti.post(self.store, "mw", [], subject="s", body="b", to_team="data")
        mid = res["id"]
        ti.claim(self.store, "data", mid, "dc")
        ack = ti.ack(self.store, "dc", mid, team="data")
        self.assertTrue(ack["acked"])
        consumed = ti.read_team(self.store, "data", include_consumed=True)
        self.assertEqual(len(consumed), 1)
        self.assertEqual(consumed[0]["_state"], "consumed")

    def test_individual_post_still_works(self):
        # 팀 전환 후에도 개인 주소 발행은 그대로(병행). 스키마만 통일.
        res = ti.post(self.store, "de", ["dc"], subject="s", body="b")
        self.assertEqual(res["delivered_to"], ["dc"])
        msgs = ti.read(self.store, "dc")
        self.assertEqual(len(msgs), 1)
        self.assertIsNone(msgs[0]["to_team"])

    def test_cli_to_team_mutually_exclusive_with_to(self):
        rc = ti.main(["--store", str(self.store), "post", "--from", "mw",
                      "--to-team", "data", "--to", "dc", "--subject", "s", "--body", "b"])
        self.assertEqual(rc, 1)  # --to-team과 --to 동시 금지


class QualityFieldsCase(unittest.TestCase):
    """(가) inbox 스키마 확장: quality_gate / verdict / work_ref (옵셔널, 기본 None)."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = Path(self._tmp.name) / ".team"
        self.store.mkdir(parents=True)
        (self.store / "team.json").write_text(json.dumps({
            "members": ["dc", "mw"],
            "subteams": [{"name": "data", "members": ["dc"]}, {"name": "write", "members": ["mw"]}],
        }), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_default_quality_fields_are_none(self):
        ti.post(self.store, "dc", ["mw"], subject="s", body="b")
        msg = ti.read(self.store, "mw")[0]
        self.assertIsNone(msg["quality_gate"])
        self.assertIsNone(msg["verdict"])
        self.assertIsNone(msg["work_ref"])

    def test_assignment_carries_quality_gate(self):
        gate = {"axes": ["A", "E"], "kind": "manuscript"}
        ti.post(self.store, "dc", ["mw"], subject="작업", body="b", quality_gate=gate)
        msg = ti.read(self.store, "mw")[0]
        self.assertEqual(msg["quality_gate"], gate)

    def test_verdict_reply_carries_verdict_and_work_ref(self):
        a = ti.post(self.store, "dc", ["mw"], subject="작업", body="b",
                    quality_gate={"axes": ["A"], "kind": "manuscript"})
        v = {"result": "FAIL", "majors": 1, "minors": 0, "by": "quality-reviewer", "round": "R3"}
        ti.post(self.store, "mw", ["dc"], subject="검수결과", body="b",
                verdict=v, work_ref=a["id"])
        msg = ti.read(self.store, "dc")[0]
        self.assertEqual(msg["verdict"], v)
        self.assertEqual(msg["work_ref"], a["id"])

    def test_team_mailbox_also_carries_quality_fields(self):
        ti.post(self.store, "mw", [], subject="s", body="b", to_team="data",
                quality_gate={"axes": ["D"], "kind": "stats"})
        files = list((self.store / "inbox" / "data").glob("*.json"))
        msg = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(msg["quality_gate"], {"axes": ["D"], "kind": "stats"})

    def test_cli_quality_gate_json_parsed(self):
        rc = ti.main(["--store", str(self.store), "post", "--from", "dc", "--to", "mw",
                      "--subject", "s", "--body", "b",
                      "--quality-gate", '{"axes":["A"],"kind":"manuscript"}'])
        self.assertEqual(rc, 0)
        msg = ti.read(self.store, "mw")[0]
        self.assertEqual(msg["quality_gate"], {"axes": ["A"], "kind": "manuscript"})

    def test_cli_bad_json_rejected(self):
        rc = ti.main(["--store", str(self.store), "post", "--from", "dc", "--to", "mw",
                      "--subject", "s", "--body", "b", "--verdict", "not-json"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
