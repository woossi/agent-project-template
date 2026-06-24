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


def project_dir(payload: dict[str, Any]) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(str(raw)).expanduser().resolve()


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
    parser.add_argument("--project-root", default=None, help="Project root override")
    args = parser.parse_args(argv)

    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    record = {
        "session": args.session,
        "signature": args.signature.strip(),
        "objective": args.objective.strip(),
        "skills": split_list(args.skills),
        "paths": split_list(args.paths),
    }
    if not record["signature"]:
        print("error: --signature must not be empty", file=sys.stderr)
        return 2
    log = load_log_paths(root)
    append_jsonl(root / log["tasks"], record)
    print(f"recorded task '{record['signature']}' -> {log['tasks']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "record-task":
        return run_record_task(argv[1:])
    # Hook mode never raises: logging must not break the tool call.
    try:
        return run_hook()
    except Exception:  # noqa: BLE001 - defensive: hooks must not crash the agent
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
