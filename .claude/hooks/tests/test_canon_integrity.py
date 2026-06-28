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
        # one index per canon kind (claim/number/provenance + lit_prop/data_registry/runs)
        self.assertEqual(len(written), len(ci.CANON))
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


# ---- S3-S7: new-kind / new-link regression tests --------------------------

class ExtendedTopologyTest(unittest.TestCase):
    """S3 (relations, grounds), S4 (lit_prop, bibkey), S5 (derived_from),
    S6 (data_registry/runs scalar links), S7 (clarity)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".project").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # --- S3: relations (claim -> claim, DAG) + grounds (claim -> lit_prop) ---
    def test_relations_dangling_target_is_error(self) -> None:
        rec = _claim(evidence=())
        rec["relations"] = [{"type": "depends_on", "target": "C999"}]
        _write(self.root, "claim", "C001", rec)
        r = ci.validate(self.root)
        self.assertTrue(any("dangling relation" in e for e in r["errors"]))

    def test_relations_unknown_type_is_error(self) -> None:
        rec = _claim(evidence=())
        rec["relations"] = [{"type": "bogus_rel", "target": "C001"}]
        _write(self.root, "claim", "C001", rec)
        r = ci.validate(self.root)
        self.assertTrue(any("unknown relation type" in e for e in r["errors"]))

    def test_relations_depends_on_cycle_is_error(self) -> None:
        a = _claim("C001", evidence=()); a["relations"] = [{"type": "depends_on", "target": "C002"}]
        b = _claim("C002", evidence=()); b["relations"] = [{"type": "depends_on", "target": "C001"}]
        _write(self.root, "claim", "C001", a)
        _write(self.root, "claim", "C002", b)
        r = ci.validate(self.root)
        self.assertTrue(any("cycle" in e for e in r["errors"]))

    def test_relations_contrasts_with_is_one_way_no_cycle(self) -> None:
        # contrasts_with is stored one-way; a mutual pair must NOT trip the DAG check.
        a = _claim("C001", evidence=()); a["relations"] = [{"type": "contrasts_with", "target": "C002"}]
        b = _claim("C002", evidence=()); b["relations"] = [{"type": "contrasts_with", "target": "C001"}]
        _write(self.root, "claim", "C001", a)
        _write(self.root, "claim", "C002", b)
        r = ci.validate(self.root)
        self.assertFalse(any("cycle" in e for e in r["errors"]))

    def test_claim_grounds_dangling_lit_prop_is_error(self) -> None:
        rec = _claim(evidence=()); rec["grounds"] = ["LP999"]
        _write(self.root, "claim", "C001", rec)
        r = ci.validate(self.root)
        self.assertTrue(any("dangling" in e and "LP999" in e for e in r["errors"]))

    def test_claim_grounds_resolves_to_lit_prop(self) -> None:
        rec = _claim(evidence=()); rec["grounds"] = ["LP001"]
        _write(self.root, "claim", "C001", rec)
        _write(self.root, "lit_prop", "LP001",
               {"lit_prop_id": "LP001", "proposition": "p", "bibkey": "ellen2016",
                "role": "empirical", "status": "core"})
        r = ci.validate(self.root)
        self.assertFalse(any("dangling" in e for e in r["errors"]))

    # --- S4: lit_prop bibkey -> refs.bib ---
    def test_lit_prop_missing_bibkey_is_error(self) -> None:
        _write(self.root, "lit_prop", "LP001",
               {"lit_prop_id": "LP001", "proposition": "p", "role": "empirical", "status": "core"})
        r = ci.validate(self.root)
        self.assertTrue(any("missing bibkey" in e for e in r["errors"]))

    def test_lit_prop_bibkey_unverified_when_no_refs_bib(self) -> None:
        # no refs.bib reachable -> warning (not error), bibkey unverified.
        _write(self.root, "lit_prop", "LP001",
               {"lit_prop_id": "LP001", "proposition": "p", "bibkey": "ghost2020",
                "role": "empirical", "status": "core"})
        r = ci.validate(self.root)
        self.assertFalse(any("dangling bibkey" in e for e in r["errors"]))
        self.assertTrue(any("unverified" in w for w in r["warnings"]))

    def test_lit_prop_bibkey_dangling_against_refs_bib(self) -> None:
        (self.root / "refs.bib").write_text("@article{ellen2016,\n}\n", encoding="utf-8")
        _write(self.root, "lit_prop", "LP001",
               {"lit_prop_id": "LP001", "proposition": "p", "bibkey": "ghost2020",
                "role": "empirical", "status": "core"})
        r = ci.validate(self.root)
        self.assertTrue(any("dangling bibkey" in e for e in r["errors"]))

    # --- S5: derived_from is recognised but NOT dangling-checked ---
    def test_derived_from_is_not_dangling_checked(self) -> None:
        _write(self.root, "claim", "C001", _claim())
        _write(self.root, "number", "N001", _number())
        prov = _prov()
        prov["derived_from"] = {"mailbox_msg": "teams/x/.claude/inbox/m.json",
                                "task": "off/graph/path"}
        _write(self.root, "provenance", "P001", prov)
        r = ci.validate(self.root)
        self.assertEqual(r["errors"], [])

    # --- S6: scalar links source_data -> data_registry, run_id -> runs ---
    def test_unwired_source_data_is_warning_not_error(self) -> None:
        _write(self.root, "claim", "C001", _claim())
        _write(self.root, "number", "N001", _number())
        prov = _prov(); prov["source_data"] = "D001"  # registry empty
        _write(self.root, "provenance", "P001", prov)
        r = ci.validate(self.root)
        self.assertFalse(r["errors"])
        self.assertTrue(any("unwired source_data" in w for w in r["warnings"]))

    def test_source_data_resolves_when_registry_present(self) -> None:
        _write(self.root, "claim", "C001", _claim())
        _write(self.root, "number", "N001", _number())
        prov = _prov(); prov["source_data"] = "D001"
        _write(self.root, "provenance", "P001", prov)
        _write(self.root, "data_registry", "D001",
               {"data_id": "D001", "label": "서울서베이", "manifest_ref": "m", "status": "active"})
        r = ci.validate(self.root)
        self.assertFalse(any("unwired source_data" in w for w in r["warnings"]))

    def test_run_placeholder_is_exempt(self) -> None:
        _write(self.root, "claim", "C001", _claim())
        _write(self.root, "number", "N001", _number())
        prov = _prov(); prov["run_id"] = "RUN-UNSPECIFIED"
        _write(self.root, "provenance", "P001", prov)
        r = ci.validate(self.root)
        self.assertFalse(any("unwired run_id" in w for w in r["warnings"]))

    # --- S7: clarity lexical audit (warnings only) ---
    def test_clarity_audit_flags_overclaimed_causation(self) -> None:
        rec = _claim(evidence=()); rec["claim"] = "저학력은 점수에 영향을 미쳤다."
        _write(self.root, "claim", "C001", rec)
        r = ci.validate(self.root)
        self.assertTrue(any("clarity R9" in w for w in r["warnings"]))
        self.assertFalse(any("clarity" in e for e in r["errors"]))  # never an error

    def test_clarity_audit_silent_on_clean_prose(self) -> None:
        rec = _claim(evidence=()); rec["claim"] = "저학력 집단은 점수가 낮게 나타났다."
        _write(self.root, "claim", "C001", rec)
        r = ci.validate(self.root)
        self.assertFalse(any("clarity" in w for w in r["warnings"]))

    # --- fold over new kinds ---
    def test_fold_covers_all_kinds(self) -> None:
        written = ci.fold(self.root)
        names = {p.name for p in written}
        self.assertIn("lit_props_index.md", names)
        self.assertIn("data_registry_index.md", names)
        self.assertIn("runs_index.md", names)

    def test_fold_claim_sentence_from_components(self) -> None:
        rec = _claim(evidence=())
        rec["components"] = {
            "scope": {"condition": "통제 이전 모형을 기준으로"},
            "target": {"text": "저학력 집단은", "type": "group"},
            "comparison": {"baseline": "대졸 기준집단과 비교할 때"},
            "finding": {"text": "점수가 20점 이상 낮게 나타났다", "closing_verb": "나타났다"},
        }
        s = ci._fold_claim_sentence(rec)
        self.assertIn("저학력 집단은", s)
        self.assertIn("통제 이전", s)


if __name__ == "__main__":
    unittest.main()
