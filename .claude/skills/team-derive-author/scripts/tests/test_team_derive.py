#!/usr/bin/env python3
"""Tests for team-derivation authoring. CI-safe: pure filesystem."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = REPO_ROOT / ".claude/skills/team-derive-author/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import team_derive as td  # noqa: E402


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = Path(self._tmp.name) / ".project"
        (self.store / "policies").mkdir(parents=True)
        (self.store / "policies/team-derivation.json").write_text(
            json.dumps({"governance": {"authoring_owner": "orchestrator"}}), encoding="utf-8"
        )
        (self.store / "team.json").write_text(json.dumps({
            "members": ["worker-1", "orchestrator"],
            "subteams": [{"name": "data", "members": ["worker-1"], "orchestrator": "worker-1"}],
        }), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()


class TermTests(_Case):
    def test_owner_registers_term(self):
        rec = td.register_term(
            self.store, term="LISA", ko="국소 모란 지수", definition="국소 공간 자기상관 지표",
            use_when="공간 클러스터를 식별할 때", by="orchestrator",
        )
        self.assertEqual(rec["term"], "LISA")
        data = json.loads((self.store / "word.json").read_text(encoding="utf-8"))
        self.assertEqual(data["terms"][0]["term"], "LISA")

    def test_non_owner_refused(self):
        with self.assertRaises(td.DeriveAuthorError):
            td.register_term(self.store, term="X", ko="x", definition="x", use_when="x", by="worker-1")

    def test_missing_field_refused(self):
        with self.assertRaises(td.DeriveAuthorError):
            td.register_term(self.store, term="X", ko="", definition="d", use_when="u", by="orchestrator")

    def test_duplicate_term_refused_case_insensitive(self):
        td.register_term(self.store, term="RAG", ko="검색증강", definition="d", use_when="u", by="orchestrator")
        with self.assertRaises(td.DeriveAuthorError):
            td.register_term(self.store, term="rag", ko="검색증강", definition="d2", use_when="u2", by="orchestrator")

    def test_word_json_valid_and_atomic(self):
        td.register_term(self.store, term="A", ko="a", definition="d", use_when="u", by="orchestrator")
        td.register_term(self.store, term="B", ko="b", definition="d", use_when="u", by="orchestrator")
        data = json.loads((self.store / "word.json").read_text(encoding="utf-8"))
        self.assertEqual([t["term"] for t in data["terms"]], ["A", "B"])
        self.assertEqual(data["schema_version"], "1.0")


class MemoryTests(_Case):
    def test_record_memory_immutable_and_renders(self):
        r1 = td.record_memory(self.store, key="use-jxa", fact="JXA로 미리알림 읽는다", by="orchestrator", clock=lambda: 1)
        self.assertTrue((self.store / "memory" / Path(
            f"{1:020d}__orchestrator__use-jxa.json").name).exists())
        td.render_memory(self.store)
        md = (self.store / "memory.md").read_text(encoding="utf-8")
        self.assertIn("use-jxa", md)
        self.assertIn("JXA로 미리알림 읽는다", md)

    def test_shared_memory_refuses_non_owner(self):
        with self.assertRaises(td.DeriveAuthorError):
            td.record_memory(self.store, key="use-jxa", fact="JXA로 미리알림 읽는다", by="worker-1", clock=lambda: 1)

    def test_record_memory_needs_key_and_fact(self):
        with self.assertRaises(td.DeriveAuthorError):
            td.record_memory(self.store, key="", fact="x")
        with self.assertRaises(td.DeriveAuthorError):
            td.record_memory(self.store, key="k", fact="")

    def test_render_dedups_by_key_last_wins(self):
        td.record_memory(self.store, key="k", fact="old", by="orchestrator", clock=lambda: 1)
        td.record_memory(self.store, key="k", fact="new", by="orchestrator", clock=lambda: 2)
        td.render_memory(self.store)
        md = (self.store / "memory.md").read_text(encoding="utf-8")
        self.assertIn("new", md)
        self.assertNotIn("old", md)


class CliTests(_Case):
    def test_cli_owner_term(self):
        rc = td.main([
            "--store", str(self.store), "--by", "orchestrator", "register-term",
            "--term", "T", "--ko", "ㅌ", "--definition", "d", "--use-when", "u",
        ])
        self.assertEqual(rc, 0)

    def test_cli_non_owner_returns_1(self):
        rc = td.main([
            "--store", str(self.store), "--by", "worker-1", "register-term",
            "--term", "T", "--ko", "ㅌ", "--definition", "d", "--use-when", "u",
        ])
        self.assertEqual(rc, 1)

    def test_cli_cwd_identity_overrides_spoofed_by(self):
        worker = self.store.parent / "teams" / "data" / "worker-1"
        worker.mkdir(parents=True)
        old_cwd = Path.cwd()
        old_pwd = os.environ.get("PWD")
        try:
            os.chdir(worker)
            os.environ["PWD"] = str(worker)
            rc = td.main([
                "--store", str(self.store), "--by", "orchestrator", "register-term",
                "--term", "T", "--ko", "ㅌ", "--definition", "d", "--use-when", "u",
            ])
        finally:
            os.chdir(old_cwd)
            if old_pwd is None:
                os.environ.pop("PWD", None)
            else:
                os.environ["PWD"] = old_pwd
        self.assertEqual(rc, 1)
        self.assertFalse((self.store / "word.json").exists())


if __name__ == "__main__":
    unittest.main()
