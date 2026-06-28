#!/usr/bin/env python3
"""Surface durable memory facts that should be derived into a dedicated store.

This hook is the memory side of the same enforced-loop idea that
``detect_promotions.py`` applies to the Tasks -> Skills -> Agents chain. Memory
(``.claude/memory/memory.md``) holds broad durable facts; two narrower stores
specialise them:

- ``.claude/memory/user_preferences.md`` — stable, project-scoped preferences.
- ``.claude/memory/word.json`` — the terminology dictionary (managed via the
  ``register-term`` skill).

A fact that is really a stable preference or a recurring term should move out of
the broad store into the specific one. This hook detects when that condition is
met and re-surfaces the candidate every turn (and at session start) until the
agent derives it and records the outcome with ``resolve`` — or declines it. The
*trigger* is deterministic; the *authoring* stays a judgment step, exactly as in
the promotion loop.

Two deterministic signal sources feed detection:

- **Explicit memory markers.** A ``memory.md`` entry may carry an optional
  ``Derive:`` line (``Derive: preference`` or ``Derive: term: <word>``). Such an
  entry is treated as an explicit, already-qualifying signal: the agent has
  marked it for derivation, so it surfaces immediately.
- **Recorded observations.** ``record-signal`` appends a semantic observation to
  ``signals.jsonl`` (a stable key plus the session id). A key that recurs across
  enough sessions qualifies on the threshold, mirroring how task signatures
  drive skill promotion.

The hook is deterministic, append-only for ``record-signal``, and must never
crash a tool call: any error is swallowed and the process exits 0.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hooklib import (  # noqa: E402
    append_jsonl,
    load_jsonl,
    merge as _merge,
    project_dir_simple as project_dir,
)

DEFAULTS: dict[str, Any] = {
    "log": {
        "signals": ".context/memory-log/signals.jsonl",
        "candidates": ".context/memory-promotions/candidates.json",
        "decisions": ".context/memory-promotions/decisions.json",
    },
    "preference_derivation": {
        "min_recurrence": 2,
        "min_distinct_sessions": 1,
        "skip_if_recorded": True,
        "max_candidates": 20,
    },
    "term_derivation": {
        "min_recurrence": 2,
        "min_distinct_sessions": 1,
        "skip_if_registered": True,
        "max_candidates": 20,
    },
}

KINDS = ("preference", "term")
# Entry heading in memory.md: "## YYYY-MM-DD - Title" (date optional).
ENTRY_RE = re.compile(r"^##\s+(.*\S)\s*$")
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s*[-–]\s*")
# Optional derivation marker line inside an entry body.
DERIVE_RE = re.compile(r"^Derive:\s*(preference|term)\b\s*:?\s*(.*)$", re.IGNORECASE)


def load_policy(root: Path) -> dict[str, Any]:
    policy_path = root / ".claude/policies/derivation.json"
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    return _merge(DEFAULTS, raw)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug


def memory_signals(root: Path) -> list[dict[str, Any]]:
    """Extract explicit ``Derive:`` markers from memory.md as qualifying signals."""
    path = root / ".claude/memory/memory.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    signals: list[dict[str, Any]] = []
    current_title: str | None = None
    for line in text.splitlines():
        heading = ENTRY_RE.match(line)
        if heading:
            current_title = DATE_PREFIX_RE.sub("", heading.group(1)).strip()
            continue
        marker = DERIVE_RE.match(line.strip())
        if not marker or current_title is None:
            continue
        kind = marker.group(1).lower()
        detail = marker.group(2).strip()
        if kind == "term":
            key = detail or current_title
        else:
            key = detail or current_title
        if not key:
            continue
        signals.append(
            {
                "kind": kind,
                "key": key.strip(),
                "note": current_title,
                "session": "memory.md",
                "explicit": True,
            }
        )
    return signals


def existing_terms(root: Path) -> set[str]:
    path = root / ".claude/memory/word.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    terms: set[str] = set()
    if isinstance(data, dict):
        for entry in data.get("terms") or []:
            if isinstance(entry, dict):
                value = entry.get("term")
                if isinstance(value, str) and value.strip():
                    terms.add(value.strip().lower())
    return terms


def existing_preferences_text(root: Path) -> str:
    path = root / ".claude/memory/user_preferences.md"
    try:
        return path.read_text(encoding="utf-8").lower()
    except OSError:
        return ""


def _preference_recorded(key: str, pref_text: str) -> bool:
    if not pref_text:
        return False
    normalized = re.sub(r"[-_]+", " ", key.strip().lower())
    return key.strip().lower() in pref_text or (bool(normalized) and normalized in pref_text)


def _group_signals(signals: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for signal in signals:
        kind = str(signal.get("kind") or "").lower()
        key = str(signal.get("key") or "").strip()
        if kind not in KINDS or not key:
            continue
        group = groups.setdefault(
            (kind, key),
            {"kind": kind, "key": key, "count": 0, "sessions": set(), "notes": [], "explicit": False},
        )
        group["count"] += 1
        group["sessions"].add(str(signal.get("session") or ""))
        note = str(signal.get("note") or "").strip()
        if note and note not in group["notes"]:
            group["notes"].append(note)
        if signal.get("explicit"):
            group["explicit"] = True
    return groups


def derive_candidates(
    signals: list[dict[str, Any]],
    rules: dict[str, Any],
    kind: str,
    is_present,
    decided: dict[str, Any],
) -> list[dict[str, Any]]:
    groups = {k: v for k, v in _group_signals(signals).items() if k[0] == kind}

    min_recurrence = int(rules.get("min_recurrence", 2))
    min_sessions = int(rules.get("min_distinct_sessions", 1))
    skip_present = bool(rules.get("skip_if_registered", rules.get("skip_if_recorded", True)))

    candidates: list[dict[str, Any]] = []
    for (_, key) in sorted(groups):
        group = groups[(kind, key)]
        if key in decided:
            continue
        if skip_present and is_present(key):
            continue
        qualifies = group["explicit"] or (
            group["count"] >= min_recurrence and len(group["sessions"]) >= min_sessions
        )
        if not qualifies:
            continue
        candidates.append(
            {
                "kind": kind,
                "key": key,
                "recurrence": group["count"],
                "distinct_sessions": len(group["sessions"]),
                "explicit": group["explicit"],
                "notes": group["notes"][:3],
            }
        )
    candidates.sort(key=lambda c: (not c["explicit"], -c["recurrence"], c["key"]))
    return candidates[: int(rules.get("max_candidates", 20))]


def load_decisions(path: Path) -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    out: dict[str, dict[str, Any]] = {kind: {} for kind in KINDS}
    if isinstance(raw, dict):
        for kind in KINDS:
            value = raw.get(kind)
            if isinstance(value, dict):
                out[kind] = value
    return out


def evaluate(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    log = policy["log"]
    signals = load_jsonl(root / log["signals"]) + memory_signals(root)
    decisions = load_decisions(root / log["decisions"])
    terms = existing_terms(root)
    pref_text = existing_preferences_text(root)
    preference = derive_candidates(
        signals,
        policy["preference_derivation"],
        "preference",
        lambda key: _preference_recorded(key, pref_text),
        decisions["preference"],
    )
    term = derive_candidates(
        signals,
        policy["term_derivation"],
        "term",
        lambda key: key.strip().lower() in terms,
        decisions["term"],
    )
    return {"preference": preference, "term": term}


def write_candidates(root: Path, policy: dict[str, Any], candidates: dict[str, Any]) -> Path:
    path = root / policy["log"]["candidates"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def format_surface(candidates: dict[str, Any]) -> str:
    lines: list[str] = []
    for cand in candidates.get("preference", []):
        notes = "; ".join(cand.get("notes", [])) or "(no note recorded)"
        seen = "explicit memory marker" if cand.get("explicit") else (
            f"observed {cand['recurrence']}x across {cand['distinct_sessions']} sessions"
        )
        lines.append(f"- [preference] key '{cand['key']}' ({seen}): {notes}")
    for cand in candidates.get("term", []):
        notes = "; ".join(cand.get("notes", [])) or "(no note recorded)"
        seen = "explicit memory marker" if cand.get("explicit") else (
            f"observed {cand['recurrence']}x across {cand['distinct_sessions']} sessions"
        )
        lines.append(f"- [term] '{cand['key']}' ({seen}): {notes}")
    if not lines:
        return ""
    header = (
        "Memory derivation conditions were met. Move each fact into its dedicated "
        "store, then run `.claude/hooks/detect_derivations.py resolve` to clear it:\n"
        "- preference candidate -> add a dated entry to "
        "`.claude/memory/user_preferences.md` (confirm it is stable and project-scoped first).\n"
        "- term candidate -> register with the `register-term` skill "
        "(confirm the four fields with the user; never invent a definition).\n"
        "- not worth deriving -> resolve with `--decision decline --reason ...`.\n"
    )
    return header + "\n".join(lines)


# Events whose hookSpecificOutput supports additionalContext (Claude Code hooks).
CONTEXT_EVENTS = {"PostToolUse", "PreToolUse", "SessionStart", "UserPromptSubmit", "Stop"}


def emit_hook_context(message: str, event_name: str = "PostToolUse") -> None:
    if not message:
        return
    # hookSpecificOutput.hookEventName must exactly match the firing event.
    if event_name not in CONTEXT_EVENTS:
        event_name = "PostToolUse"
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": message,
        }
    }
    print(json.dumps(payload, ensure_ascii=False))


def run_hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    root = project_dir(payload)
    policy = load_policy(root)
    candidates = evaluate(root, policy)
    write_candidates(root, policy, candidates)
    event_name = str(payload.get("hook_event_name") or "PostToolUse")
    emit_hook_context(format_surface(candidates), event_name)
    return 0


def run_record_signal(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_derivations.py record-signal")
    parser.add_argument("--kind", required=True, choices=list(KINDS))
    parser.add_argument("--key", required=True, help="Stable key (preference slug or term word)")
    parser.add_argument("--session", default="", help="Session id for distinct-session counting")
    parser.add_argument("--note", default="", help="Short human-readable note")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)

    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    key = args.key.strip()
    if not key:
        print("error: --key must not be empty", file=sys.stderr)
        return 2
    record = {
        "kind": args.kind,
        "key": key,
        "session": args.session,
        "note": args.note.strip(),
    }
    policy = load_policy(root)
    append_jsonl(root / policy["log"]["signals"], record)
    print(f"recorded {args.kind} signal '{key}' -> {policy['log']['signals']}")
    return 0


def run_evaluate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_derivations.py evaluate")
    parser.add_argument("--project-root", default=None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when any derivation candidate exists (for CI)",
    )
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    policy = load_policy(root)
    candidates = evaluate(root, policy)
    path = write_candidates(root, policy, candidates)
    total = len(candidates["preference"]) + len(candidates["term"])
    if args.check and total:
        print(f"{total} derivation candidate(s) pending", file=sys.stderr)
        return 1
    print(
        f"{len(candidates['preference'])} preference / {len(candidates['term'])} "
        f"term candidate(s) -> {path}"
    )
    return 0


def run_resolve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_derivations.py resolve")
    parser.add_argument("--kind", required=True, choices=list(KINDS))
    parser.add_argument("--key", required=True, help="Candidate key (preference slug or term word)")
    parser.add_argument("--decision", required=True, choices=["promote", "decline"])
    parser.add_argument("--reason", default="")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    policy = load_policy(root)
    path = root / policy["log"]["decisions"]
    decisions = load_decisions(path)
    decisions[args.kind][args.key] = {"decision": args.decision, "reason": args.reason.strip()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(decisions, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # Refresh candidates so the resolved one stops surfacing immediately.
    write_candidates(root, policy, evaluate(root, policy))
    print(f"resolved {args.kind} '{args.key}' as {args.decision}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "record-signal":
        return run_record_signal(argv[1:])
    if argv and argv[0] == "resolve":
        return run_resolve(argv[1:])
    if argv and argv[0] == "evaluate":
        return run_evaluate(argv[1:])
    try:
        return run_hook()
    except Exception:  # noqa: BLE001 - hooks must not crash the agent
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
