#!/usr/bin/env python3
"""Argument-integrity canon: link-integrity guard + deterministic fold view.

The heart of ADR-005. The project canon is not 14 independent registries but ONE
linked graph:

    claim C ──evidence──> number N ──provenance──> P ──source──> data D / run RUN

The value of the graph is realised only when links do not break. This module is
the single enforcement point for that, mirroring how ``guard_word_json`` enforces
the word.json schema:

- ``check``    — validate the graph (dangling links, deprecated refs, id clashes,
  orphans). Exit 1 on hard violations (CI / explicit run). Used by ``evaluate``.
- ``guard``    — PreToolUse hook entry. Reads the hook payload; if a tool is about
  to Edit/Write a canon record, re-validates and BLOCKS (exit 2) on a hard
  violation so a broken link never lands. Never crashes a tool call otherwise.
- ``fold``     — regenerate the human-readable index views from the immutable JSON
  records (claims_index.md / numbers_index.md / provenance_index.md). The records
  are the canon; the indexes are a derived view and are never hand-edited.

Records are immutable per-file JSON under ``.project/{claims,numbers,provenance}``
(ADR-005 D1). Standard library only; the hook swallows errors and exits 0 so it
can never break the agent loop (D2 / hook contract).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hooklib import project_dir_simple as project_dir  # noqa: E402

# ---- canon topology -------------------------------------------------------
# Each kind: directory, id field, id prefix, and the outgoing links it carries
# as (field_name -> target_kind). Adding a kind/link is one entry; validate(),
# _backrefs(), fold() and the guard all extend from this table automatically.
#
# Slice history (ADR-canon-unified):
#   S0-2: claim/number/provenance (3 forced links).
#   S3:   claim.grounds/counter_grounds -> lit_prop, claim.relations (claim->claim, DAG).
#   S4:   lit_prop kind (LP) + bibkey -> refs.bib (external SSOT).
#   S5:   provenance.derived_from (lifecycle lineage — recognised but NOT dangling-checked).
#   S6:   data_registry (D) + runs (RUN); provenance.source_data -> D, run_id -> RUN.
#   S7:   clarity-rule lexical audit (R8/R9/R10) on claim/lit_prop prose (warnings).
CANON = {
    "claim": {
        "dir": ".project/claims",
        "id": "claim_id",
        "prefix": "C",
        # evidence -> number (data axis), grounds/counter_grounds -> lit_prop (literature
        # axis). relations (claim->claim) is handled separately (object array).
        "links": {
            "evidence": "number",
            "grounds": "lit_prop",
            "counter_grounds": "lit_prop",
        },
    },
    "number": {
        "dir": ".project/numbers",
        "id": "number_id",
        "prefix": "N",
        "links": {"provenance": "provenance"},
    },
    "provenance": {
        "dir": ".project/provenance",
        "id": "artifact_id",
        "prefix": "P",
        # related_claims -> claim (list). source_data -> data_registry and run_id -> runs
        # are SINGLE strings (scalar links), validated by dedicated passes so they stay
        # scalars in the existing schema. derived_from (lifecycle, off-graph) is recognised
        # but never dangling-checked.
        "links": {
            "related_claims": "claim",
        },
    },
    "lit_prop": {
        "dir": ".project/lit_props",
        "id": "lit_prop_id",
        "prefix": "LP",
        # lit_prop points at no other canon node; its external SSOT link (bibkey ->
        # refs.bib) is verified by a dedicated pass (_validate_bibkeys).
        "links": {},
    },
    "data_registry": {
        "dir": ".project/data_registry",
        "id": "data_id",
        "prefix": "D",
        "links": {},
    },
    "runs": {
        "dir": ".project/runs",
        "id": "run_id",
        "prefix": "RUN",
        "links": {},
    },
}
DEPRECATED = {"deprecated", "replaced"}

# ``run_id`` on a provenance record is a single string id into the runs kind, not a
# list. It is validated by a dedicated pass so it can stay a scalar in the schema.
# The sentinel below is the historical placeholder and is exempt from dangling checks
# until S6 wires real run records (kept so seed records do not falsely block).
RUN_PLACEHOLDERS = {"RUN-UNSPECIFIED", "", None}
# ``source_data`` placeholder sentinels, exempt from dangling checks until S6 wires the
# data_registry. Once a real D-record with the same id exists, the scalar link resolves
# and the warning disappears automatically (no record edit needed).
DATA_PLACEHOLDERS = {"D-UNSPECIFIED", "", None}

# ``derived_from`` (provenance, ADR §C / F-D3 #2) names lifecycle artefacts that live
# OUTSIDE the .project canon graph (worker mailbox/task/memory). canon_integrity does
# NOT dangling-check it — it is recognised as a known field and deliberately skipped, so
# referencing off-graph lineage never blocks a write. File-system access to those paths
# is governed by guard_agent_workspace (orthogonal axis), not here.
OFFGRAPH_FIELDS = {"derived_from"}

# Clarity lexical audit (S7 / clarity-rules R8·R9·R10). Deterministic substring probes
# on canon prose (claim.claim, lit_prop.proposition). Warnings only — judgment stays with
# the writer; the audit flags likely violations for review, it does not block.
CLARITY_LEXICON = {
    # R8 (기능어 감축): weak functional verbs that should be replaced by observable verbs.
    "R8": ["기능한다", "작용한다", "위치한다", "구성된다"],
    # R9 (인과 과장 회피): causal verbs only allowed with a causal design.
    "R9": ["영향을 미쳤다", "영향을 미친다", "효과가 있었다", "초래했다", "야기했다"],
    # R10 (과잉 방어 금지): hedge stacking inside a single result sentence.
    "R10": ["작지만", "보조적으로", "제한적으로", "맥락적으로"],
}


def _load_kind(root: Path, kind: str) -> dict[str, dict[str, Any]]:
    """Map id -> record for one canon kind. Skips unreadable/duplicate-id files."""
    spec = CANON[kind]
    out: dict[str, dict[str, Any]] = {}
    cdir = root / spec["dir"]
    if not cdir.is_dir():
        return out
    for path in sorted(cdir.glob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rec, dict):
            continue
        rid = rec.get(spec["id"])
        if isinstance(rid, str) and rid.strip():
            rec["_file"] = path.name
            out.setdefault(rid.strip(), rec)
            # Record collisions are flagged in validate(), not here, so the
            # second file's data is still visible for the clash report.
            if path.name not in (r.get("_file") for r in [out[rid.strip()]]):
                pass
    return out


def _load_all(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    return {kind: _load_kind(root, kind) for kind in CANON}


def _file_ids(root: Path, kind: str) -> list[tuple[str, str]]:
    """(id, filename) for every record file, to detect duplicate ids."""
    spec = CANON[kind]
    cdir = root / spec["dir"]
    pairs: list[tuple[str, str]] = []
    if not cdir.is_dir():
        return pairs
    for path in sorted(cdir.glob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rid = rec.get(spec["id"]) if isinstance(rec, dict) else None
        if isinstance(rid, str) and rid.strip():
            pairs.append((rid.strip(), path.name))
    return pairs


def validate(root: Path) -> dict[str, list[str]]:
    """Return {"errors": [...], "warnings": [...]}. Errors are hard (block)."""
    graph = _load_all(root)
    errors: list[str] = []
    warnings: list[str] = []

    # 1. duplicate ids within a kind
    for kind in CANON:
        seen: dict[str, str] = {}
        for rid, fname in _file_ids(root, kind):
            if rid in seen:
                errors.append(f"id clash: {kind} '{rid}' in both {seen[rid]} and {fname}")
            else:
                seen[rid] = fname

    referenced: dict[str, set[str]] = {k: set() for k in CANON}
    # 2. dangling links + 3. deprecated refs
    for kind, spec in CANON.items():
        for rid, rec in graph[kind].items():
            # A deprecated/replaced record is already out of the manuscript, so
            # what it points at no longer constrains integrity. The deprecated-ref
            # rule is referrer-gated to active records only; otherwise cleaning up
            # a retired sub-graph would falsely block. Dangling links are still
            # flagged for any referrer (a missing target is always an error).
            referrer_active = str(rec.get("status", "")).lower() not in DEPRECATED
            for field, target_kind in spec["links"].items():
                targets = rec.get(field) or []
                if not isinstance(targets, list):
                    errors.append(f"{kind} '{rid}': field '{field}' must be a list")
                    continue
                for tid in targets:
                    referenced[target_kind].add(tid)
                    tgt = graph[target_kind].get(tid)
                    if tgt is None:
                        errors.append(
                            f"dangling link: {kind} '{rid}'.{field} -> {target_kind} "
                            f"'{tid}' (not found)"
                        )
                    elif referrer_active and str(tgt.get("status", "")).lower() in DEPRECATED:
                        errors.append(
                            f"deprecated ref: active {kind} '{rid}'.{field} -> "
                            f"{target_kind} '{tid}' (status={tgt.get('status')})"
                        )

    # 4. orphans (warning only): a number/provenance no active record points at
    for kind in ("number", "provenance"):
        for rid, rec in graph[kind].items():
            if str(rec.get("status", "")).lower() in DEPRECATED:
                continue
            if rid not in referenced[kind]:
                warnings.append(f"orphan {kind} '{rid}': not referenced by any record")

    # 5. supersedes chaining (ADR §A.4 / canon link type 4). A record's
    # ``supersedes`` names the SAME-kind record it replaces (immutable-record
    # evolution: change = new record + supersedes pointer). This is checked here,
    # NOT via CANON[kind]["links"], on purpose:
    #   * The link target must EXIST (dangling is an error) — same as evidence/provenance.
    #   * But the deprecated-ref rule must be INVERTED: a superseded record is SUPPOSED
    #     to be deprecated/replaced, so reusing the link machinery (which flags an active
    #     referrer -> deprecated target) would fire on every healthy supersession. Hence a
    #     dedicated pass: dangling-only, plus a soft warning when the superseded target is
    #     still active (a likely un-retired predecessor).
    for kind, spec in CANON.items():
        for rid, rec in graph[kind].items():
            sup = rec.get("supersedes")
            if sup is None or sup == "":
                continue
            # supersedes may be a single id (schema default) or a list (chain).
            sup_ids = sup if isinstance(sup, list) else [sup]
            for sid in sup_ids:
                if not isinstance(sid, str) or not sid.strip():
                    continue
                sid = sid.strip()
                if sid == rid:
                    errors.append(f"self-supersedes: {kind} '{rid}'.supersedes -> itself")
                    continue
                tgt = graph[kind].get(sid)
                if tgt is None:
                    errors.append(
                        f"dangling supersedes: {kind} '{rid}'.supersedes -> {kind} "
                        f"'{sid}' (not found)"
                    )
                elif str(tgt.get("status", "")).lower() not in DEPRECATED:
                    warnings.append(
                        f"un-retired predecessor: {kind} '{rid}' supersedes still-active "
                        f"'{sid}' (status={tgt.get('status', '?')}) — retire it (deprecated/replaced)"
                    )

    # 6. scalar links on provenance (run_id -> runs, source_data -> data_registry).
    #    Both are single strings (not lists), so the generic list-link pass skips them.
    #    A real target must exist; placeholders are exempt until S6 wires registries, so
    #    seed records do not falsely block. Unwired = warning (not error) during migration.
    for rid, rec in graph["provenance"].items():
        run = rec.get("run_id")
        if run not in RUN_PLACEHOLDERS and isinstance(run, str) and run.strip():
            if run.strip() not in graph["runs"]:
                warnings.append(
                    f"unwired run_id: provenance '{rid}'.run_id -> runs '{run}' "
                    f"(not found; placeholder until S6)"
                )
        dsrc = rec.get("source_data")
        if isinstance(dsrc, str) and dsrc.strip() and dsrc.strip() not in DATA_PLACEHOLDERS:
            if dsrc.strip() not in graph["data_registry"]:
                warnings.append(
                    f"unwired source_data: provenance '{rid}'.source_data -> data_registry "
                    f"'{dsrc}' (not found; placeholder until S6)"
                )

    # 7. relations cycle check (claim->claim, ADR §B.3 / §E "depends_on DAG"). relations
    #    is an object array [{"type": ..., "target": "C..."}]. depends_on must form a DAG;
    #    a dangling target is an error; contrasts_with/supported_by_lit are stored one-way.
    errors.extend(_validate_relations(graph))

    # 8. external SSOT links: lit_prop.bibkey -> refs.bib. Verified against the bib file
    #    when present; a missing bibkey is an error, a missing refs.bib is a warning (the
    #    bib lives in research/UMC and may be outside an isolated worker's read scope).
    errors2, warns2 = _validate_bibkeys(root, graph)
    errors.extend(errors2)
    warnings.extend(warns2)

    # 9. clarity lexical audit (S7, R8/R9/R10) — warnings only.
    warnings.extend(_clarity_audit(graph))

    return {"errors": errors, "warnings": warnings}


# ---- extra validation passes (S3-S7) --------------------------------------

RELATION_TYPES = {
    "depends_on", "contrasts_with", "limits", "contradicts", "elaborates",
    "supported_by_lit",
}


def _validate_relations(graph: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    """claim.relations object array: dangling-target + depends_on-DAG (cycle) check.

    Each relation is ``{"type": <RELATION_TYPES>, "target": <id>}``. ``supported_by_lit``
    targets a lit_prop; every other type targets a claim. Only ``depends_on`` is required
    to be acyclic (DAG); the rest are stored one-way (fold shows the symmetric view).
    """
    errors: list[str] = []
    claims = graph["claim"]
    deps: dict[str, set[str]] = {}
    for rid, rec in claims.items():
        rels = rec.get("relations") or []
        if not isinstance(rels, list):
            errors.append(f"claim '{rid}': relations must be a list")
            continue
        for rel in rels:
            if not isinstance(rel, dict):
                errors.append(f"claim '{rid}': each relation must be an object")
                continue
            rtype = rel.get("type")
            target = rel.get("target")
            if rtype not in RELATION_TYPES:
                errors.append(f"claim '{rid}': unknown relation type '{rtype}'")
            if not isinstance(target, str) or not target.strip():
                errors.append(f"claim '{rid}': relation '{rtype}' has no target")
                continue
            target = target.strip()
            target_kind = "lit_prop" if rtype == "supported_by_lit" else "claim"
            if target not in graph[target_kind]:
                errors.append(
                    f"dangling relation: claim '{rid}' {rtype} -> {target_kind} "
                    f"'{target}' (not found)"
                )
            if rtype == "depends_on" and target in graph["claim"]:
                deps.setdefault(rid, set()).add(target)
    # cycle detection over depends_on (DFS three-colour).
    WHITE, GREY, BLACK = 0, 1, 2
    color = {c: WHITE for c in claims}

    def _dfs(node: str, stack: list[str]) -> None:
        color[node] = GREY
        for nxt in sorted(deps.get(node, ())):
            if nxt not in color:
                continue
            if color[nxt] == GREY:
                cyc = " -> ".join(stack + [node, nxt])
                errors.append(f"relation cycle (depends_on): {cyc}")
            elif color[nxt] == WHITE:
                _dfs(nxt, stack + [node])
        color[node] = BLACK

    for c in sorted(claims):
        if color.get(c) == WHITE:
            _dfs(c, [])
    return errors


def _read_bibkeys(root: Path) -> set[str] | None:
    """Collect @key entries from refs.bib (research/UMC SSOT). None if unreadable
    (outside read scope / absent) so callers can downgrade to a warning."""
    candidates = [
        root.parent / "research" / "UMC" / "refs.bib",
        root / "refs.bib",
    ]
    for bib in candidates:
        try:
            text = bib.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        keys: set[str] = set()
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("@") and "{" in line:
                key = line.split("{", 1)[1].rstrip(",").strip()
                if key:
                    keys.add(key)
        return keys
    return None


def _validate_bibkeys(
    root: Path, graph: dict[str, dict[str, dict[str, Any]]]
) -> tuple[list[str], list[str]]:
    """lit_prop.bibkey must resolve in refs.bib (external SSOT, complain on dangling)."""
    errors: list[str] = []
    warnings: list[str] = []
    lit = graph.get("lit_prop", {})
    if not lit:
        return errors, warnings
    bibkeys = _read_bibkeys(root)
    for rid, rec in lit.items():
        key = rec.get("bibkey")
        if not isinstance(key, str) or not key.strip():
            errors.append(f"lit_prop '{rid}': missing bibkey (refs.bib SSOT link)")
            continue
        if bibkeys is None:
            warnings.append(
                f"lit_prop '{rid}'.bibkey '{key}': refs.bib not readable here — bibkey "
                f"unverified (outside read scope?)"
            )
        elif key.strip() not in bibkeys:
            errors.append(
                f"dangling bibkey: lit_prop '{rid}'.bibkey -> '{key}' (not in refs.bib)"
            )
    return errors, warnings


def _clarity_audit(graph: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    """Deterministic lexical probes for clarity rules R8/R9/R10 on canon prose.
    Warnings only (judgment stays with the writer). Checks claim.claim and
    lit_prop.proposition for banned-verb substrings."""
    warnings: list[str] = []
    probes = [("claim", "claim"), ("lit_prop", "proposition")]
    for kind, field in probes:
        for rid, rec in graph.get(kind, {}).items():
            text = rec.get(field)
            if not isinstance(text, str) or not text:
                continue
            for rule, terms in CLARITY_LEXICON.items():
                hits = [t for t in terms if t in text]
                if hits:
                    warnings.append(
                        f"clarity {rule}: {kind} '{rid}' uses {hits} — review "
                        f"(R8 weak-verb / R9 overclaimed-causation / R10 hedge-stacking)"
                    )
    return warnings


# ---- fold view ------------------------------------------------------------

def _backrefs(graph: dict[str, dict[str, dict[str, Any]]]) -> dict[str, dict[str, list[str]]]:
    """Compute reverse links per target kind (canon link type 3: back-reference is a
    DERIVED view, never a stored field — ADR §C mechanism 3, "no sync debt").

    For every outgoing link ``referrer.<field> -> target``, record ``target -> [referrers]``.
    Returns ``{target_kind: {target_id: [referrer_id, ...]}}`` with referrers sorted and
    de-duplicated so the fold output is deterministic. The canonical use is
    ``number -> [claim, ...]`` ("which claims cite this number"), the exact reverse of
    ``claim.evidence``; provenance back-refs from numbers come for free the same way.
    """
    back: dict[str, dict[str, set[str]]] = {k: {} for k in CANON}
    for kind, spec in CANON.items():
        for rid, rec in graph[kind].items():
            for field, target_kind in spec["links"].items():
                targets = rec.get(field) or []
                if not isinstance(targets, list):
                    continue
                for tid in targets:
                    if isinstance(tid, str) and tid.strip():
                        back[target_kind].setdefault(tid.strip(), set()).add(rid)
    return {k: {tid: sorted(refs) for tid, refs in d.items()} for k, d in back.items()}


def _fold_one(root: Path, kind: str, backrefs: dict[str, list[str]] | None = None) -> str:
    spec = CANON[kind]
    graph = _load_kind(root, kind)
    backrefs = backrefs or {}
    lines = [
        f"# {kind} index (derived view — do not hand-edit)",
        "",
        f"Regenerated from `{spec['dir']}/*.json` by `canon_integrity.py fold`. "
        "The immutable JSON records are the canon. Back-references (cited_by) are computed, "
        "not stored.",
        "",
    ]
    if not graph:
        lines.append("_(no records)_")
        return "\n".join(lines) + "\n"
    for rid in sorted(graph):
        rec = graph[rid]
        status = rec.get("status", "?")
        cited_by = backrefs.get(rid, [])
        if kind == "claim":
            # Prefer the folded sentence from components when present (S3), else the
            # stored claim string. components are the single source of truth; the
            # sentence is a derived view (ADR §B.3 "claim: <fold from components>").
            head = _fold_claim_sentence(rec) or rec.get("claim", "")
            links = (
                f"evidence={rec.get('evidence', [])} grounds={rec.get('grounds', [])} "
                f"relations={[ (r.get('type'), r.get('target')) for r in (rec.get('relations') or []) if isinstance(r, dict) ]}"
            )
            extra = f"used_in={rec.get('used_in', [])} verified_by={rec.get('verified_by', '?')}"
        elif kind == "number":
            head = f"{rec.get('value', '?')} — {rec.get('label', '')}"
            links = f"provenance={rec.get('provenance', [])}"
            extra = f"checked_by={rec.get('checked_by', '?')}"
        elif kind == "provenance":
            head = f"{rec.get('artifact_type', '?')}: {rec.get('value', '')}"
            links = (
                f"related_claims={rec.get('related_claims', [])} "
                f"source_data={rec.get('source_data', '?')} run_id={rec.get('run_id', '?')}"
            )
            extra = f"loc={rec.get('manuscript_location', '?')}"
        elif kind == "lit_prop":
            head = f"{rec.get('role', '?')}: {rec.get('proposition', '')}"
            links = f"bibkey={rec.get('bibkey', '?')} -> refs.bib"
            extra = f"loc={rec.get('manuscript_location', '?')} argument_step={rec.get('argument_step', '?')}"
        elif kind == "data_registry":
            head = f"{rec.get('label', '')}"
            links = f"manifest_ref={rec.get('manifest_ref', '?')}"
            extra = f"period={rec.get('period', '?')} area={rec.get('area', '?')}"
        else:  # runs
            head = f"{rec.get('label', '')}"
            links = f"script={rec.get('script_or_process', '?')}"
            extra = f"inputs={rec.get('inputs', [])}"
        lines.append(f"## {rid} [{status}]")
        lines.append(f"{head}")
        lines.append(f"- {links}")
        lines.append(f"- {extra}")
        # Reverse link (cited_by): which records point AT this one. Derived, not stored.
        lines.append(f"- cited_by={cited_by}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _fold_claim_sentence(rec: dict[str, Any]) -> str:
    """Derive a claim sentence from its components (S3, ADR §B.3). Deterministic
    template assembly: '[scope.condition] [target] [comparison] [finding].'. Returns ""
    when components are absent so the caller falls back to the stored sentence."""
    comp = rec.get("components")
    if not isinstance(comp, dict) or not comp:
        return ""
    def _txt(slot: str, *keys: str) -> str:
        node = comp.get(slot)
        if not isinstance(node, dict):
            return ""
        for k in keys:
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""
    parts = [
        _txt("scope", "condition", "analysis_basis"),
        _txt("target", "text"),
        _txt("comparison", "baseline", "criterion"),
        _txt("finding", "text"),
    ]
    sentence = " ".join(p for p in parts if p).strip()
    return sentence


def fold(root: Path) -> list[Path]:
    written: list[Path] = []
    names = {
        "claim": "claims_index.md", "number": "numbers_index.md",
        "provenance": "provenance_index.md", "lit_prop": "lit_props_index.md",
        "data_registry": "data_registry_index.md", "runs": "runs_index.md",
    }
    backrefs = _backrefs(_load_all(root))
    for kind, spec in CANON.items():
        cdir = root / spec["dir"]
        cdir.mkdir(parents=True, exist_ok=True)
        path = cdir / names[kind]
        path.write_text(_fold_one(root, kind, backrefs.get(kind, {})), encoding="utf-8")
        written.append(path)
    return written


# ---- guard (PreToolUse) ---------------------------------------------------

CANON_DIRS = tuple(CANON[k]["dir"] for k in CANON)
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _touches_canon(payload: dict[str, Any], root: Path) -> bool:
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return False
    raw = ti.get("file_path") or ti.get("path") or ""
    if not isinstance(raw, str) or not raw:
        return False
    try:
        p = Path(raw).expanduser().resolve()
        rel = p.relative_to(root)
    except (ValueError, OSError):
        return False
    return any(str(rel).startswith(d.replace(".project/", ".project/")) for d in CANON_DIRS) \
        and rel.parts[:1] == (".project",)


def run_guard() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") not in EDIT_TOOLS:
        return 0
    root = project_dir(payload)
    if not _touches_canon(payload, root):
        return 0
    result = validate(root)
    if result["errors"]:
        msg = "Canon integrity violation(s) — fix before writing:\n" + \
            "\n".join(f"  - {e}" for e in result["errors"])
        print(msg, file=sys.stderr)
        return 2
    return 0


# ---- CLI ------------------------------------------------------------------

def run_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="canon_integrity.py check")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    result = validate(root)
    for w in result["warnings"]:
        print(f"WARN  {w}")
    for e in result["errors"]:
        print(f"ERROR {e}", file=sys.stderr)
    print(f"{len(result['errors'])} error(s) / {len(result['warnings'])} warning(s)")
    return 1 if result["errors"] else 0


def run_fold(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="canon_integrity.py fold")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    written = fold(root)
    for p in written:
        print(f"folded -> {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "check":
        return run_check(argv[1:])
    if argv and argv[0] == "fold":
        return run_fold(argv[1:])
    if argv and argv[0] == "guard":
        try:
            return run_guard()
        except Exception:  # noqa: BLE001 - hooks must not crash the agent
            return 0
    # default: behave as the PreToolUse guard (stdin payload)
    try:
        return run_guard()
    except Exception:  # noqa: BLE001
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
