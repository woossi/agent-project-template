#!/usr/bin/env python3
"""Team-tier derivation: surface facts that should move into a SHARED team store.

The memory-side sibling of ``detect_team_promotions.py``. The per-agent derivation
loop (``detect_derivations.py``) asks "did one agent see this enough" and moves it
into that agent's private ``user_preferences.md`` / ``word.json``. This asks "do
several peers independently want this shared" and moves it into the TEAM store
(``.project/word.json`` for terms, a shared preferences doc, ``.project/memory/`` for team
decisions). The per-agent loop is left byte-untouched.

Three signal sources, read-only across ``agents/*``:
- **Per-agent ``signals.jsonl``** — the term/preference observations each agent
  already records for its own loop; reused here, aggregated by DISTINCT AGENT.
- **Per-agent ``team-signals.jsonl``** — explicit team signals (incl. ``memory``)
  appended by ``record-team-signal``.
- **``Share:`` markers** in each agent's private ``memory.md`` (``Share: term: <w>`` /
  ``Share: preference: <k>`` / ``Share: memory``). A Share marker is an explicit,
  already-qualifying signal (a deliberate push), so it surfaces immediately even
  from a single agent — mirroring the per-agent ``Derive:`` short-circuit.

Conflict-safe team store, inherited from the reviewed team-promotion detector:
one shared candidate shard + one immutable decision file per ``(kind, key)`` (the
filename carries a hash of the exact key so distinct keys never collide), all via
atomic ``os.replace``. ``find_team_root`` returns ``None`` outside a team checkout so
the SessionStart hook never mints a fake ``.project/`` skeleton.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from team_common.candidate_store import (  # noqa: E402
    canonical_team_runner,
    decision_record_path,
    load_decisions,
    safe_segment,
    write_team_shard,
)
from team_common.identity import identity_from_cwd  # noqa: E402
from team_common.io import atomic_write_json  # noqa: E402
from team_common.paths import find_team_root as _find_team_root  # noqa: E402
from team_common.policy import governance_owner as _governance_owner  # noqa: E402
from team_common.policy import load_policy as _load_policy  # noqa: E402
from team_common.roster import TeamIndex, discover_worker_dirs  # noqa: E402
from _hooklib import (  # noqa: E402
    append_jsonl,
    load_jsonl,
    project_dir_simple as project_dir,
)

DEFAULTS: dict[str, Any] = {
    "agent_ledger": {
        "signals": ".context/memory-log/signals.jsonl",
        "team_signals": ".context/memory-log/team-signals.jsonl",
        "memory": ".claude/memory/memory.md",
    },
    "team_store": {
        "word": ".project/word.json",
        "preferences": ".project/user_preferences.md",
        "memory_dir": ".project/memory",
    },
    "log": {
        "candidates_dir": ".project/derivations/candidates",
        "decisions_dir": ".project/derivations/decisions",
    },
    "term_derivation": {"min_distinct_agents": 2, "skip_if_registered": True, "max_candidates": 20},
    "preference_derivation": {"min_distinct_agents": 2, "skip_if_recorded": True, "max_candidates": 20},
    "memory_derivation": {"min_distinct_agents": 2, "skip_if_recorded": True, "max_candidates": 20},
    "governance": {"mode": "owner-authors", "authoring_owner": "orchestrator"},
}

KINDS = ("term", "preference", "memory")
ENTRY_RE = re.compile(r"^##\s+(.*\S)\s*$")
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s*[-–]\s*")
SHARE_RE = re.compile(r"^Share:\s*(term|preference|memory)\b\s*:?\s*(.*)$", re.IGNORECASE)


# ---------------- roots & policy ----------------

def find_team_root(start: Path) -> Path | None:
    return _find_team_root(start)


def load_policy(team_root: Path) -> dict[str, Any]:
    return _load_policy(team_root / ".project/policies/team-derivation.json", DEFAULTS)


def governance_owner(policy: dict[str, Any]) -> str:
    return _governance_owner(policy, "authoring_owner", default="orchestrator")


def _subteam_members(team_root: Path) -> dict[str, list[str]]:
    return TeamIndex.load(team_root).subteams


def _worker_at(team_root: Path, candidate: Path) -> str | None:
    return TeamIndex.load(team_root).worker_at(candidate)


def _identity_from_cwd(team_root: Path) -> str | None:
    return identity_from_cwd(team_root)


def resolve_actor(team_root: Path, explicit: str | None) -> str:
    cwd_id = _identity_from_cwd(team_root)
    if cwd_id is not None:
        return cwd_id
    return explicit or os.environ.get("CLAUDE_AGENT_NAME") or "team"


# ---------------- readers ----------------

def slugify(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "-", text.strip()).strip("-").lower()


def _is_worker_dir(p: Path) -> bool:
    """A derivation worker is a folder carrying any surface this roll-up reads: a private
    memory-log ledger (.context/memory-log) OR a private memory store (.claude/memory),
    since share markers live in memory.md. Excludes non-worker scratch folders (only
    handoff notes under .context) and TEAM folders — which also hold .claude/memory but
    are explicitly marked with a ``.team-folder`` sentinel so they are never roll-up workers."""
    if not p.is_dir() or p.name.startswith(".") or (p / ".team-folder").exists():
        return False
    return (p / ".context" / "memory-log").is_dir() or (p / ".claude" / "memory").is_dir()


def worker_dirs(team_root: Path) -> dict[str, Path]:
    """Map worker NAME -> folder across both topologies. Names are globally unique."""
    return discover_worker_dirs(team_root, _is_worker_dir)


def list_agents(team_root: Path) -> list[str]:
    return sorted(worker_dirs(team_root))


def memory_share_signals(memory_path: Path, agent: str) -> list[dict[str, Any]]:
    try:
        text = memory_path.read_text(encoding="utf-8")
    except OSError:
        return []
    signals: list[dict[str, Any]] = []
    current_title: str | None = None
    for line in text.splitlines():
        heading = ENTRY_RE.match(line)
        if heading:
            current_title = DATE_PREFIX_RE.sub("", heading.group(1)).strip()
            continue
        marker = SHARE_RE.match(line.strip())
        if not marker or current_title is None:
            continue
        kind = marker.group(1).lower()
        detail = marker.group(2).strip()
        key = (detail or current_title).strip()
        if key:
            signals.append({"kind": kind, "key": key, "note": current_title, "_agent": agent, "explicit": True})
    return signals


def collect_signals(team_root: Path, policy: dict[str, Any]) -> list[dict[str, Any]]:
    rel = policy["agent_ledger"]
    out: list[dict[str, Any]] = []
    for agent, adir in sorted(worker_dirs(team_root).items()):
        for rec in load_jsonl(adir / rel["signals"]):
            rec = dict(rec)
            rec.pop("explicit", None)  # per-agent observations are never team-explicit
            rec["_agent"] = agent
            out.append(rec)
        for rec in load_jsonl(adir / rel["team_signals"]):
            rec = dict(rec)
            rec["_agent"] = agent
            out.append(rec)
        out.extend(memory_share_signals(adir / rel["memory"], agent))
    return out


# ---------------- present-in-team-store checks ----------------

def team_terms(team_root: Path, policy: dict[str, Any]) -> set[str]:
    path = team_root / policy["team_store"]["word"]
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


def team_preferences_text(team_root: Path, policy: dict[str, Any]) -> str:
    path = team_root / policy["team_store"]["preferences"]
    try:
        return path.read_text(encoding="utf-8").lower()
    except OSError:
        return ""


def team_memory_keys(team_root: Path, policy: dict[str, Any]) -> set[str]:
    mdir = team_root / policy["team_store"]["memory_dir"]
    keys: set[str] = set()
    if not mdir.is_dir():
        return keys
    for path in mdir.glob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        key = rec.get("key")
        if isinstance(key, str) and key.strip():
            keys.add(slugify(key))
    return keys


def _preference_present(key: str, pref_text: str) -> bool:
    if not pref_text:
        return False
    normalized = re.sub(r"[-_]+", " ", key.strip().lower())
    return key.strip().lower() in pref_text or (bool(normalized) and normalized in pref_text)


# ---------------- candidate detection (distinct-AGENT axis) ----------------

def _group_signals(signals: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for signal in signals:
        kind = str(signal.get("kind") or "").lower()
        key = str(signal.get("key") or "").strip()
        if kind not in KINDS or not key:
            continue
        # Bucket case-insensitively so two agents writing "LISA"/"lisa" form ONE
        # group (matching register-term's case-insensitive identity); keep the
        # first-seen raw casing for display. Mismatch with the lowercasing
        # presence checks would otherwise split the group and miss the candidate.
        nkey = key.lower()
        group = groups.setdefault(
            (kind, nkey),
            {"kind": kind, "key": key, "nkey": nkey, "count": 0, "agents": set(), "notes": [], "explicit": False},
        )
        group["count"] += 1
        agent = str(signal.get("_agent") or signal.get("agent") or "")
        if agent:
            group["agents"].add(agent)
        note = str(signal.get("note") or "").strip()
        if note and note not in group["notes"]:
            group["notes"].append(note)
        if signal.get("explicit"):
            group["explicit"] = True
    return groups


def derive_candidates(
    signals: list[dict[str, Any]], rules: dict[str, Any], kind: str, is_present, decided: dict[str, Any]
) -> list[dict[str, Any]]:
    groups = {k: v for k, v in _group_signals(signals).items() if k[0] == kind}
    min_agents = int(rules.get("min_distinct_agents", 2))
    skip_present = bool(rules.get("skip_if_registered", rules.get("skip_if_recorded", True)))
    decided_norm = {str(k).strip().lower() for k in decided}  # close mis-cased resolves too

    candidates: list[dict[str, Any]] = []
    for (_, nkey) in sorted(groups):
        group = groups[(kind, nkey)]
        if nkey in decided_norm:
            continue
        if skip_present and is_present(group["key"]):
            continue
        qualifies = group["explicit"] or len(group["agents"]) >= min_agents
        if not qualifies:
            continue
        candidates.append(
            {
                "kind": kind,
                "key": group["key"],
                "recurrence": group["count"],
                "distinct_agents": len(group["agents"]),
                "agents": sorted(group["agents"]),
                "explicit": group["explicit"],
                "notes": group["notes"][:3],
            }
        )
    candidates.sort(key=lambda c: (not c["explicit"], -c["distinct_agents"], c["key"]))
    return candidates[: int(rules.get("max_candidates", 20))]


# ---------------- decisions (per-record immutable, folded) ----------------

def _safe(text: str) -> str:
    return safe_segment(text)


def _roster_members(team_root: Path) -> set[str]:
    """Registered worker identities from .project/team.json (empty set if unreadable)."""
    return TeamIndex.load(team_root).registered_members("orchestrator")


def _validated_runner(team_root: Path, runner: str) -> str:
    """Fold every runner into the canonical team-tier candidate shard.

    Team derivation candidates aggregate shared signals across workers; they do not
    belong to the hook runner that happened to surface them. One ``team.json`` shard
    avoids empty or duplicate per-runner files while decisions remain per ``(kind,key)``.
    """
    return canonical_team_runner(team_root, runner)


def load_team_decisions(decisions_dir: Path) -> dict[str, dict[str, Any]]:
    return load_decisions(decisions_dir, KINDS)


def _atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_json(path, payload)


# ---------------- evaluate / surface / persist ----------------

def evaluate(team_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    signals = collect_signals(team_root, policy)
    decisions = load_team_decisions(team_root / policy["log"]["decisions_dir"])
    terms = team_terms(team_root, policy)
    pref_text = team_preferences_text(team_root, policy)
    mem_keys = team_memory_keys(team_root, policy)
    return {
        "term": derive_candidates(
            signals, policy["term_derivation"], "term", lambda k: k.strip().lower() in terms, decisions["term"]
        ),
        "preference": derive_candidates(
            signals, policy["preference_derivation"], "preference",
            lambda k: _preference_present(k, pref_text), decisions["preference"]
        ),
        "memory": derive_candidates(
            signals, policy["memory_derivation"], "memory", lambda k: slugify(k) in mem_keys, decisions["memory"]
        ),
    }


def write_candidates_shard(team_root: Path, policy: dict[str, Any], candidates: dict[str, Any], runner: str) -> Path:
    return write_team_shard(team_root, policy["log"]["candidates_dir"], candidates, runner)


def format_surface(candidates: dict[str, Any], governance: dict[str, Any]) -> str:
    lines: list[str] = []
    for kind in KINDS:
        for cand in candidates.get(kind, []):
            notes = "; ".join(cand.get("notes", [])) or "(no note)"
            how = "explicit team signal" if cand.get("explicit") else (
                f"{cand['distinct_agents']} agents ({', '.join(cand['agents'])})"
            )
            lines.append(f"- [team_{kind}] '{cand['key']}' ({how}): {notes}")
    if not lines:
        return ""
    owner = governance.get("authoring_owner", "data-curator")
    header = (
        f"Team-derivation conditions were met. Governance: owner {owner}. The owner authors once and closes:\n"
        "- team_term -> register into .project/word.json (register_term.py --word-file; owner serializes the write).\n"
        "- team_preference -> add a dated entry to the team preferences doc.\n"
        "- team_memory -> append an immutable record under .project/memory/.\n"
        "- close with `.claude/hooks/detect_team_derivations.py resolve` (--decision promote|decline).\n"
    )
    return header + "\n".join(lines)


CONTEXT_EVENTS = {"PostToolUse", "PreToolUse", "SessionStart", "UserPromptSubmit", "Stop"}


def emit_hook_context(message: str, event_name: str = "SessionStart") -> None:
    if not message:
        return
    if event_name not in CONTEXT_EVENTS:
        event_name = "SessionStart"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": message}}, ensure_ascii=False))


# ---------------- run modes ----------------

def run_hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    team_root = find_team_root(project_dir(payload))
    if team_root is None:
        return 0
    policy = load_policy(team_root)
    candidates = evaluate(team_root, policy)
    runner = os.environ.get("CLAUDE_AGENT_NAME") or "team"
    write_candidates_shard(team_root, policy, candidates, runner)
    event_name = str(payload.get("hook_event_name") or "SessionStart")
    emit_hook_context(format_surface(candidates, policy.get("governance", {})), event_name)
    return 0


def run_record_team_signal(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_team_derivations.py record-team-signal")
    parser.add_argument("--kind", required=True, choices=list(KINDS))
    parser.add_argument("--key", required=True, help="Stable key (term word / preference slug / memory slug)")
    parser.add_argument("--note", default="", help="Short human-readable note")
    parser.add_argument("--agent", default=None, help="Agent identity (default: $CLAUDE_AGENT_NAME)")
    parser.add_argument("--project-root", default=None, help="The CURRENT agent's root (agents/<name>/)")
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    key = args.key.strip()
    if not key:
        print("error: --key must not be empty", file=sys.stderr)
        return 2
    agent = args.agent if args.agent is not None else (os.environ.get("CLAUDE_AGENT_NAME") or "")
    record = {"kind": args.kind, "key": key, "note": args.note.strip(), "explicit": True}
    if agent:
        record["agent"] = agent
    team_root = find_team_root(root)
    rel = (load_policy(team_root) if team_root else DEFAULTS)["agent_ledger"]["team_signals"]
    path = root / rel
    append_jsonl(path, record)
    print(f"recorded team {args.kind} signal '{key}' -> {path}")
    return 0


def run_evaluate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_team_derivations.py evaluate")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--check", action="store_true", help="Exit 1 when any team-derivation candidate exists")
    args = parser.parse_args(argv)
    start = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    team_root = find_team_root(start)
    if team_root is None:
        print(f"no team root (.project/) found from {start}")
        return 0
    policy = load_policy(team_root)
    candidates = evaluate(team_root, policy)
    runner = os.environ.get("CLAUDE_AGENT_NAME") or "team"
    path = write_candidates_shard(team_root, policy, candidates, runner)
    total = sum(len(candidates[k]) for k in KINDS)
    if args.check and total:
        print(f"{total} team-derivation candidate(s) pending", file=sys.stderr)
        return 1
    print(" / ".join(f"{len(candidates[k])} team_{k}" for k in KINDS) + f" candidate(s) -> {path}")
    return 0


def run_resolve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_team_derivations.py resolve")
    parser.add_argument("--kind", required=True, choices=list(KINDS))
    parser.add_argument("--key", required=True)
    parser.add_argument("--decision", required=True, choices=["promote", "decline"])
    parser.add_argument("--reason", default="")
    parser.add_argument("--by", default=None)
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)
    start = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    team_root = find_team_root(start)
    if team_root is None:
        print(f"no team root (.project/) found from {start}; cannot resolve", file=sys.stderr)
        return 1
    policy = load_policy(team_root)
    by = resolve_actor(team_root, args.by)
    owner = governance_owner(policy)
    if by != owner:
        print(f"only the governance owner '{owner}' may resolve team derivations (you are '{by}')", file=sys.stderr)
        return 1
    record = {
        "kind": args.kind,
        "key": args.key,
        "decision": args.decision,
        "reason": args.reason.strip(),
        "by": by,
        "ts_ns": time.time_ns(),
    }
    path = decision_record_path(team_root / policy["log"]["decisions_dir"], args.kind, args.key)
    _atomic_write_json(path, record)
    write_candidates_shard(team_root, policy, evaluate(team_root, policy), by)
    print(f"resolved {args.kind} '{args.key}' as {args.decision} -> {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "record-team-signal":
        return run_record_team_signal(argv[1:])
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
