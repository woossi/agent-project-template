#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = HOOKS_DIR / "detect_promotions.py"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import detect_promotions as dp  # noqa: E402

SKILL_RULES = {"min_recurrence": 3, "min_distinct_sessions": 2, "skip_if_skill_exists": True, "max_candidates": 20}
AGENT_RULES = {
    "min_package_size": 2,
    "min_cousage": 3,
    "min_distinct_sessions": 2,
    "skip_if_agent_exists": True,
    "max_candidates": 20,
}


def task(session: str, signature: str, skills=None) -> dict:
    return {"session": session, "signature": signature, "objective": f"do {signature}", "skills": skills or []}


class SkillCandidateTest(unittest.TestCase):
    def test_recurring_signature_across_sessions_is_a_candidate(self) -> None:
        tasks = [task("s1", "x"), task("s1", "x"), task("s2", "x")]
        cands = dp.skill_candidates(tasks, SKILL_RULES, set(), {})
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["signature"], "x")
        self.assertEqual(cands[0]["recurrence"], 3)
        self.assertEqual(cands[0]["distinct_sessions"], 2)

    def test_single_session_does_not_qualify(self) -> None:
        tasks = [task("s1", "x"), task("s1", "x"), task("s1", "x")]
        self.assertEqual(dp.skill_candidates(tasks, SKILL_RULES, set(), {}), [])

    def test_below_recurrence_does_not_qualify(self) -> None:
        tasks = [task("s1", "x"), task("s2", "x")]
        self.assertEqual(dp.skill_candidates(tasks, SKILL_RULES, set(), {}), [])

    def test_existing_skill_is_skipped(self) -> None:
        tasks = [task("s1", "x"), task("s1", "x"), task("s2", "x")]
        self.assertEqual(dp.skill_candidates(tasks, SKILL_RULES, {"x"}, {}), [])

    def test_decided_signature_is_skipped(self) -> None:
        tasks = [task("s1", "x"), task("s1", "x"), task("s2", "x")]
        decided = {"x": {"decision": "decline"}}
        self.assertEqual(dp.skill_candidates(tasks, SKILL_RULES, set(), decided), [])


class AgentCandidateTest(unittest.TestCase):
    def test_skill_package_co_used_across_sessions_is_a_candidate(self) -> None:
        tasks = [
            task("s1", "t", ["a", "b"]),
            task("s2", "t", ["a", "b"]),
            task("s3", "t", ["a", "b"]),
        ]
        cands = dp.agent_candidates(tasks, [], AGENT_RULES, [], {})
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["skills"], ["a", "b"])
        self.assertEqual(cands[0]["cousage"], 3)

    def test_skill_usage_events_feed_detection(self) -> None:
        events = [
            {"session": "s1", "skill": "a"},
            {"session": "s1", "skill": "b"},
            {"session": "s2", "skill": "a"},
            {"session": "s2", "skill": "b"},
            {"session": "s3", "skill": "a"},
            {"session": "s3", "skill": "b"},
        ]
        cands = dp.agent_candidates([], events, AGENT_RULES, [], {})
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["skills"], ["a", "b"])

    def test_only_maximal_package_is_reported(self) -> None:
        tasks = [
            task("s1", "t", ["a", "b", "c"]),
            task("s2", "t", ["a", "b", "c"]),
            task("s3", "t", ["a", "b", "c"]),
        ]
        cands = dp.agent_candidates(tasks, [], AGENT_RULES, [], {})
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["skills"], ["a", "b", "c"])

    def test_package_covered_by_existing_agent_is_skipped(self) -> None:
        tasks = [
            task("s1", "t", ["a", "b"]),
            task("s2", "t", ["a", "b"]),
            task("s3", "t", ["a", "b"]),
        ]
        agent_text = "This agent uses skills a and b together."
        self.assertEqual(dp.agent_candidates(tasks, [], AGENT_RULES, [agent_text], {}), [])

    def test_decided_package_is_skipped(self) -> None:
        tasks = [
            task("s1", "t", ["a", "b"]),
            task("s2", "t", ["a", "b"]),
            task("s3", "t", ["a", "b"]),
        ]
        self.assertEqual(dp.agent_candidates(tasks, [], AGENT_RULES, [], {"a+b": {"decision": "decline"}}), [])


class SurfaceTest(unittest.TestCase):
    def test_surface_is_empty_without_candidates(self) -> None:
        self.assertEqual(dp.format_surface({"skill": [], "agent": []}), "")

    def test_surface_lists_actionable_candidates(self) -> None:
        candidates = {
            "skill": [
                {"signature": "x", "recurrence": 3, "distinct_sessions": 2, "objectives": ["do x"]}
            ],
            "agent": [{"skills": ["a", "b"], "cousage": 3, "distinct_sessions": 2}],
        }
        text = dp.format_surface(candidates)
        self.assertIn("write-skill", text)
        self.assertIn("write-subagent", text)
        self.assertIn("signature 'x'", text)
        self.assertIn("[a, b]", text)

    def test_emit_unknown_event_defaults_to_posttooluse(self) -> None:
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dp.emit_hook_context("hello", "NotARealEvent")
        out = json.loads(buf.getvalue())
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")


class IntegrationTest(unittest.TestCase):
    def _seed(self, root: Path) -> None:
        log = root / ".context/task-log"
        log.mkdir(parents=True)
        tasks = [task("s1", "x"), task("s1", "x"), task("s2", "x")]
        (log / "tasks.jsonl").write_text(
            "\n".join(json.dumps(t) for t in tasks) + "\n", encoding="utf-8"
        )
        (root / ".claude/skills").mkdir(parents=True)

    def test_evaluate_writes_candidates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "evaluate", "--project-root", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            candidates = json.loads((root / ".context/promotions/candidates.json").read_text())
            self.assertEqual(len(candidates["skill"]), 1)

    def test_check_flag_returns_one_when_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "evaluate", "--check", "--project-root", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)

    def test_resolve_clears_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            resolve = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "resolve",
                    "--kind",
                    "skill",
                    "--key",
                    "x",
                    "--decision",
                    "decline",
                    "--reason",
                    "one-off",
                    "--project-root",
                    str(root),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(resolve.returncode, 0, resolve.stderr)
            decisions = json.loads((root / ".context/promotions/decisions.json").read_text())
            self.assertEqual(decisions["skill"]["x"]["decision"], "decline")
            candidates = json.loads((root / ".context/promotions/candidates.json").read_text())
            self.assertEqual(candidates["skill"], [])

    def test_hook_mode_emits_additional_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            payload = {"session_id": "s3", "tool_name": "Edit", "cwd": str(root)}
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=False,
                env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out = json.loads(result.stdout)
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")
            self.assertIn("signature 'x'", out["hookSpecificOutput"]["additionalContext"])

    def test_hook_mode_echoes_session_start_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            payload = {
                "session_id": "s3",
                "hook_event_name": "SessionStart",
                "source": "startup",
                "cwd": str(root),
            }
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=False,
                env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out = json.loads(result.stdout)
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
            self.assertIn("signature 'x'", out["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
