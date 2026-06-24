#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = HOOKS_DIR / "detect_derivations.py"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import detect_derivations as dd  # noqa: E402

PREF_RULES = {"min_recurrence": 2, "min_distinct_sessions": 1, "skip_if_recorded": True, "max_candidates": 20}
TERM_RULES = {"min_recurrence": 2, "min_distinct_sessions": 1, "skip_if_registered": True, "max_candidates": 20}


def signal(kind: str, key: str, session: str = "s1", note: str = "", explicit: bool = False) -> dict:
    rec = {"kind": kind, "key": key, "session": session, "note": note}
    if explicit:
        rec["explicit"] = True
    return rec


class PreferenceCandidateTest(unittest.TestCase):
    def test_recurring_signal_qualifies(self) -> None:
        signals = [signal("preference", "terse-output", "s1"), signal("preference", "terse-output", "s2")]
        cands = dd.derive_candidates(signals, PREF_RULES, "preference", lambda k: False, {})
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["key"], "terse-output")
        self.assertEqual(cands[0]["recurrence"], 2)

    def test_single_observation_does_not_qualify(self) -> None:
        signals = [signal("preference", "terse-output", "s1")]
        self.assertEqual(dd.derive_candidates(signals, PREF_RULES, "preference", lambda k: False, {}), [])

    def test_explicit_marker_qualifies_immediately(self) -> None:
        signals = [signal("preference", "terse-output", "memory.md", explicit=True)]
        cands = dd.derive_candidates(signals, PREF_RULES, "preference", lambda k: False, {})
        self.assertEqual(len(cands), 1)
        self.assertTrue(cands[0]["explicit"])

    def test_already_recorded_preference_is_skipped(self) -> None:
        signals = [signal("preference", "terse-output", "s1"), signal("preference", "terse-output", "s2")]
        self.assertEqual(dd.derive_candidates(signals, PREF_RULES, "preference", lambda k: True, {}), [])

    def test_decided_preference_is_skipped(self) -> None:
        signals = [signal("preference", "terse-output", "s1"), signal("preference", "terse-output", "s2")]
        decided = {"terse-output": {"decision": "decline"}}
        self.assertEqual(dd.derive_candidates(signals, PREF_RULES, "preference", lambda k: False, decided), [])

    def test_explicit_marker_sorts_before_recorded(self) -> None:
        signals = [
            signal("preference", "recorded", "s1"),
            signal("preference", "recorded", "s2"),
            signal("preference", "marked", "memory.md", explicit=True),
        ]
        cands = dd.derive_candidates(signals, PREF_RULES, "preference", lambda k: False, {})
        self.assertEqual([c["key"] for c in cands], ["marked", "recorded"])


class TermCandidateTest(unittest.TestCase):
    def test_recurring_term_qualifies(self) -> None:
        signals = [signal("term", "RAG", "s1"), signal("term", "RAG", "s2")]
        cands = dd.derive_candidates(signals, TERM_RULES, "term", lambda k: False, {})
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["key"], "RAG")

    def test_registered_term_is_skipped(self) -> None:
        registered = {"rag"}
        signals = [signal("term", "RAG", "s1"), signal("term", "RAG", "s2")]
        is_present = lambda k: k.strip().lower() in registered  # noqa: E731
        self.assertEqual(dd.derive_candidates(signals, TERM_RULES, "term", is_present, {}), [])

    def test_kind_filtering(self) -> None:
        signals = [signal("preference", "x", "s1"), signal("preference", "x", "s2")]
        self.assertEqual(dd.derive_candidates(signals, TERM_RULES, "term", lambda k: False, {}), [])


class MemoryScanTest(unittest.TestCase):
    def _root(self, body: str) -> Path:
        tmp = tempfile.mkdtemp()
        root = Path(tmp)
        (root / ".claude/memory").mkdir(parents=True)
        (root / ".claude/memory/memory.md").write_text(body, encoding="utf-8")
        return root

    def test_preference_marker_is_extracted(self) -> None:
        root = self._root("## 2026-06-24 - Likes terse output\n\nFact: x\nDerive: preference\n")
        signals = dd.memory_signals(root)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["kind"], "preference")
        self.assertEqual(signals[0]["key"], "Likes terse output")
        self.assertTrue(signals[0]["explicit"])

    def test_term_marker_with_word_is_extracted(self) -> None:
        root = self._root("## 2026-06-24 - LISA definition\n\nFact: x\nDerive: term: LISA\n")
        signals = dd.memory_signals(root)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["kind"], "term")
        self.assertEqual(signals[0]["key"], "LISA")

    def test_entry_without_marker_is_ignored(self) -> None:
        root = self._root("## 2026-06-24 - Plain fact\n\nFact: x\nSource: y\n")
        self.assertEqual(dd.memory_signals(root), [])


class SurfaceTest(unittest.TestCase):
    def test_surface_is_empty_without_candidates(self) -> None:
        self.assertEqual(dd.format_surface({"preference": [], "term": []}), "")

    def test_surface_lists_actionable_candidates(self) -> None:
        candidates = {
            "preference": [
                {"key": "terse-output", "recurrence": 2, "distinct_sessions": 2, "explicit": False, "notes": ["likes terse"]}
            ],
            "term": [
                {"key": "RAG", "recurrence": 1, "distinct_sessions": 1, "explicit": True, "notes": ["RAG def"]}
            ],
        }
        text = dd.format_surface(candidates)
        self.assertIn("register-term", text)
        self.assertIn("user_preferences.md", text)
        self.assertIn("terse-output", text)
        self.assertIn("'RAG'", text)
        self.assertIn("explicit memory marker", text)

    def test_emit_unknown_event_defaults_to_posttooluse(self) -> None:
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dd.emit_hook_context("hello", "NotARealEvent")
        out = json.loads(buf.getvalue())
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")


class IntegrationTest(unittest.TestCase):
    def _seed(self, root: Path) -> None:
        mem = root / ".claude/memory"
        mem.mkdir(parents=True)
        (mem / "memory.md").write_text(
            "## 2026-06-24 - Likes terse output\n\nFact: prefers short answers\nDerive: preference\n",
            encoding="utf-8",
        )
        (mem / "user_preferences.md").write_text("# User Preferences\n\nNo preferences yet.\n", encoding="utf-8")
        (mem / "word.json").write_text(json.dumps({"terms": []}), encoding="utf-8")

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
            candidates = json.loads((root / ".context/memory-promotions/candidates.json").read_text())
            self.assertEqual(len(candidates["preference"]), 1)

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

    def test_record_signal_then_detect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude/memory").mkdir(parents=True)
            (root / ".claude/memory/word.json").write_text(json.dumps({"terms": []}), encoding="utf-8")
            for session in ("s1", "s2"):
                rec = subprocess.run(
                    [
                        sys.executable, str(SCRIPT), "record-signal",
                        "--kind", "term", "--key", "RAG", "--session", session,
                        "--project-root", str(root),
                    ],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(rec.returncode, 0, rec.stderr)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "evaluate", "--check", "--project-root", str(root)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 1)
            candidates = json.loads((root / ".context/memory-promotions/candidates.json").read_text())
            self.assertEqual(candidates["term"][0]["key"], "RAG")

    def test_resolve_clears_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            resolve = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "resolve",
                    "--kind", "preference", "--key", "Likes terse output",
                    "--decision", "promote", "--reason", "moved to prefs",
                    "--project-root", str(root),
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(resolve.returncode, 0, resolve.stderr)
            decisions = json.loads((root / ".context/memory-promotions/decisions.json").read_text())
            self.assertEqual(decisions["preference"]["Likes terse output"]["decision"], "promote")
            candidates = json.loads((root / ".context/memory-promotions/candidates.json").read_text())
            self.assertEqual(candidates["preference"], [])

    def test_hook_mode_emits_additional_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            payload = {"session_id": "s3", "tool_name": "Edit", "cwd": str(root)}
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                input=json.dumps(payload),
                text=True, capture_output=True, check=False,
                env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out = json.loads(result.stdout)
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")
            self.assertIn("Likes terse output", out["hookSpecificOutput"]["additionalContext"])

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
                text=True, capture_output=True, check=False,
                env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out = json.loads(result.stdout)
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")


if __name__ == "__main__":
    unittest.main()
