#!/usr/bin/env python3
"""Apple Reminders <-> Team bridge CLI.

Borrows the Reminders structure as the team work model and syncs with it for real:

    list (목록)     -> Team
    reminder (할일) -> Task   { id, name, completed, priority, due, notes }
    body/notes      -> free-text channel that agents annotate progress into

This is a thin, deterministic CLI over ``reminders.jxa.js`` (a JXA worker run via
``osascript -l JavaScript``). JXA is used so JSON.stringify returns clean UTF-8
JSON for Korean text and ISO Date values; plain AppleScript ``as text`` mojibakes.

Read ops (``list-teams``, ``pull``) are side-effect free. Write ops (``add``,
``complete``, ``reopen``, ``annotate``, ``create-list``, ``delete-list``) mutate
the live Reminders database, so they are explicit subcommands, never defaults.

Runtime requirements:
- macOS with the Reminders app and ``osascript`` (checked at call time).
- Automation/TCC permission to control Reminders for the invoking process. Under
  a sandboxed shell this must run with the sandbox disabled, or it returns -1743.

The CLI exits non-zero and prints ``{"ok": false, "error": ...}`` on any failure,
so callers can branch on the exit code and still parse a JSON explanation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

JXA_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.jxa.js")


class BridgeError(RuntimeError):
    """Raised when the JXA worker cannot be run or returns a failure."""


def run_jxa(command: dict[str, Any], *, runner=None) -> dict[str, Any]:
    """Run the JXA worker with ``command`` as its single JSON argv element.

    ``runner`` is injectable for tests; it takes (argv_list) and returns a
    CompletedProcess-like object exposing ``returncode``/``stdout``/``stderr``.
    """
    payload = json.dumps(command, ensure_ascii=False)
    argv = ["osascript", "-l", "JavaScript", JXA_WORKER, payload]
    runner = runner or _default_runner
    proc = runner(argv)
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 and not out:
        raise BridgeError((proc.stderr or "osascript failed").strip())
    try:
        result = json.loads(out)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise BridgeError(f"non-JSON output from JXA worker: {out!r}") from exc
    if not result.get("ok", False):
        raise BridgeError(result.get("error", "unknown JXA error"))
    return result


def _default_runner(argv: list[str]):
    return subprocess.run(argv, capture_output=True, text=True)


def build_command(args: argparse.Namespace) -> dict[str, Any]:
    """Translate parsed CLI args into a JXA command dict (pure, testable)."""
    op = args.op
    cmd: dict[str, Any] = {"op": op}
    if op == "list-teams":
        return cmd
    if op == "pull":
        cmd["list"] = args.team
        cmd["includeCompleted"] = bool(args.all)
        return cmd
    if op == "add":
        cmd["list"] = args.team
        cmd["name"] = args.name
        if args.notes is not None:
            cmd["notes"] = args.notes
        if args.priority is not None:
            cmd["priority"] = args.priority
        if args.due is not None:
            cmd["due"] = args.due
        return cmd
    if op in ("complete", "reopen"):
        cmd["list"] = args.team
        _attach_selector(cmd, args)
        return cmd
    if op == "annotate":
        cmd["list"] = args.team
        cmd["note"] = args.note
        _attach_selector(cmd, args)
        return cmd
    if op in ("create-list", "delete-list"):
        cmd["list"] = args.team
        return cmd
    raise BridgeError(f"unhandled op: {op}")  # pragma: no cover - argparse guards


def _attach_selector(cmd: dict[str, Any], args: argparse.Namespace) -> None:
    """A task is selected by stable ``--id`` (preferred) or by ``--name``."""
    if getattr(args, "id", None):
        cmd["id"] = args.id
    elif getattr(args, "name", None):
        cmd["name"] = args.name
    else:
        raise BridgeError("select the task with --id (preferred) or --name")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reminders_bridge.py",
        description="Apple Reminders <-> Team bridge (list=Team, reminder=Task).",
    )
    sub = parser.add_subparsers(dest="op", required=True)

    sub.add_parser("list-teams", help="List every Reminders list as a candidate team with open/total counts.")

    p_pull = sub.add_parser("pull", help="Read a team's tasks as JSON (open only by default).")
    p_pull.add_argument("team", help="Reminders list name = team name.")
    p_pull.add_argument("--all", action="store_true", help="Include completed tasks.")

    p_add = sub.add_parser("add", help="Create a task in a team.")
    p_add.add_argument("team")
    p_add.add_argument("name", help="Task title.")
    p_add.add_argument("--notes", default=None)
    p_add.add_argument("--priority", type=int, default=None, help="0 none, 1 high, 5 medium, 9 low.")
    p_add.add_argument("--due", default=None, help="Due date, e.g. 2026-06-30 or 2026-06-30T09:00.")

    for name in ("complete", "reopen"):
        p = sub.add_parser(name, help=f"Mark a task {'done' if name == 'complete' else 'not done'}.")
        p.add_argument("team")
        p.add_argument("--id", default=None, help="Stable reminder id (preferred).")
        p.add_argument("--name", default=None, help="Task title (used if --id absent).")

    p_ann = sub.add_parser("annotate", help="Append a progress note to a task's body channel.")
    p_ann.add_argument("team")
    p_ann.add_argument("note", help="Text appended to the task notes.")
    p_ann.add_argument("--id", default=None)
    p_ann.add_argument("--name", default=None)

    p_cl = sub.add_parser("create-list", help="Create a new list (team). Useful for an isolated sandbox.")
    p_cl.add_argument("team")
    p_dl = sub.add_parser("delete-list", help="Delete a list (team). Irreversible; intended for sandbox cleanup.")
    p_dl.add_argument("team")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        command = build_command(args)
        result = run_jxa(command)
    except BridgeError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
