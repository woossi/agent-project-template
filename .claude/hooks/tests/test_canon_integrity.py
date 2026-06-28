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

    # ---- supersedes chaining (canon link type 4) ----

    def test_supersedes_dangling_is_error(self) -> None:
        # New number supersedes a predecessor that does not exist -> dangling.
        rec = _number(rid="N002", provenance=())
        rec["supersedes"] = "N999"
        _write(self.root, "number", "N002", rec)
        result = ci.validate(self.root)
        self.assertTrue(any("dangling supersedes" in e for e in result["errors"]))

    def test_supersedes_active_predecessor_is_warning_not_error(self) -> None:
        # Predecessor exists but is still active -> soft "un-retired predecessor" warning,
        # NOT an error (the deprecated-ref rule must be inverted for supersedes).
        _write(self.root, "number", "N001", _number(provenance=(), status="active"))
        rec = _number(rid="N002", provenance=())
        rec["supersedes"] = "N001"
        _write(self.root, "number", "N002", rec)
        result = ci.validate(self.root)
        self.assertFalse(any("supersedes" in e for e in result["errors"]))
        self.assertTrue(any("un-retired predecessor" in w for w in result["warnings"]))

    def test_supersedes_retired_predecessor_is_clean(self) -> None:
        # Predecessor properly retired (replaced) -> no error, no supersedes warning.
        _write(self.root, "number", "N001", _number(provenance=(), status="replaced"))
        rec = _number(rid="N002", provenance=())
        rec["supersedes"] = "N001"
        _write(self.root, "number", "N002", rec)
        result = ci.validate(self.root)
        self.assertFalse(any("supersedes" in e for e in result["errors"]))
        self.assertFalse(any("un-retired predecessor" in w for w in result["warnings"]))

    def test_self_supersedes_is_error(self) -> None:
        rec = _number(rid="N001", provenance=())
        rec["supersedes"] = "N001"
        _write(self.root, "number", "N001", rec)
        result = ci.validate(self.root)
        self.assertTrue(any("self-supersedes" in e for e in result["errors"]))

    def test_supersedes_null_is_ignored(self) -> None:
        # The default schema value supersedes=null must not trip any rule.
        _write(self.root, "number", "N001", _number(provenance=()))  # supersedes absent
        result = ci.validate(self.root)
        self.assertFalse(any("supersedes" in e for e in result["errors"]))


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

    def test_fold_computes_number_backref_from_claim(self) -> None:
        # claim C001 cites number N001 via evidence; the numbers index must show the
        # reverse link (cited_by=['C001']) WITHOUT N001 storing any back-reference field.
        _write(self.root, "claim", "C001", _claim(evidence=("N001",)))
        _write(self.root, "number", "N001", _number(provenance=()))
        ci.fold(self.root)
        nidx = (self.root / ".project/numbers/numbers_index.md").read_text(encoding="utf-8")
        self.assertIn("cited_by=['C001']", nidx)
        # And the stored record is untouched (no cited_by field persisted).
        rec = json.loads((self.root / ".project/numbers").glob("N001__*.json").__next__().read_text())
        self.assertNotIn("cited_by", rec)

    def test_fold_backref_empty_when_unreferenced(self) -> None:
        _write(self.root, "number", "N001", _number(provenance=()))
        ci.fold(self.root)
        nidx = (self.root / ".project/numbers/numbers_index.md").read_text(encoding="utf-8")
        self.assertIn("cited_by=[]", nidx)

    def test_backrefs_helper_is_deterministic(self) -> None:
        _write(self.root, "claim", "C002", _claim(rid="C002", evidence=("N001",)))
        _write(self.root, "claim", "C001", _claim(rid="C001", evidence=("N001",)))
        _write(self.root, "number", "N001", _number(provenance=()))
        back = ci._backrefs(ci._load_all(self.root))
        # Referrers sorted -> C001 before C002 regardless of file discovery order.
        self.assertEqual(back["number"]["N001"], ["C001", "C002"])


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
