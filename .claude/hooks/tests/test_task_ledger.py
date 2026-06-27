#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = HOOKS_DIR / "task_ledger.py"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import task_ledger  # noqa: E402


def run_hook(root: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"},
    )


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class RecordSkillUseTest(unittest.TestCase):
    def test_record_skill_use_stamps_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rc = task_ledger.main([
                "record-skill-use", "--skill", "reminders-team-bridge",
                "--agent", "worker-1", "--session", "s1", "--project-root", str(root),
            ])
            self.assertEqual(rc, 0)
            events = read_jsonl(root / ".context/task-log/events.jsonl")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["tool"], "SkillUse")
            self.assertEqual(events[0]["skill"], "reminders-team-bridge")
            self.assertEqual(events[0]["agent"], "worker-1")

    def test_empty_skill_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc = task_ledger.main(["record-skill-use", "--skill", "  ", "--project-root", tmp])
            self.assertEqual(rc, 2)


class TaskLedgerTest(unittest.TestCase):
    def test_edit_event_is_captured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "session_id": "s1",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(root / "src/app.py")},
            }
            result = run_hook(root, payload)
            self.assertEqual(result.returncode, 0, result.stderr)
            events = read_jsonl(root / ".context/task-log/events.jsonl")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["tool"], "Edit")
            self.assertEqual(events[0]["paths"], ["src/app.py"])
            self.assertEqual(events[0]["session"], "s1")
            self.assertNotIn("skill", events[0])

    def test_skill_md_read_is_captured_as_skill_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "session_id": "s1",
                "tool_name": "Read",
                "tool_input": {"file_path": ".claude/skills/write-task/SKILL.md"},
            }
            result = run_hook(root, payload)
            self.assertEqual(result.returncode, 0, result.stderr)
            events = read_jsonl(root / ".context/task-log/events.jsonl")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["skill"], "write-task")

    def test_plain_read_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "session_id": "s1",
                "tool_name": "Read",
                "tool_input": {"file_path": "README.md"},
            }
            result = run_hook(root, payload)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / ".context/task-log/events.jsonl").exists())

    def test_consecutive_identical_events_are_deduped(self) -> None:
        """A repeated idempotent tool call (e.g. `echo hi` Bash) must not stack up."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"session_id": "s1", "tool_name": "Bash", "tool_input": {}}
            for _ in range(5):
                run_hook(root, payload)
            events = read_jsonl(root / ".context/task-log/events.jsonl")
            self.assertEqual(len(events), 1)

    def test_distinct_events_are_not_deduped(self) -> None:
        """Dedup is consecutive-only: a different event between repeats is preserved."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = {"session_id": "s1", "tool_name": "Edit", "tool_input": {"file_path": str(root / "a.py")}}
            b = {"session_id": "s1", "tool_name": "Edit", "tool_input": {"file_path": str(root / "b.py")}}
            run_hook(root, a)
            run_hook(root, a)  # consecutive dup -> suppressed
            run_hook(root, b)  # distinct -> kept
            run_hook(root, a)  # not consecutive with the first a -> kept
            events = read_jsonl(root / ".context/task-log/events.jsonl")
            self.assertEqual([e["paths"] for e in events], [["a.py"], ["b.py"], ["a.py"]])

    def test_events_rotate_when_over_max_lines(self) -> None:
        """Distinct events past the policy cap trim in place, keeping a .1 backup."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = root / ".claude/policies/promotion.json"
            policy.parent.mkdir(parents=True, exist_ok=True)
            policy.write_text(json.dumps({"log": {"events_max_lines": 10}}), encoding="utf-8")
            for i in range(25):
                run_hook(root, {
                    "session_id": "s1", "tool_name": "Edit",
                    "tool_input": {"file_path": str(root / f"f{i}.py")},
                })
            events_path = root / ".context/task-log/events.jsonl"
            events = read_jsonl(events_path)
            self.assertLessEqual(len(events), 10)
            self.assertEqual(events[-1]["paths"], ["f24.py"])  # newest retained
            self.assertTrue(events_path.with_suffix(".jsonl.1").exists())  # backup made

    def test_bad_stdin_never_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                input="not-json",
                text=True,
                capture_output=True,
                check=False,
                env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_record_task_appends_semantic_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "record-task",
                    "--project-root",
                    str(root),
                    "--session",
                    "s1",
                    "--signature",
                    "translate-doc",
                    "--objective",
                    "Translate the spec",
                    "--skills",
                    "register-term,write-task",
                    "--paths",
                    "docs/spec.md",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            tasks = read_jsonl(root / ".context/task-log/tasks.jsonl")
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["signature"], "translate-doc")
            self.assertEqual(tasks[0]["skills"], ["register-term", "write-task"])
            self.assertEqual(tasks[0]["paths"], ["docs/spec.md"])

    def test_record_task_requires_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "record-task",
                    "--project-root",
                    str(root),
                    "--signature",
                    "   ",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)

    def test_skill_from_paths_unit(self) -> None:
        self.assertEqual(
            task_ledger.skill_from_paths([".claude/skills/write-skill/SKILL.md"]),
            "write-skill",
        )
        self.assertIsNone(task_ledger.skill_from_paths(["docs/SKILL.md"]))

    def test_find_repo_root_prefers_project_marker_over_worker_agents_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worker = root / "teams/data/de"
            worker.mkdir(parents=True)
            (root / ".project").mkdir()
            (root / ".project/team.json").write_text("{}", encoding="utf-8")
            (worker / "AGENTS.md").write_text("# symlink stand-in", encoding="utf-8")
            self.assertEqual(task_ledger._find_repo_root(worker), root)

    def test_project_dir_uses_registered_worker_under_explicit_project_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worker = root / "teams/data/de"
            worker.mkdir(parents=True)
            (root / ".project").mkdir()
            (root / ".project/team.json").write_text(json.dumps({
                "members": ["de"],
                "subteams": [{"name": "data", "members": ["de"], "orchestrator": "de"}],
            }), encoding="utf-8")
            old_project = os.environ.get("CLAUDE_PROJECT_DIR")
            old_agent = os.environ.get("CLAUDE_AGENT_NAME")
            try:
                os.environ["CLAUDE_PROJECT_DIR"] = str(root)
                os.environ["CLAUDE_AGENT_NAME"] = "de"
                self.assertEqual(task_ledger.project_dir({"cwd": str(worker)}), worker.resolve())
            finally:
                if old_project is None:
                    os.environ.pop("CLAUDE_PROJECT_DIR", None)
                else:
                    os.environ["CLAUDE_PROJECT_DIR"] = old_project
                if old_agent is None:
                    os.environ.pop("CLAUDE_AGENT_NAME", None)
                else:
                    os.environ["CLAUDE_AGENT_NAME"] = old_agent


if __name__ == "__main__":
    unittest.main()
