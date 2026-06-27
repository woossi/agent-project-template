#!/usr/bin/env python3
"""Team-tier promotion: surface assets that recur across DISTINCT agents.

A sibling of ``detect_promotions.py`` that adds a second tier WITHOUT editing the
per-agent loop. The individual loop asks "did one agent repeat this across sessions"
(``min_distinct_sessions``); this asks "do several peers independently want the same
thing" (``min_distinct_agents``). The two axes are orthogonal: one agent repeating a
signature in three of its own sessions is NOT a team signal.

How it stays conflict-free and non-invasive (per the team-tier plan, all verified):
- **Read-only roll-up.** It reads every ``agents/*/.context/`` ledger read-only and
  never writes into any agent's private ledger, so the per-agent loop is untouched.
- **Distinct-AGENT axis.** Recurrence is keyed on the agent FOLDER name (ground truth
  per the roster), not the session id (which cannot distinguish agents). The
  agent-package detector buckets by agent, not by session (the session bucketing of
  the per-agent ``_occurrences`` would collapse N agents into distinct=1).
- **Per-record immutable team store.** Candidates are written to a per-runner shard
  (``.project/promotions/candidates/<runner>.json``) and decisions to one immutable file
  per ``(kind, key)`` (``.project/promotions/decisions/<kind>__<slug>.json``), both via
  atomic ``os.replace`` — never a single shared JSON array edited by N writers.
- **Single-source sync-back.** ``skip_if_*_exists`` scans the team root
  ``.claude/skills`` / ``.claude/agents`` (the single source symlinked into every
  agent), so a promoted team asset is skipped for everyone at once.

Run modes: hook (stdin payload, SessionStart), ``evaluate`` (CLI inspect), and
``resolve`` (record a promote/decline decision). Hooks never crash the agent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from itertools import combinations
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "agent_ledger": {
        "tasks": ".context/task-log/tasks.jsonl",
        "events": ".context/task-log/events.jsonl",
    },
    "log": {
        "candidates_dir": ".project/promotions/candidates",
        "decisions_dir": ".project/promotions/decisions",
    },
    "team_skill_promotion": {
        "min_distinct_agents": 2,
        "min_total_recurrence": 2,
        "skip_if_skill_exists": True,
        "max_candidates": 20,
    },
    "team_agent_promotion": {
        "min_package_size": 2,
        "min_distinct_agents": 2,
        "skip_if_agent_exists": True,
        "max_candidates": 20,
    },
    "governance": {"mode": "orchestrator-authors", "authoring_owner": "orchestrator"},
}

MAX_SKILLS_PER_OCCURRENCE = 6
KINDS = ("team_skill", "team_agent")
CONTEXT_EVENTS = {"PostToolUse", "PreToolUse", "SessionStart", "UserPromptSubmit", "Stop"}


# ---------------- roots & policy ----------------

def project_dir(payload: dict[str, Any]) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(str(raw)).expanduser().resolve()


def find_team_root(start: Path) -> Path | None:
    """Nearest ancestor (or self) that holds a ``.project/`` directory, else ``None``.

    When run from a peer agent (project root agents/<name>/), walk up to the team
    root; when run from the team root itself, return it. Returning ``None`` when no
    ``.project/`` exists is load-bearing: it stops the SessionStart hook from minting a
    fake ``.project/`` skeleton (and self-pollinating the search) in a non-team clone.
    """
    cur = start.resolve()
    for _ in range(10):
        if (cur / ".project").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _merge(base: dict[str, Any], override: Any) -> dict[str, Any]:
    merged = dict(base)
    if isinstance(override, dict):
        for key, value in override.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = _merge(merged[key], value)
            else:
                merged[key] = value
    return merged


def load_policy(team_root: Path) -> dict[str, Any]:
    policy_path = team_root / ".project/policies/team-promotion.json"
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    return _merge(DEFAULTS, raw)


# ---------------- shared readers (self-contained copies) ----------------

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return records
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def existing_skills(team_root: Path) -> set[str]:
    skills_dir = team_root / ".claude/skills"
    names: set[str] = set()
    if not skills_dir.is_dir():
        return names
    for child in skills_dir.iterdir():
        if child.is_dir() and (child / "SKILL.md").exists():
            names.add(child.name)
    return names


def agent_texts(team_root: Path) -> list[str]:
    agents_dir = team_root / ".claude/agents"
    texts: list[str] = []
    if not agents_dir.is_dir():
        return texts
    for child in sorted(agents_dir.glob("*.md")):
        if child.name == "agents.md":
            continue
        try:
            texts.append(child.read_text(encoding="utf-8"))
        except OSError:
            continue
    return texts


def _covered_by_agent(skills: list[str], texts: list[str]) -> bool:
    return any(all(skill in text for skill in skills) for text in texts)


def _is_worker_dir(p: Path) -> bool:
    """A roll-up worker is a folder carrying a private LEDGER (.context/task-log or
    .context/memory-log). That is the exact surface this roll-up reads, and it cleanly
    excludes non-worker folders that hold only handoff notes under .context (e.g. an
    orchestrator scratch folder) as well as TEAM folders, which are explicitly marked
    with a ``.team-folder`` sentinel so they are never counted as workers."""
    if not p.is_dir() or p.name.startswith(".") or (p / ".team-folder").exists():
        return False
    ctx = p / ".context"
    return (ctx / "task-log").is_dir() or (ctx / "memory-log").is_dir()


def worker_dirs(team_root: Path) -> dict[str, Path]:
    """Map worker NAME -> folder across both topologies (teams/<team>/<w> and agents/<w>).

    Worker names are globally unique, so name is a safe key. See _is_worker_dir for the
    identification rule (ledger-bearing folder)."""
    found: dict[str, Path] = {}
    teams_dir = team_root / "teams"
    if teams_dir.is_dir():
        for team in sorted(teams_dir.iterdir(), key=lambda p: p.name):
            if not team.is_dir() or team.name.startswith("."):
                continue
            for child in sorted(team.iterdir(), key=lambda p: p.name):
                if _is_worker_dir(child):
                    found.setdefault(child.name, child)
    agents_dir = team_root / "agents"
    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir(), key=lambda p: p.name):
            if _is_worker_dir(child):
                found.setdefault(child.name, child)
    return found


def list_agents(team_root: Path) -> list[str]:
    return sorted(worker_dirs(team_root))


def load_agent_ledgers(team_root: Path, policy: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read every peer's private ledger read-only, tagging each record with its agent."""
    rel = policy["agent_ledger"]
    tasks: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for agent, adir in sorted(worker_dirs(team_root).items()):
        for rec in load_jsonl(adir / rel["tasks"]):
            rec = dict(rec)
            rec["_agent"] = agent
            tasks.append(rec)
        for rec in load_jsonl(adir / rel["events"]):
            rec = dict(rec)
            rec["_agent"] = agent
            events.append(rec)
    return tasks, events


# ---------------- candidate detection (distinct-AGENT axis) ----------------

def team_skill_candidates(
    tasks: list[dict[str, Any]], rules: dict[str, Any], skills: set[str], decided: dict[str, Any]
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for task in tasks:
        signature = str(task.get("signature") or "").strip()
        if not signature:
            continue
        group = groups.setdefault(
            signature, {"count": 0, "agents": set(), "objectives": [], "skills": set()}
        )
        group["count"] += 1
        group["agents"].add(str(task.get("_agent") or task.get("agent") or ""))
        objective = str(task.get("objective") or "").strip()
        if objective and objective not in group["objectives"]:
            group["objectives"].append(objective)
        for skill in task.get("skills") or []:
            if isinstance(skill, str) and skill:
                group["skills"].add(skill)

    min_agents = int(rules.get("min_distinct_agents", 2))
    min_total = int(rules.get("min_total_recurrence", 2))
    skip_existing = bool(rules.get("skip_if_skill_exists", True))

    candidates: list[dict[str, Any]] = []
    for signature in sorted(groups):
        group = groups[signature]
        agents = {a for a in group["agents"] if a}
        if skip_existing and signature in skills:
            continue
        if signature in decided:
            continue
        if len(agents) < min_agents or group["count"] < min_total:
            continue
        candidates.append(
            {
                "kind": "team_skill",
                "key": signature,
                "signature": signature,
                "recurrence": group["count"],
                "distinct_agents": len(agents),
                "agents": sorted(agents),
                "objectives": group["objectives"][:3],
                "related_skills": sorted(group["skills"]),
            }
        )
    candidates.sort(key=lambda c: (-c["distinct_agents"], -c["recurrence"], c["key"]))
    return candidates[: int(rules.get("max_candidates", 20))]


def _team_occurrences(
    tasks: list[dict[str, Any]], events: list[dict[str, Any]], min_size: int
) -> list[tuple[str, set[str]]]:
    """Skill bundles keyed by AGENT (not session). Session bucketing here would
    collapse distinct agents into one bucket and break the distinct-agent count."""
    occurrences: list[tuple[str, set[str]]] = []
    for task in tasks:
        skills = {s for s in (task.get("skills") or []) if isinstance(s, str) and s}
        if len(skills) >= min_size:
            occurrences.append((str(task.get("_agent") or ""), skills))

    by_agent: dict[str, set[str]] = {}
    for event in events:
        skill = event.get("skill")
        if isinstance(skill, str) and skill:
            by_agent.setdefault(str(event.get("_agent") or ""), set()).add(skill)
    for agent, skills in by_agent.items():
        if len(skills) >= min_size:
            occurrences.append((agent, skills))
    return occurrences


def team_agent_candidates(
    tasks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    rules: dict[str, Any],
    agent_text_blobs: list[str],
    decided: dict[str, Any],
) -> list[dict[str, Any]]:
    min_size = int(rules.get("min_package_size", 2))
    min_agents = int(rules.get("min_distinct_agents", 2))
    skip_existing = bool(rules.get("skip_if_agent_exists", True))

    occurrences = _team_occurrences(tasks, events, min_size)

    counts: dict[frozenset[str], set[str]] = {}
    for agent, skills in occurrences:
        if not agent:
            continue
        ordered = sorted(skills)[:MAX_SKILLS_PER_OCCURRENCE]
        for size in range(min_size, len(ordered) + 1):
            for combo in combinations(ordered, size):
                counts.setdefault(frozenset(combo), set()).add(agent)

    qualifying = {pkg: agents for pkg, agents in counts.items() if len(agents) >= min_agents}
    keys = list(qualifying)
    maximal = [pkg for pkg in keys if not any(other != pkg and pkg < other for other in keys)]

    candidates: list[dict[str, Any]] = []
    for package in maximal:
        skills = sorted(package)
        key = "+".join(skills)
        if key in decided:
            continue
        if skip_existing and _covered_by_agent(skills, agent_text_blobs):
            continue
        agents = qualifying[package]
        candidates.append(
            {
                "kind": "team_agent",
                "key": key,
                "skills": skills,
                "distinct_agents": len(agents),
                "agents": sorted(agents),
            }
        )
    candidates.sort(key=lambda c: (-c["distinct_agents"], c["key"]))
    return candidates[: int(rules.get("max_candidates", 20))]


# ---------------- decisions (per-record immutable, folded) ----------------

def _safe(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z가-힣._-]+", "_", text).strip("_")
    return (slug or "x")[:120]


def load_team_decisions(decisions_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {kind: {} for kind in KINDS}
    if not decisions_dir.is_dir():
        return out
    for path in sorted(decisions_dir.glob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        kind = rec.get("kind")
        key = rec.get("key")
        if kind in out and isinstance(key, str) and key:
            out[kind][key] = rec
    return out


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# ---------------- evaluate / surface / persist ----------------

def evaluate(team_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    tasks, events = load_agent_ledgers(team_root, policy)
    decisions = load_team_decisions(team_root / policy["log"]["decisions_dir"])
    skills = team_skill_candidates(
        tasks, policy["team_skill_promotion"], existing_skills(team_root), decisions["team_skill"]
    )
    agents = team_agent_candidates(
        tasks, events, policy["team_agent_promotion"], agent_texts(team_root), decisions["team_agent"]
    )
    return {"team_skill": skills, "team_agent": agents}


def write_candidates_shard(team_root: Path, policy: dict[str, Any], candidates: dict[str, Any], runner: str) -> Path:
    path = team_root / policy["log"]["candidates_dir"] / f"{_safe(runner)}.json"
    _atomic_write_json(path, candidates)
    return path


def format_surface(candidates: dict[str, Any], governance: dict[str, Any]) -> str:
    lines: list[str] = []
    for cand in candidates.get("team_skill", []):
        objectives = "; ".join(cand.get("objectives", [])) or "(no objective recorded)"
        lines.append(
            f"- [team_skill] signature '{cand['signature']}' used by "
            f"{cand['distinct_agents']} agents ({', '.join(cand['agents'])}), {cand['recurrence']}x total: {objectives}"
        )
    for cand in candidates.get("team_agent", []):
        package = ", ".join(cand.get("skills", []))
        lines.append(
            f"- [team_agent] skill package [{package}] used by "
            f"{cand['distinct_agents']} agents ({', '.join(cand['agents'])})"
        )
    if not lines:
        return ""
    owner = governance.get("authoring_owner", "orchestrator")
    mode = governance.get("mode", "orchestrator-authors")
    header = (
        "Team-promotion conditions were met (recurs across distinct agents). "
        f"Governance: {mode} (owner: {owner}). Propose via the inbox, then the owner authors once and closes:\n"
        "- team_skill -> author with `write-skill` into the team root .claude/skills (symlinked to all agents).\n"
        "- team_agent -> author with `write-subagent` into the team root .claude/agents.\n"
        "- close with `.claude/hooks/detect_team_promotions.py resolve` (--decision promote|decline).\n"
    )
    return header + "\n".join(lines)


def emit_hook_context(message: str, event_name: str = "SessionStart") -> None:
    if not message:
        return
    if event_name not in CONTEXT_EVENTS:
        event_name = "SessionStart"
    payload = {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": message}}
    print(json.dumps(payload, ensure_ascii=False))


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
        return 0  # not a team checkout: write nothing, surface nothing
    policy = load_policy(team_root)
    candidates = evaluate(team_root, policy)
    runner = os.environ.get("CLAUDE_AGENT_NAME") or "team"
    write_candidates_shard(team_root, policy, candidates, runner)
    event_name = str(payload.get("hook_event_name") or "SessionStart")
    emit_hook_context(format_surface(candidates, policy.get("governance", {})), event_name)
    return 0


def run_evaluate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_team_promotions.py evaluate")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--check", action="store_true", help="Exit 1 when any team candidate exists")
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
    total = len(candidates["team_skill"]) + len(candidates["team_agent"])
    if args.check and total:
        print(f"{total} team-promotion candidate(s) pending", file=sys.stderr)
        return 1
    print(f"{len(candidates['team_skill'])} team_skill / {len(candidates['team_agent'])} team_agent candidate(s) -> {path}")
    return 0


def run_resolve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_team_promotions.py resolve")
    parser.add_argument("--kind", required=True, choices=list(KINDS))
    parser.add_argument("--key", required=True, help="Candidate key (signature or skill+skill)")
    parser.add_argument("--decision", required=True, choices=["promote", "decline"])
    parser.add_argument("--reason", default="")
    parser.add_argument("--by", default=None, help="Who decided (default: $CLAUDE_AGENT_NAME)")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)
    start = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    team_root = find_team_root(start)
    if team_root is None:
        print(f"no team root (.project/) found from {start}; cannot resolve", file=sys.stderr)
        return 1
    policy = load_policy(team_root)
    by = args.by or os.environ.get("CLAUDE_AGENT_NAME") or "team"
    record = {
        "kind": args.kind,
        "key": args.key,
        "decision": args.decision,
        "reason": args.reason.strip(),
        "by": by,
        "ts_ns": time.time_ns(),
    }
    # Filename must be unique per EXACT (kind, key). _safe() is many-to-one, so a
    # short hash of the exact key prevents distinct keys (e.g. "a+b+c" vs "a_b+c")
    # from colliding to one file and silently overwriting each other's decision.
    digest = hashlib.sha1(args.key.encode("utf-8")).hexdigest()[:8]
    filename = f"{args.kind}__{_safe(args.key)}__{digest}.json"
    path = team_root / policy["log"]["decisions_dir"] / filename
    _atomic_write_json(path, record)
    # Refresh this runner's shard so the resolved candidate stops surfacing immediately.
    write_candidates_shard(team_root, policy, evaluate(team_root, policy), by)
    print(f"resolved {args.kind} '{args.key}' as {args.decision} -> {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
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
