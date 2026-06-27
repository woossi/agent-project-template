#!/usr/bin/env python3
"""Auto-capture executed work into the task ledger under .context/task-log/.

This hook makes "the agent automatically records all executed work" a measured
fact instead of a promise. It is wired as a PostToolUse hook in
.claude/settings.json and runs on every Edit/Write/MultiEdit/Bash/Read.

Two record streams are produced:

- ``events.jsonl`` — one compact line per tool action. A Read of any
  ``.claude/skills/<name>/SKILL.md`` is captured as a deterministic *skill usage*
  signal, which lets ``detect_promotions.py`` find skill packages that are used
  together without any semantic judgment.
- ``tasks.jsonl`` — semantic task records appended by the agent through the
  ``record-task`` subcommand (used by the ``write-task`` skill). These carry the
  task signature that drives skill promotion.

The hook is deterministic, append-only, and must never block a tool call: any
error is swallowed and the process exits 0.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

DIRECT_PATH_KEYS = ("file_path", "path", "notebook_path")
SKILL_RE = re.compile(r"(?:^|/)\.claude/skills/([^/]+)/SKILL\.md$")

DEFAULT_LOG = {
    "events": ".context/task-log/events.jsonl",
    "tasks": ".context/task-log/tasks.jsonl",
}


def _find_repo_root(start: Path) -> Path:
    """Walk up from ``start`` to the team repo root.

    The root is the directory that anchors the shared store: it contains
    ``.project/team.json`` (canonical) or, as a fallback, ``AGENTS.md``. Peers run
    hooks from anywhere under the repo (agent folders, skill dirs), so a bare
    cwd is not a reliable anchor. If nothing matches we keep ``start``.
    """
    for base in (start, *start.parents):
        if (base / ".project" / "team.json").is_file():
            return base
    for base in (start, *start.parents):
        if (base / "AGENTS.md").is_file():
            return base
    return start


def project_dir(payload: dict[str, Any]) -> Path:
    """Resolve the per-agent log anchor.

    The task ledger and promotion state are *per-agent private* (each peer is
    isolated to ``agents/<name>/`` and its ``.context`` is not shared). So we
    anchor to the repo root, then descend into ``agents/<CLAUDE_AGENT_NAME>/``
    when an agent identity is set. This keeps every peer's ledger separated no
    matter where the hook fires (the raw cwd / payload cwd is the session root
    for all peers and would otherwise collapse them into the root ``.context``).

    ``CLAUDE_PROJECT_DIR`` supplies the shared repo root when the hook is launched from a
    symlinked worker folder, but it is not the ledger destination. When an agent identity is
    set, descend to that registered worker folder first.
    """
    explicit = os.environ.get("CLAUDE_PROJECT_DIR")
    start = Path(str(payload.get("cwd") or os.getcwd())).expanduser().resolve()
    root = Path(explicit).expanduser().resolve() if explicit else _find_repo_root(start)
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
    copy in detect_promotions.py — both hooks must resolve a worker the same way.
    """
    teams_dir = root / "teams"
    if teams_dir.is_dir():
        for team in teams_dir.iterdir():
            cand = team / agent
            if cand.is_dir():
                return cand
    flat = root / "agents" / agent
    return flat if flat.is_dir() else None


def load_log_paths(root: Path) -> dict[str, str]:
    policy_path = root / ".claude/policies/promotion.json"
    log = dict(DEFAULT_LOG)
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        configured = policy.get("log")
        if isinstance(configured, dict):
            for key in ("events", "tasks"):
                value = configured.get(key)
                if isinstance(value, str) and value:
                    log[key] = value
    except (OSError, json.JSONDecodeError):
        pass
    return log


def relative_path(raw_path: str, root: Path) -> str | None:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        rel = candidate.resolve(strict=False).relative_to(root)
    except ValueError:
        return None
    return rel.as_posix() or "."


def tool_paths(tool_input: dict[str, Any], root: Path) -> list[str]:
    paths: list[str] = []
    for key in DIRECT_PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            rel = relative_path(value, root)
            if rel and rel not in paths:
                paths.append(rel)
    return paths


def skill_from_paths(paths: list[str]) -> str | None:
    for rel in paths:
        match = SKILL_RE.search(rel)
        if match:
            return match.group(1)
    return None


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def build_event(payload: dict[str, Any], root: Path) -> dict[str, Any] | None:
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    paths = tool_paths(tool_input, root)
    skill = skill_from_paths(paths)

    # Only keep Read events that carry a skill-usage signal; raw reads are noise.
    if tool_name == "Read" and skill is None:
        return None

    event: dict[str, Any] = {
        "session": str(payload.get("session_id") or ""),
        "tool": tool_name,
        "paths": paths,
    }
    # Additive, backward-compatible: stamp the agent identity when present so the
    # team-tier detector can count distinct agents. Absent in single-agent mode;
    # the per-agent evaluator ignores unknown keys.
    agent = os.environ.get("CLAUDE_AGENT_NAME") or ""
    if agent:
        event["agent"] = agent
    if skill:
        event["skill"] = skill
    return event


def run_hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    root = project_dir(payload)
    event = build_event(payload, root)
    if event is None:
        return 0
    log = load_log_paths(root)
    append_jsonl(root / log["events"], event)
    return 0


def split_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    for value in values:
        for piece in value.split(","):
            piece = piece.strip()
            if piece and piece not in items:
                items.append(piece)
    return items


def run_record_task(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="task_ledger.py record-task")
    parser.add_argument("--session", default="", help="Session id for distinct-session counting")
    parser.add_argument("--signature", required=True, help="Stable slug describing the task kind")
    parser.add_argument("--objective", default="", help="Short human-readable objective")
    parser.add_argument("--skills", action="append", help="Skill names used (comma-separated or repeated)")
    parser.add_argument("--paths", action="append", help="Primary paths touched (comma-separated or repeated)")
    parser.add_argument(
        "--agent",
        default=None,
        help="Agent identity for distinct-agent team counting (default: $CLAUDE_AGENT_NAME)",
    )
    parser.add_argument(
        "--retro",
        default=None,
        help=(
            "Mandatory one-line retrospective on task completion: was a better result possible / "
            "what to improve. Use 'none' (or '개선없음') when nothing to improve. "
            "A non-empty improvement flags this signature as a worker-skill improvement candidate "
            "(authored by the team lead, not the worker)."
        ),
    )
    parser.add_argument("--project-root", default=None, help="Project root override")
    args = parser.parse_args(argv)

    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    agent = args.agent if args.agent is not None else (os.environ.get("CLAUDE_AGENT_NAME") or "")
    record = {
        "session": args.session,
        "signature": args.signature.strip(),
        "objective": args.objective.strip(),
        "skills": split_list(args.skills),
        "paths": split_list(args.paths),
    }
    if agent:
        record["agent"] = agent
    # Retrospective is optional on the CLI (back-compat: old callers omit it), but
    # the write-task procedure mandates passing it on every completion. When given,
    # store the raw text; detect_promotions reads `retro` to decide whether the
    # signature is a worker-skill *improvement* candidate (non-empty improvement =
    # better result was possible). Sentinels meaning "nothing to improve" normalize
    # to empty so they never raise an improvement candidate.
    if args.retro is not None:
        retro = args.retro.strip()
        if retro.lower() in {"none", "n/a", "-"} or retro in {"개선없음", "없음"}:
            retro = ""
        record["retro"] = retro
    if not record["signature"]:
        print("error: --signature must not be empty", file=sys.stderr)
        return 2
    log = load_log_paths(root)
    append_jsonl(root / log["tasks"], record)
    print(f"recorded task '{record['signature']}' -> {log['tasks']}")
    return 0


def run_record_skill_use(argv: list[str]) -> int:
    """Explicitly stamp a shared-skill use (team-tier fallback, P1.5).

    A peer's ``.claude/skills`` is a symlink to the team root, so a Read of a shared
    ``SKILL.md`` resolves outside the agent root and is NOT path-matched into a
    skill-usage event. This subcommand records the skill use directly so the
    team-tier detector (and the per-agent loop) still see it.
    """
    parser = argparse.ArgumentParser(prog="task_ledger.py record-skill-use")
    parser.add_argument("--skill", required=True, help="Shared skill name that was used")
    parser.add_argument("--session", default="", help="Session id")
    parser.add_argument("--agent", default=None, help="Agent identity (default: $CLAUDE_AGENT_NAME)")
    parser.add_argument("--project-root", default=None, help="Project root override")
    args = parser.parse_args(argv)

    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    skill = args.skill.strip()
    if not skill:
        print("error: --skill must not be empty", file=sys.stderr)
        return 2
    agent = args.agent if args.agent is not None else (os.environ.get("CLAUDE_AGENT_NAME") or "")
    event: dict[str, Any] = {"session": args.session, "tool": "SkillUse", "paths": [], "skill": skill}
    if agent:
        event["agent"] = agent
    log = load_log_paths(root)
    append_jsonl(root / log["events"], event)
    print(f"recorded skill use '{skill}' -> {log['events']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "record-task":
        return run_record_task(argv[1:])
    if argv and argv[0] == "record-skill-use":
        return run_record_skill_use(argv[1:])
    # Hook mode never raises: logging must not break the tool call.
    try:
        return run_hook()
    except Exception:  # noqa: BLE001 - defensive: hooks must not crash the agent
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
