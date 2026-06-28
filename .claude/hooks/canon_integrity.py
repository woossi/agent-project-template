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
# as (field_name -> target_kind). Adding data_registry/runs later is one entry.
CANON = {
    "claim": {
        "dir": ".project/claims",
        "id": "claim_id",
        "prefix": "C",
        "links": {"evidence": "number"},
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
        "links": {"related_claims": "claim"},
    },
}
DEPRECATED = {"deprecated", "replaced"}


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

    return {"errors": errors, "warnings": warnings}


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
            head = rec.get("claim", "")
            links = f"evidence={rec.get('evidence', [])}"
            extra = f"used_in={rec.get('used_in', [])} verified_by={rec.get('verified_by', '?')}"
        elif kind == "number":
            head = f"{rec.get('value', '?')} — {rec.get('label', '')}"
            links = f"provenance={rec.get('provenance', [])}"
            extra = f"checked_by={rec.get('checked_by', '?')}"
        else:  # provenance
            head = f"{rec.get('artifact_type', '?')}: {rec.get('value', '')}"
            links = f"related_claims={rec.get('related_claims', [])}"
            extra = f"run_id={rec.get('run_id', '?')} loc={rec.get('manuscript_location', '?')}"
        lines.append(f"## {rid} [{status}]")
        lines.append(f"{head}")
        lines.append(f"- {links}")
        lines.append(f"- {extra}")
        # Reverse link (cited_by): which records point AT this one. Derived, not stored.
        lines.append(f"- cited_by={cited_by}")
        lines.append("")
    return "\n".join(lines) + "\n"


def fold(root: Path) -> list[Path]:
    written: list[Path] = []
    names = {"claim": "claims_index.md", "number": "numbers_index.md",
             "provenance": "provenance_index.md"}
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
