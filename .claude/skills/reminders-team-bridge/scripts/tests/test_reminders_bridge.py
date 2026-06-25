#!/usr/bin/env python3
"""Tests for the Apple Reminders <-> Team bridge CLI.

These tests are CI-safe: they never call ``osascript`` or touch the real
Reminders database. ``run_jxa`` takes an injectable ``runner`` so the JXA
boundary is faked, and ``build_command`` is a pure function over parsed args.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = REPO_ROOT / ".claude/skills/reminders-team-bridge/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import reminders_bridge as rb  # noqa: E402


def parse(argv: list[str]):
    return rb.build_parser().parse_args(argv)


def fake_runner(returncode: int, stdout: str, stderr: str = ""):
    return lambda argv: SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class BuildCommandTests(unittest.TestCase):
    def test_list_teams(self):
        self.assertEqual(rb.build_command(parse(["list-teams"])), {"op": "list-teams"})

    def test_pull_open_only(self):
        cmd = rb.build_command(parse(["pull", "umc"]))
        self.assertEqual(cmd, {"op": "pull", "list": "umc", "includeCompleted": False})

    def test_pull_all(self):
        cmd = rb.build_command(parse(["pull", "umc", "--all"]))
        self.assertTrue(cmd["includeCompleted"])

    def test_add_full(self):
        cmd = rb.build_command(
            parse(["add", "umc", "작업", "--notes", "메모", "--priority", "1", "--due", "2026-06-30"])
        )
        self.assertEqual(cmd["op"], "add")
        self.assertEqual(cmd["list"], "umc")
        self.assertEqual(cmd["name"], "작업")
        self.assertEqual(cmd["notes"], "메모")
        self.assertEqual(cmd["priority"], 1)
        self.assertEqual(cmd["due"], "2026-06-30")

    def test_add_minimal_omits_optional_keys(self):
        cmd = rb.build_command(parse(["add", "umc", "작업"]))
        self.assertNotIn("notes", cmd)
        self.assertNotIn("priority", cmd)
        self.assertNotIn("due", cmd)

    def test_complete_prefers_id_over_name(self):
        cmd = rb.build_command(parse(["complete", "umc", "--id", "x://1", "--name", "작업"]))
        self.assertEqual(cmd["id"], "x://1")
        self.assertNotIn("name", cmd)

    def test_complete_falls_back_to_name(self):
        cmd = rb.build_command(parse(["complete", "umc", "--name", "작업"]))
        self.assertEqual(cmd["name"], "작업")
        self.assertNotIn("id", cmd)

    def test_selector_requires_id_or_name(self):
        with self.assertRaises(rb.BridgeError):
            rb.build_command(parse(["complete", "umc"]))

    def test_annotate(self):
        cmd = rb.build_command(parse(["annotate", "umc", "[agent-A] 25%", "--name", "작업"]))
        self.assertEqual(cmd["op"], "annotate")
        self.assertEqual(cmd["note"], "[agent-A] 25%")
        self.assertEqual(cmd["name"], "작업")

    def test_create_and_delete_list(self):
        self.assertEqual(rb.build_command(parse(["create-list", "sbx"]))["op"], "create-list")
        self.assertEqual(rb.build_command(parse(["delete-list", "sbx"]))["list"], "sbx")


class RunJxaTests(unittest.TestCase):
    def test_ok_path_returns_parsed(self):
        out = rb.run_jxa({"op": "pull"}, runner=fake_runner(0, '{"ok": true, "op": "pull", "result": []}'))
        self.assertTrue(out["ok"])
        self.assertEqual(out["result"], [])

    def test_ok_path_preserves_korean(self):
        out = rb.run_jxa(
            {"op": "pull"},
            runner=fake_runner(0, '{"ok": true, "op": "pull", "result": [{"name": "작업"}]}'),
        )
        self.assertEqual(out["result"][0]["name"], "작업")

    def test_worker_failure_raises(self):
        with self.assertRaises(rb.BridgeError) as ctx:
            rb.run_jxa({"op": "pull"}, runner=fake_runner(0, '{"ok": false, "error": "list not found"}'))
        self.assertIn("list not found", str(ctx.exception))

    def test_non_json_raises(self):
        with self.assertRaises(rb.BridgeError):
            rb.run_jxa({"op": "pull"}, runner=fake_runner(0, "not json at all"))

    def test_nonzero_empty_stdout_raises_stderr(self):
        # The -1743 (not authorized for Automation) shape: nonzero exit, message on stderr.
        with self.assertRaises(rb.BridgeError) as ctx:
            rb.run_jxa({"op": "pull"}, runner=fake_runner(1, "", "Not authorized to send Apple events"))
        self.assertIn("Not authorized", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
