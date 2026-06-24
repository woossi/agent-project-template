#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = HOOKS_DIR / "detect_feedback.py"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import detect_feedback  # noqa: E402


def run_hook(root: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"},
    )


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
        env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"},
    )


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_policy(self_root: Path, peer_inbox: Path, self_name: str = "agent-a", peer_name: str = "agent-b") -> None:
    policy = {
        "version": 1,
        "agent": {"self": self_name, "peer": peer_name, "peer_inbox": str(peer_inbox)},
        "log": {
            "inbox": ".context/feedback/inbox.jsonl",
            "outbox": ".context/feedback/outbox.jsonl",
            "candidates": ".context/feedback/candidates.json",
            "decisions": ".context/feedback/decisions.json",
        },
        "surface": {
            "max_open": 10,
            "min_severity": "minor",
            "recurrence_signal": {"min_recurrence": 2, "min_distinct_sessions": 1},
        },
        "kinds": ["praise", "issue", "request_change", "question"],
        "severity_order": ["info", "minor", "major", "critical"],
    }
    path = self_root / ".claude/policies/feedback.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy), encoding="utf-8")


class RecordFeedbackTest(unittest.TestCase):
    def test_writes_peer_inbox_and_own_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root_a, root_b = Path(a), Path(b)
            peer_inbox = root_b / ".context/feedback/inbox.jsonl"
            write_policy(root_a, peer_inbox)
            result = run_cli(
                root_a, "record-feedback",
                "--task-ref", "summarize-x", "--kind", "request_change",
                "--severity", "major", "--message", "broken source link",
                "--related-paths", "notes/x.md", "--session", "s1",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            inbox = read_jsonl(peer_inbox)
            outbox = read_jsonl(root_a / ".context/feedback/outbox.jsonl")
            self.assertEqual(len(inbox), 1)
            self.assertEqual(len(outbox), 1)
            self.assertEqual(inbox[0]["from_agent"], "agent-a")
            self.assertEqual(inbox[0]["to_agent"], "agent-b")
            self.assertEqual(inbox[0]["status"], "open")
            self.assertTrue(inbox[0]["id"].startswith("fb-"))
            self.assertEqual(inbox[0], outbox[0])

    def test_rejects_unknown_kind_and_severity(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root_a, root_b = Path(a), Path(b)
            write_policy(root_a, root_b / ".context/feedback/inbox.jsonl")
            bad_kind = run_cli(
                root_a, "record-feedback", "--task-ref", "x",
                "--kind", "nope", "--message", "m",
            )
            self.assertEqual(bad_kind.returncode, 2)
            bad_sev = run_cli(
                root_a, "record-feedback", "--task-ref", "x",
                "--kind", "issue", "--severity", "huge", "--message", "m",
            )
            self.assertEqual(bad_sev.returncode, 2)

    def test_missing_peer_inbox_errors(self) -> None:
        with tempfile.TemporaryDirectory() as a:
            root_a = Path(a)
            # Policy with an explicitly empty peer_inbox.
            policy = {
                "version": 1,
                "agent": {"self": "agent-a", "peer": "agent-b", "peer_inbox": ""},
                "log": {
                    "inbox": ".context/feedback/inbox.jsonl",
                    "outbox": ".context/feedback/outbox.jsonl",
                    "candidates": ".context/feedback/candidates.json",
                    "decisions": ".context/feedback/decisions.json",
                },
                "kinds": ["praise", "issue", "request_change", "question"],
                "severity_order": ["info", "minor", "major", "critical"],
            }
            path = root_a / ".claude/policies/feedback.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(policy), encoding="utf-8")
            result = run_cli(
                root_a, "record-feedback", "--task-ref", "x",
                "--kind", "issue", "--message", "m",
            )
            self.assertEqual(result.returncode, 2)


class MakeIdTest(unittest.TestCase):
    def test_idempotent(self) -> None:
        rec = {
            "from_agent": "a", "to_agent": "b", "task_ref": "t",
            "kind": "issue", "message": "m",
        }
        self.assertEqual(detect_feedback.make_id(rec), detect_feedback.make_id(dict(rec)))

    def test_fold_dedups_by_id(self) -> None:
        rec = {"id": "fb-1", "status": "open", "task_ref": "t", "kind": "issue"}
        update = {"id": "fb-1", "status": "resolved"}
        folded = detect_feedback.fold_inbox([rec, update])
        self.assertEqual(len(folded), 1)
        self.assertEqual(folded["fb-1"]["status"], "resolved")
        self.assertEqual(folded["fb-1"]["task_ref"], "t")  # original field preserved


class EvaluateTest(unittest.TestCase):
    def _seed(self, root: Path, records: list[dict]) -> None:
        inbox = root / ".context/feedback/inbox.jsonl"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        for rec in records:
            detect_feedback.append_jsonl(inbox, rec)

    def test_min_severity_filters_info(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root_a = Path(a)
            write_policy(root_a, Path(b) / "inbox.jsonl")
            self._seed(root_a, [
                {"id": "fb-i", "from_agent": "x", "kind": "question", "severity": "info",
                 "task_ref": "t1", "message": "minor q", "status": "open", "session": "s1"},
                {"id": "fb-m", "from_agent": "x", "kind": "issue", "severity": "major",
                 "task_ref": "t2", "message": "big", "status": "open", "session": "s1"},
            ])
            policy = detect_feedback.load_policy(root_a)
            result = detect_feedback.evaluate(root_a, policy)
            ids = {c["id"] for c in result["feedback"]}
            self.assertIn("fb-m", ids)
            self.assertNotIn("fb-i", ids)

    def test_recurring_flag(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root_a = Path(a)
            write_policy(root_a, Path(b) / "inbox.jsonl")
            self._seed(root_a, [
                {"id": "fb-1", "from_agent": "x", "kind": "issue", "severity": "major",
                 "task_ref": "same", "message": "first", "status": "open", "session": "s1"},
                {"id": "fb-2", "from_agent": "x", "kind": "issue", "severity": "major",
                 "task_ref": "same", "message": "second", "status": "open", "session": "s1"},
            ])
            policy = detect_feedback.load_policy(root_a)
            result = detect_feedback.evaluate(root_a, policy)
            self.assertTrue(all(c["recurring"] for c in result["feedback"]))


class ResolveTest(unittest.TestCase):
    def test_resolve_closes_item(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root_a = Path(a)
            write_policy(root_a, Path(b) / "inbox.jsonl")
            inbox = root_a / ".context/feedback/inbox.jsonl"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            detect_feedback.append_jsonl(inbox, {
                "id": "fb-x", "from_agent": "x", "kind": "issue", "severity": "major",
                "task_ref": "t", "message": "m", "status": "open", "session": "s1",
            })
            before = detect_feedback.evaluate(root_a, detect_feedback.load_policy(root_a))
            self.assertEqual(len(before["feedback"]), 1)

            result = run_cli(root_a, "resolve", "--id", "fb-x", "--decision", "resolved", "--reason", "fixed")
            self.assertEqual(result.returncode, 0, result.stderr)
            after = detect_feedback.evaluate(root_a, detect_feedback.load_policy(root_a))
            self.assertEqual(len(after["feedback"]), 0)
            decisions = json.loads((root_a / ".context/feedback/decisions.json").read_text())
            self.assertEqual(decisions["feedback"]["fb-x"]["decision"], "resolved")


class HookSafetyTest(unittest.TestCase):
    def test_bad_stdin_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                input="not json",
                text=True,
                capture_output=True,
                check=False,
                env={"CLAUDE_PROJECT_DIR": tmp, "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(result.returncode, 0)

    def test_hook_surfaces_open_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root_a = Path(a)
            write_policy(root_a, Path(b) / "inbox.jsonl")
            inbox = root_a / ".context/feedback/inbox.jsonl"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            detect_feedback.append_jsonl(inbox, {
                "id": "fb-h", "from_agent": "peer", "kind": "request_change", "severity": "major",
                "task_ref": "t", "message": "please fix", "status": "open", "session": "s1",
            })
            result = run_hook(root_a, {"hook_event_name": "PostToolUse", "tool_name": "Edit"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("please fix", result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "PostToolUse")


if __name__ == "__main__":
    unittest.main()
