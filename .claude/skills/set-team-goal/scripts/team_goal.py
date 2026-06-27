#!/usr/bin/env python3
"""Team goals — the team's top-level context, set by the user, decomposed into Tasks.

A goal is handled SEPARATELY from Apple Reminders. The user sets a goal (with concrete
contract elements); the team then decomposes it into concrete Tasks that achieve it.
Goals are the boundary AND stop condition for the team's work.

Storage: one canonical file per goal at ``<store>/goals/<id>.json`` (id = slug(title)).
The goal file is the single source of truth for that goal; status updates rewrite it
atomically via ``os.replace`` (last-writer-wins; goals are low-contention, typically
set by one agent on the user's behalf). Goal *records* are never a shared append log.

Contract elements (required: title, objective, deliverable, >=1 success_criteria,
>=1 verification) are confirmed with the user before calling this — like register-term,
the CLI enforces presence but never invents content.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any


class GoalError(RuntimeError):
    """Raised on missing contract elements or an unknown goal id."""


def _find_anchored_store(name: str) -> Path:
    """Resolve a relative store name against the team root, not the cwd.

    The CLI is run from anywhere under the repo (agent folders, skill dirs). A
    bare ``.project`` resolved against the cwd lands in the wrong place, so goals and
    tasks get written to or read from a phantom store. For a relative store name
    we walk up from the cwd for a directory containing ``<name>/team.json`` (the
    canonical shared store) and anchor there; otherwise fall back to the
    cwd-relative path (original behaviour) so fresh trees and tests still work.
    """
    cwd = Path.cwd()
    for base in (cwd, *cwd.parents):
        candidate = base / name
        if (candidate / "team.json").is_file():
            return candidate
    return cwd / name


def resolve_store(explicit: str | None) -> Path:
    raw = explicit or os.environ.get("CLAUDE_PROJECT_STORE") or ".project"
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return _find_anchored_store(raw)


def resolve_identity(explicit: str | None) -> str:
    return explicit or os.environ.get("CLAUDE_AGENT_NAME") or "user"


def slugify(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", text.strip()).strip("-").lower()
    return slug or "goal"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def goals_dir(store: Path) -> Path:
    return store / "goals"


def goal_path(store: Path, goal_id: str) -> Path:
    return goals_dir(store) / f"{goal_id}.json"


def set_goal(
    store: Path,
    *,
    title: str,
    objective: str,
    deliverable: str,
    success_criteria: list[str],
    verification: list[str],
    scope: str | None = None,
    constraints: list[str] | None = None,
    by: str = "user",
    clock=time.time_ns,
) -> dict[str, Any]:
    missing = [
        name
        for name, val in (
            ("title", title),
            ("objective", objective),
            ("deliverable", deliverable),
            ("success_criteria", success_criteria),
            ("verification", verification),
        )
        if not val
    ]
    if missing:
        raise GoalError(
            "missing required contract elements: " + ", ".join(missing)
            + " (confirm with the user; never invent goal contract content)"
        )
    goal_id = slugify(title)
    path = goal_path(store, goal_id)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    record = {
        "id": goal_id,
        "title": title,
        "objective": objective,
        "scope": scope,
        "deliverable": deliverable,
        "success_criteria": success_criteria,
        "verification": verification,
        "constraints": constraints or [],
        "status": existing.get("status", "active"),
        "created_by": existing.get("created_by", by),
        "updated_by": by,
        "created_ts_ns": existing.get("created_ts_ns", clock()),
        "updated_ts_ns": clock(),
    }
    _atomic_write_json(path, record)
    return record


def set_status(store: Path, goal_id: str, status: str, *, by: str = "user", clock=time.time_ns) -> dict[str, Any]:
    path = goal_path(store, goal_id)
    if not path.exists():
        raise GoalError(f"goal not found: {goal_id}")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["status"] = status
    record["updated_by"] = by
    record["updated_ts_ns"] = clock()
    _atomic_write_json(path, record)
    return record


def list_goals(store: Path, *, status: str | None = None) -> list[dict[str, Any]]:
    gdir = goals_dir(store)
    if not gdir.exists():
        return []
    out = []
    for p in sorted(gdir.glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        if status is None or rec.get("status") == status:
            out.append(rec)
    return out


def show_goal(store: Path, goal_id: str) -> dict[str, Any]:
    path = goal_path(store, goal_id)
    if not path.exists():
        raise GoalError(f"goal not found: {goal_id}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------- goal -> tasks decomposition ----------------
#
# Decomposition is a JUDGMENT step: the agent decides the tasks; this records each
# one as a team-backlog task linked to the goal and (optionally) a success
# criterion and an assignee. This is the INTERNAL task path (separate from the
# Apple Reminders path); both converge on per-agent assignment. The criterion link
# makes the goal its own stop condition: the goal is done when every criterion is
# covered by a done task.

def tasks_dir(store: Path) -> Path:
    return store / "tasks"


def task_path(store: Path, goal_id: str, task_slug: str) -> Path:
    return tasks_dir(store) / f"{goal_id}__{task_slug}.json"


def decompose(
    store: Path,
    goal_id: str,
    *,
    title: str,
    criterion: str | None = None,
    assignee: str | None = None,
    by: str = "user",
    clock=time.time_ns,
) -> dict[str, Any]:
    if not title.strip():
        raise GoalError("task title must not be empty")
    if not goal_path(store, goal_id).exists():
        raise GoalError(f"goal not found: {goal_id} (set the goal before decomposing it)")
    slug = slugify(title)
    path = task_path(store, goal_id, slug)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    record = {
        "id": f"{goal_id}__{slug}",
        "goal": goal_id,
        "title": title,
        "criterion": criterion,
        "assignee": assignee,
        "status": existing.get("status", "pending"),
        "created_by": existing.get("created_by", by),
        "updated_by": by,
        "created_ts_ns": existing.get("created_ts_ns", clock()),
        "updated_ts_ns": clock(),
    }
    _atomic_write_json(path, record)
    return record


def list_tasks(store: Path, *, goal_id: str | None = None) -> list[dict[str, Any]]:
    tdir = tasks_dir(store)
    if not tdir.exists():
        return []
    out = []
    for p in sorted(tdir.glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        if goal_id is None or rec.get("goal") == goal_id:
            out.append(rec)
    return out


def set_task_status(store: Path, goal_id: str, task_slug: str, status: str, *, by: str = "user", clock=time.time_ns) -> dict[str, Any]:
    path = task_path(store, goal_id, task_slug)
    if not path.exists():
        raise GoalError(f"task not found: {goal_id}__{task_slug}")
    rec = json.loads(path.read_text(encoding="utf-8"))
    rec["status"] = status
    rec["updated_by"] = by
    rec["updated_ts_ns"] = clock()
    _atomic_write_json(path, rec)
    return rec


def goal_progress(store: Path, goal_id: str) -> dict[str, Any]:
    """Stop-condition view: criteria covered by a done task vs total criteria."""
    goal = show_goal(store, goal_id)
    criteria = goal.get("success_criteria", [])
    tasks = list_tasks(store, goal_id=goal_id)
    covered = {t.get("criterion") for t in tasks if t.get("status") == "done" and t.get("criterion")}
    return {
        "goal": goal_id,
        "criteria_total": len(criteria),
        "criteria_covered": sorted(c for c in covered if c in criteria),
        "tasks": len(tasks),
        "tasks_done": sum(1 for t in tasks if t.get("status") == "done"),
        "complete": bool(criteria) and all(c in covered for c in criteria),
    }


# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team_goal.py", description="Team goals (set by user, decomposed into Tasks).")
    parser.add_argument("--store", default=None, help="Shared store dir (default: $CLAUDE_PROJECT_STORE or .project).")
    parser.add_argument("--by", default=None, help="Author (default: $CLAUDE_AGENT_NAME or 'user').")
    sub = parser.add_subparsers(dest="op", required=True)

    p_set = sub.add_parser("set", help="Create or update a goal with its contract elements.")
    p_set.add_argument("--title", required=True)
    p_set.add_argument("--objective", required=True, help="One-sentence outcome.")
    p_set.add_argument("--deliverable", required=True, help="Concrete artifact the goal produces.")
    p_set.add_argument("--success-criteria", action="append", default=[], help="A success criterion (repeatable).")
    p_set.add_argument("--verification", action="append", default=[], help="How success is verified (repeatable).")
    p_set.add_argument("--scope", default=None)
    p_set.add_argument("--constraints", action="append", default=[])

    p_status = sub.add_parser("status", help="Update a goal's status.")
    p_status.add_argument("--id", required=True)
    p_status.add_argument("--set", dest="status", required=True, choices=["pending", "active", "done", "dropped"])

    p_list = sub.add_parser("list", help="List goals (optionally by status).")
    p_list.add_argument("--status", default=None, choices=["pending", "active", "done", "dropped"])

    p_show = sub.add_parser("show", help="Show one goal.")
    p_show.add_argument("--id", required=True)

    p_dec = sub.add_parser("decompose", help="Record a goal-derived task (judgment step) in the team backlog.")
    p_dec.add_argument("--id", required=True, help="Goal id.")
    p_dec.add_argument("--task", required=True, help="Task title.")
    p_dec.add_argument("--criterion", default=None, help="The success_criterion this task covers.")
    p_dec.add_argument("--assign", dest="assignee", default=None, help="Agent assigned to this task.")

    p_tasks = sub.add_parser("tasks", help="List goal-derived tasks.")
    p_tasks.add_argument("--goal", default=None)

    p_ts = sub.add_parser("task-status", help="Update a goal-derived task's status.")
    p_ts.add_argument("--id", required=True, help="Goal id.")
    p_ts.add_argument("--task-slug", required=True, help="Task slug (the part after '<goal>__').")
    p_ts.add_argument("--set", dest="status", required=True, choices=["pending", "in-progress", "done", "dropped"])

    p_prog = sub.add_parser("progress", help="Goal stop-condition view (criteria covered by done tasks).")
    p_prog.add_argument("--id", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = resolve_store(args.store)
    by = resolve_identity(args.by)
    try:
        if args.op == "set":
            result = set_goal(
                store,
                title=args.title,
                objective=args.objective,
                deliverable=args.deliverable,
                success_criteria=args.success_criteria,
                verification=args.verification,
                scope=args.scope,
                constraints=args.constraints,
                by=by,
            )
        elif args.op == "status":
            result = set_status(store, args.id, args.status, by=by)
        elif args.op == "list":
            result = list_goals(store, status=args.status)
        elif args.op == "show":
            result = show_goal(store, args.id)
        elif args.op == "decompose":
            result = decompose(store, args.id, title=args.task, criterion=args.criterion, assignee=args.assignee, by=by)
        elif args.op == "tasks":
            result = list_tasks(store, goal_id=args.goal)
        elif args.op == "task-status":
            result = set_task_status(store, args.id, args.task_slug, args.status, by=by)
        elif args.op == "progress":
            result = goal_progress(store, args.id)
        else:  # pragma: no cover
            raise GoalError(f"unhandled op: {args.op}")
    except GoalError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    json.dump({"ok": True, "op": args.op, "result": result}, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
