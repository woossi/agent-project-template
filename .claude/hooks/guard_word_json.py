#!/usr/bin/env python3
"""Claude Code hook guard for the project terminology dictionary."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


WORD_RELATIVE_PATH = Path(".claude/memory/word.json")
DIRECT_EDIT_TOOLS = {"Edit", "Write", "MultiEdit"}


def load_payload() -> dict[str, Any]:
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}


def project_dir(payload: dict[str, Any]) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(raw).expanduser().resolve()


def iter_tool_paths(tool_input: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    return paths


def is_word_json(path_value: str, root: Path) -> bool:
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        relative = candidate.resolve().relative_to(root)
    except ValueError:
        return False
    return relative == WORD_RELATIVE_PATH


def validate_word_json(root: Path) -> int:
    script = root / ".claude/skills/register-term/scripts/register_term.py"
    word_file = root / WORD_RELATIVE_PATH
    if not script.exists():
        print(f"register-term validator not found: {script}", file=sys.stderr)
        return 2

    result = subprocess.run(
        ["python3", str(script), "--word-file", str(word_file), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return 0

    message = result.stderr.strip() or result.stdout.strip()
    if message:
        print(message, file=sys.stderr)
    else:
        print(f"word.json validation failed: {word_file}", file=sys.stderr)
    return 2


def main() -> int:
    payload = load_payload()
    root = project_dir(payload)
    event = payload.get("hook_event_name")
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    if event == "PreToolUse" and tool_name in DIRECT_EDIT_TOOLS:
        if any(is_word_json(path, root) for path in iter_tool_paths(tool_input)):
            print(
                "Blocked direct edit to .claude/memory/word.json. "
                "Use the register-term skill and script so required fields and "
                "duplicates are validated.",
                file=sys.stderr,
            )
            return 2

    if event == "PostToolUse" and tool_name == "Bash":
        return validate_word_json(root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
