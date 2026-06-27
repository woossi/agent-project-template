#!/usr/bin/env python3
"""Evaluate the task ledger against promotion conditions and force candidates up.

This hook turns the Tasks -> Skills -> Agents promotion chain from a promise into
an enforced loop. It reads the ledger written by ``task_ledger.py``, applies the
concrete thresholds in ``.claude/policies/promotion.json``, and writes the
qualifying candidates to ``.context/promotions/candidates.json``.

In hook mode (PostToolUse, payload on stdin) it also emits ``additionalContext``
so every turn re-surfaces any unresolved candidate. A candidate disappears only
when the agent promotes it (``write-skill`` / ``write-subagent``) and records the
outcome with the ``resolve`` subcommand, or explicitly declines it. The semantic
authoring stays with the agent; the *trigger* is enforced deterministically here.

The judgment boundary is deliberate:

- **Agent candidates** are fully deterministic: a Read of a ``SKILL.md`` is a
  skill-usage signal, so skill packages used together are detected with no
  semantic guess.
- **Skill candidates** come from the semantic task signatures the agent records
  via ``task_ledger.py record-task`` (driven by the ``write-task`` skill); the
  detector enforces the threshold, the agent decides the covering name.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "log": {
        "events": ".context/task-log/events.jsonl",
        "tasks": ".context/task-log/tasks.jsonl",
        "candidates": ".context/promotions/candidates.json",
        "decisions": ".context/promotions/decisions.json",
    },
    "skill_promotion": {
        "min_recurrence": 3,
        "min_distinct_sessions": 2,
        "skip_if_skill_exists": True,
        "max_candidates": 20,
    },
    "agent_promotion": {
        "min_package_size": 2,
        "min_cousage": 3,
        "min_distinct_sessions": 2,
        "skip_if_agent_exists": True,
        "max_candidates": 20,
    },
}

MAX_SKILLS_PER_OCCURRENCE = 6


def _find_repo_root(start: Path) -> Path:
    """Walk up from ``start`` to the team repo root.

    The root anchors the shared store: it contains ``.project/team.json``
    (canonical) or, as a fallback, ``AGENTS.md``. If nothing matches, keep
    ``start``.
    """
    for base in (start, *start.parents):
        if (base / ".project" / "team.json").is_file() or (base / "AGENTS.md").is_file():
            return base
    return start


def project_dir(payload: dict[str, Any]) -> Path:
    """Resolve the per-agent ledger/promotion anchor.

    The ledger and promotion state are per-agent private. Anchor to the repo
    root, then descend into ``agents/<CLAUDE_AGENT_NAME>/`` when an identity is
    set, so every peer's candidates/decisions stay separated regardless of where
    the hook fires. ``CLAUDE_PROJECT_DIR`` remains a hard override when set.

    This must match ``task_ledger.project_dir`` exactly: the ledger writer and
    the promotion reader have to agree on the same ``.context`` directory, or
    candidates are written where the detector never reads them.
    """
    explicit = os.environ.get("CLAUDE_PROJECT_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    start = Path(str(payload.get("cwd") or os.getcwd())).expanduser().resolve()
    root = _find_repo_root(start)
    agent = os.environ.get("CLAUDE_AGENT_NAME") or ""
    if agent:
        agent_root = _agent_root(root, agent)
        if agent_root is not None:
            return agent_root
    return root


def _agent_root(root: Path, agent: str) -> Path | None:
    """The worker's folder under ``root``, supporting both topologies.

    Prefers the 2-tier location ``teams/<team>/<agent>/`` (any team), falls back to the
    flat ``agents/<agent>/``. Returns None if neither exists. Kept byte-identical to the
    copy in task_ledger.py — both hooks must resolve a worker the same way.
    """
    teams_dir = root / "teams"
    if teams_dir.is_dir():
        for team in teams_dir.iterdir():
            cand = team / agent
            if cand.is_dir():
                return cand
    flat = root / "agents" / agent
    return flat if flat.is_dir() else None


def _merge(base: dict[str, Any], override: Any) -> dict[str, Any]:
    merged = dict(base)
    if isinstance(override, dict):
        for key, value in override.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = _merge(merged[key], value)
            else:
                merged[key] = value
    return merged


def load_policy(root: Path) -> dict[str, Any]:
    policy_path = root / ".claude/policies/promotion.json"
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    return _merge(DEFAULTS, raw)


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


def existing_skills(root: Path) -> set[str]:
    skills_dir = root / ".claude/skills"
    names: set[str] = set()
    if not skills_dir.is_dir():
        return names
    for child in skills_dir.iterdir():
        if child.is_dir() and (child / "SKILL.md").exists():
            names.add(child.name)
    return names


def agent_texts(root: Path) -> list[str]:
    agents_dir = root / ".claude/agents"
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


def load_decisions(path: Path) -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    out = {"skill": {}, "agent": {}}
    if isinstance(raw, dict):
        for kind in ("skill", "agent"):
            value = raw.get(kind)
            if isinstance(value, dict):
                out[kind] = value
    return out


def skill_candidates(
    tasks: list[dict[str, Any]],
    rules: dict[str, Any],
    skills: set[str],
    decided: dict[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for task in tasks:
        signature = str(task.get("signature") or "").strip()
        if not signature:
            continue
        group = groups.setdefault(
            signature, {"count": 0, "sessions": set(), "objectives": [], "skills": set()}
        )
        group["count"] += 1
        group["sessions"].add(str(task.get("session") or ""))
        objective = str(task.get("objective") or "").strip()
        if objective and objective not in group["objectives"]:
            group["objectives"].append(objective)
        for skill in task.get("skills") or []:
            if isinstance(skill, str) and skill:
                group["skills"].add(skill)

    min_recurrence = int(rules.get("min_recurrence", 3))
    min_sessions = int(rules.get("min_distinct_sessions", 2))
    skip_existing = bool(rules.get("skip_if_skill_exists", True))

    candidates: list[dict[str, Any]] = []
    for signature in sorted(groups):
        group = groups[signature]
        if skip_existing and signature in skills:
            continue
        if signature in decided:
            continue
        if group["count"] < min_recurrence or len(group["sessions"]) < min_sessions:
            continue
        candidates.append(
            {
                "kind": "skill",
                "key": signature,
                "signature": signature,
                "recurrence": group["count"],
                "distinct_sessions": len(group["sessions"]),
                "objectives": group["objectives"][:3],
                "related_skills": sorted(group["skills"]),
            }
        )
    candidates.sort(key=lambda c: (-c["recurrence"], c["key"]))
    return candidates[: int(rules.get("max_candidates", 20))]


def _occurrences(
    tasks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    min_size: int,
) -> list[tuple[str, set[str]]]:
    occurrences: list[tuple[str, set[str]]] = []
    for task in tasks:
        skills = {s for s in (task.get("skills") or []) if isinstance(s, str) and s}
        if len(skills) >= min_size:
            occurrences.append((str(task.get("session") or ""), skills))

    by_session: dict[str, set[str]] = {}
    for event in events:
        skill = event.get("skill")
        if isinstance(skill, str) and skill:
            by_session.setdefault(str(event.get("session") or ""), set()).add(skill)
    for session, skills in by_session.items():
        if len(skills) >= min_size:
            occurrences.append((session, skills))
    return occurrences


def _covered_by_agent(skills: list[str], texts: list[str]) -> bool:
    return any(all(skill in text for skill in skills) for text in texts)


def agent_candidates(
    tasks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    rules: dict[str, Any],
    agents: list[str],
    decided: dict[str, Any],
) -> list[dict[str, Any]]:
    min_size = int(rules.get("min_package_size", 2))
    min_cousage = int(rules.get("min_cousage", 3))
    min_sessions = int(rules.get("min_distinct_sessions", 2))
    skip_existing = bool(rules.get("skip_if_agent_exists", True))

    occurrences = _occurrences(tasks, events, min_size)

    counts: dict[frozenset[str], dict[str, Any]] = {}
    for session, skills in occurrences:
        ordered = sorted(skills)[:MAX_SKILLS_PER_OCCURRENCE]
        for size in range(min_size, len(ordered) + 1):
            for combo in combinations(ordered, size):
                package = frozenset(combo)
                stat = counts.setdefault(package, {"count": 0, "sessions": set()})
                stat["count"] += 1
                stat["sessions"].add(session)

    qualifying = {
        package: stat
        for package, stat in counts.items()
        if stat["count"] >= min_cousage and len(stat["sessions"]) >= min_sessions
    }
    keys = list(qualifying)
    maximal = [pkg for pkg in keys if not any(other != pkg and pkg < other for other in keys)]

    candidates: list[dict[str, Any]] = []
    for package in maximal:
        skills = sorted(package)
        key = "+".join(skills)
        if key in decided:
            continue
        if skip_existing and _covered_by_agent(skills, agents):
            continue
        stat = qualifying[package]
        candidates.append(
            {
                "kind": "agent",
                "key": key,
                "skills": skills,
                "cousage": stat["count"],
                "distinct_sessions": len(stat["sessions"]),
            }
        )
    candidates.sort(key=lambda c: (-c["cousage"], c["key"]))
    return candidates[: int(rules.get("max_candidates", 20))]


def evaluate(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    log = policy["log"]
    tasks = load_jsonl(root / log["tasks"])
    events = load_jsonl(root / log["events"])
    decisions = load_decisions(root / log["decisions"])
    skills = skill_candidates(
        tasks, policy["skill_promotion"], existing_skills(root), decisions["skill"]
    )
    agents = agent_candidates(
        tasks, events, policy["agent_promotion"], agent_texts(root), decisions["agent"]
    )
    return {"skill": skills, "agent": agents}


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
    for cand in candidates.get("skill", []):
        objectives = "; ".join(cand.get("objectives", [])) or "(no objective recorded)"
        lines.append(
            f"- [skill] signature '{cand['signature']}' recurred {cand['recurrence']}x "
            f"across {cand['distinct_sessions']} sessions: {objectives}"
        )
    for cand in candidates.get("agent", []):
        package = ", ".join(cand.get("skills", []))
        lines.append(
            f"- [agent] skill package [{package}] co-used {cand['cousage']}x "
            f"across {cand['distinct_sessions']} sessions"
        )
    if not lines:
        return ""
    header = (
        "Promotion conditions were met. Act on each candidate, then run "
        "`.claude/hooks/detect_promotions.py resolve` to clear it:\n"
        "- skill candidate -> author with the `write-skill` skill (one covering name).\n"
        "- agent candidate -> author with the `write-subagent` skill (independent context).\n"
        "- not worth promoting -> resolve with `--decision decline --reason ...`.\n"
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


def run_evaluate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_promotions.py evaluate")
    parser.add_argument("--project-root", default=None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when any promotion candidate exists (for CI)",
    )
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    policy = load_policy(root)
    candidates = evaluate(root, policy)
    path = write_candidates(root, policy, candidates)
    total = len(candidates["skill"]) + len(candidates["agent"])
    if args.check and total:
        print(f"{total} promotion candidate(s) pending", file=sys.stderr)
        return 1
    print(f"{len(candidates['skill'])} skill / {len(candidates['agent'])} agent candidate(s) -> {path}")
    return 0


def run_resolve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_promotions.py resolve")
    parser.add_argument("--kind", required=True, choices=["skill", "agent"])
    parser.add_argument("--key", required=True, help="Candidate key (signature or skill+skill)")
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
