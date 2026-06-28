#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = HOOKS_DIR / "canon_integrity.py"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import canon_integrity as ci  # noqa: E402


def _write(root: Path, kind: str, rid: str, rec: dict) -> Path:
    spec = ci.CANON[kind]
    d = root / spec["dir"]
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{rid}__t.json"
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return p


def _claim(rid="C001", evidence=("N001",), status="verified") -> dict:
    return {"claim_id": rid, "claim": "x", "status": status, "evidence": list(evidence)}


def _number(rid="N001", provenance=("P001",), status="active") -> dict:
    return {"number_id": rid, "value": "0.49%", "label": "l", "provenance": list(provenance), "status": status}


def _prov(rid="P001", related=("C001",), status="active") -> dict:
    return {"artifact_id": rid, "artifact_type": "model_result", "value": "v",
            "related_claims": list(related), "status": status}


class ValidateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".project").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _full_graph(self) -> None:
        _write(self.root, "claim", "C001", _claim())
        _write(self.root, "number", "N001", _number())
        _write(self.root, "provenance", "P001", _prov())

    def test_clean_graph_has_no_errors(self) -> None:
        self._full_graph()
        result = ci.validate(self.root)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["warnings"], [])

    def test_dangling_link_is_error(self) -> None:
        _write(self.root, "claim", "C001", _claim(evidence=("N999",)))
        result = ci.validate(self.root)
        self.assertTrue(any("dangling" in e for e in result["errors"]))

    def test_deprecated_ref_is_error(self) -> None:
        _write(self.root, "claim", "C001", _claim())
        _write(self.root, "number", "N001", _number(status="deprecated"))
        _write(self.root, "provenance", "P001", _prov())
        result = ci.validate(self.root)
        self.assertTrue(any("deprecated ref" in e for e in result["errors"]))

    def test_deprecated_ref_rule_is_referrer_gated(self) -> None:
        # Retiring a sub-graph must not falsely block: a DEPRECATED claim that
        # points at a DEPRECATED number is a self-consistent retirement, so the
        # deprecated-ref rule (active-referrer only) must NOT fire. The number
        # points at no provenance and nothing active references it, so no other
        # rule fires either -> a clean retirement.
        _write(self.root, "claim", "C001", _claim(status="deprecated"))
        _write(self.root, "number", "N001", _number(provenance=(), status="deprecated"))
        result = ci.validate(self.root)
        self.assertFalse(any("deprecated ref" in e for e in result["errors"]))
        self.assertFalse(any("dangling" in e for e in result["errors"]))

    def test_duplicate_id_is_error(self) -> None:
        spec = ci.CANON["claim"]
        d = self.root / spec["dir"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "C001__a.json").write_text(json.dumps(_claim(evidence=())), encoding="utf-8")
        (d / "C001__b.json").write_text(json.dumps(_claim(evidence=())), encoding="utf-8")
        result = ci.validate(self.root)
        self.assertTrue(any("id clash" in e for e in result["errors"]))

    def test_orphan_number_is_warning_not_error(self) -> None:
        # N001 exists but no claim references it; P-less so no dangling.
        _write(self.root, "number", "N001", _number(provenance=()))
        result = ci.validate(self.root)
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("orphan" in w for w in result["warnings"]))

    def test_non_list_link_field_is_error(self) -> None:
        _write(self.root, "claim", "C001", {"claim_id": "C001", "claim": "x",
                                            "status": "draft", "evidence": "N001"})
        result = ci.validate(self.root)
        self.assertTrue(any("must be a list" in e for e in result["errors"]))


class FoldTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".project").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_fold_is_deterministic_and_lists_records(self) -> None:
        _write(self.root, "claim", "C001", _claim(evidence=()))
        first = [p.read_text(encoding="utf-8") for p in ci.fold(self.root)]
        second = [p.read_text(encoding="utf-8") for p in ci.fold(self.root)]
        self.assertEqual(first, second)  # deterministic
        idx = (self.root / ".project/claims/claims_index.md").read_text(encoding="utf-8")
        self.assertIn("C001", idx)
        self.assertIn("do not hand-edit", idx)

    def test_fold_empty_kind_is_safe(self) -> None:
        written = ci.fold(self.root)
        self.assertEqual(len(written), 3)
        idx = (self.root / ".project/numbers/numbers_index.md").read_text(encoding="utf-8")
        self.assertIn("no records", idx)


class GuardCliTest(unittest.TestCase):
    """End-to-end via the actual script (matches the registered hook command)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".project").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _guard(self, file_path: str, tool: str = "Write") -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": file_path},
                              "cwd": str(self.root)})
        return subprocess.run(
            [sys.executable, str(SCRIPT), "guard"],
            input=payload, capture_output=True, text=True,
            env={"CLAUDE_PROJECT_DIR": str(self.root), "PATH": "/usr/bin:/bin"},
        )

    def test_guard_blocks_when_graph_broken(self) -> None:
        _write(self.root, "claim", "C001", _claim(evidence=("N999",)))  # dangling
        r = self._guard(str(self.root / ".project/claims/Cnew.json"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("integrity", r.stderr.lower())

    def test_guard_passes_when_graph_clean(self) -> None:
        _write(self.root, "claim", "C001", _claim(evidence=()))
        r = self._guard(str(self.root / ".project/claims/Cnew.json"))
        self.assertEqual(r.returncode, 0)

    def test_guard_ignores_non_canon_path(self) -> None:
        _write(self.root, "claim", "C001", _claim(evidence=("N999",)))  # broken, but...
        r = self._guard(str(self.root / "scratch.md"))  # ...not a canon path
        self.assertEqual(r.returncode, 0)  # no interference

    def test_guard_ignores_non_edit_tool(self) -> None:
        _write(self.root, "claim", "C001", _claim(evidence=("N999",)))
        r = self._guard(str(self.root / ".project/claims/Cnew.json"), tool="Read")
        self.assertEqual(r.returncode, 0)

    def test_check_exit_code(self) -> None:
        _write(self.root, "claim", "C001", _claim(evidence=("N999",)))
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "check", "--project-root", str(self.root)],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
