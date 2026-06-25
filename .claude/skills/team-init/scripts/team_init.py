#!/usr/bin/env python3
"""Initialize a team from a team-setup.json (the team-DEFINITION conversion step).

Mirrors how ``agent-clone-setup`` turns ``agent-setup.json`` into a converted project
and how ``create-team-agent`` scaffolds one peer — but at the TEAM level. Given a
single ``team-setup.json``, it writes the shared team state:

    .team/team.json                    roster + Reminders binding + goals dir
    .team/policies/team-promotion.json team-tier thresholds + governance owner
    .team/policies/team-derivation.json
    .team/goals/.gitkeep               (durable goal records land here)
    .team/inbox/.gitkeep               (runtime channel; contents git-ignored)

With ``--create-agents`` it also scaffolds every member via create-team-agent, so a
team goes from one JSON file to a runnable Model Y team in one step.

Input is a file (``--input``) or stdin. The normalized input is saved back to
``team-setup.json`` (skip with ``--no-save-input``), exactly like agent-clone-setup.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any


class TeamInitError(RuntimeError):
    """Raised on missing/invalid team-setup fields."""


def default_team_root() -> Path:
    return Path(__file__).resolve().parents[4]


def load_setup(input_path: str | None) -> dict[str, Any]:
    if input_path in (None, "-"):
        text = sys.stdin.read()
    else:
        text = Path(input_path).expanduser().read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TeamInitError(f"team-setup is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TeamInitError("team-setup must be a JSON object")
    return data


def normalize_setup(data: dict[str, Any]) -> dict[str, Any]:
    team = str(data.get("team") or "").strip()
    if not team:
        raise TeamInitError("team-setup needs a non-empty 'team' name")
    members = data.get("members")
    if not isinstance(members, list) or not members or not all(isinstance(m, str) and m.strip() for m in members):
        raise TeamInitError("team-setup needs 'members': a non-empty list of agent names")
    members = [m.strip() for m in members]

    roles = data.get("roles")
    roles = {k: str(v) for k, v in roles.items() if isinstance(k, str)} if isinstance(roles, dict) else {}

    owner = str(data.get("authoring_owner") or "").strip() or members[0]
    if owner not in members:
        raise TeamInitError(f"authoring_owner '{owner}' must be one of members {members}")

    try:
        min_agents = int(data.get("min_distinct_agents", 2))
    except (TypeError, ValueError):
        raise TeamInitError("min_distinct_agents must be an integer")
    if min_agents < 1:
        raise TeamInitError("min_distinct_agents must be >= 1")

    reminders_list = data.get("reminders_list")
    reminders_list = str(reminders_list).strip() if isinstance(reminders_list, str) and reminders_list.strip() else None

    return {
        "team": team,
        "members": members,
        "roles": roles,
        "authoring_owner": owner,
        "min_distinct_agents": min_agents,
        "reminders_list": reminders_list,
    }


def build_team_json(setup: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "team": setup["team"],
        "topology": "model-y",
        "shared_store": ".team",
        "reminders_list": setup["reminders_list"],
        "members": setup["members"],
        "roles": setup["roles"],
        "goals_dir": ".team/goals",
        "inbox": ".team/inbox",
    }


def build_promotion_policy(setup: dict[str, Any]) -> dict[str, Any]:
    n = setup["min_distinct_agents"]
    owner = setup["authoring_owner"]
    return {
        "version": 1,
        "agent_ledger": {"tasks": ".context/task-log/tasks.jsonl", "events": ".context/task-log/events.jsonl"},
        "log": {"candidates_dir": ".team/promotions/candidates", "decisions_dir": ".team/promotions/decisions"},
        "team_skill_promotion": {"min_distinct_agents": n, "min_total_recurrence": 2, "skip_if_skill_exists": True, "max_candidates": 20},
        "team_agent_promotion": {"min_package_size": 2, "min_distinct_agents": n, "skip_if_agent_exists": True, "max_candidates": 20},
        "governance": {"mode": "orchestrator-authors", "authoring_owner": owner},
    }


def build_derivation_policy(setup: dict[str, Any]) -> dict[str, Any]:
    n = setup["min_distinct_agents"]
    owner = setup["authoring_owner"]
    return {
        "version": 1,
        "agent_ledger": {
            "signals": ".context/memory-log/signals.jsonl",
            "team_signals": ".context/memory-log/team-signals.jsonl",
            "memory": ".claude/memory/memory.md",
        },
        "team_store": {"word": ".team/word.json", "preferences": ".team/user_preferences.md", "memory_dir": ".team/memory"},
        "log": {"candidates_dir": ".team/derivations/candidates", "decisions_dir": ".team/derivations/decisions"},
        "term_derivation": {"min_distinct_agents": n, "skip_if_registered": True, "max_candidates": 20},
        "preference_derivation": {"min_distinct_agents": n, "skip_if_recorded": True, "max_candidates": 20},
        "memory_derivation": {"min_distinct_agents": n, "skip_if_recorded": True, "max_candidates": 20},
        "governance": {"mode": "orchestrator-authors", "authoring_owner": owner},
    }


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _create_members(team_root: Path, setup: dict[str, Any]) -> list[dict[str, Any]]:
    scripts = team_root / ".claude/skills/create-team-agent/scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import team_agent  # noqa: E402 - optional dependency, only when --create-agents

    out = []
    for name in setup["members"]:
        out.append(team_agent.create_agent(team_root, name, role=setup["roles"].get(name), force=False))
    return out


def init_team(team_root: Path, setup: dict[str, Any], *, create_agents: bool = False) -> dict[str, Any]:
    store = team_root / ".team"
    _atomic_write_json(store / "team.json", build_team_json(setup))
    _atomic_write_json(store / "policies/team-promotion.json", build_promotion_policy(setup))
    _atomic_write_json(store / "policies/team-derivation.json", build_derivation_policy(setup))
    for keep in ("goals/.gitkeep", "inbox/.gitkeep"):
        p = store / keep
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text("", encoding="utf-8")

    agents = _create_members(team_root, setup) if create_agents else []
    return {
        "team": setup["team"],
        "members": setup["members"],
        "authoring_owner": setup["authoring_owner"],
        "min_distinct_agents": setup["min_distinct_agents"],
        "reminders_list": setup["reminders_list"],
        "files": [
            ".team/team.json",
            ".team/policies/team-promotion.json",
            ".team/policies/team-derivation.json",
        ],
        "agents_created": [a.get("name") for a in agents if a.get("created")],
    }


# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team_init.py", description="Initialize a team from team-setup.json.")
    sub = parser.add_subparsers(dest="op", required=True)
    p = sub.add_parser("init", help="Write .team/ definition from a team-setup.json (file or stdin).")
    p.add_argument("--input", default=None, help="team-setup.json path (default: stdin).")
    p.add_argument("--team-root", default=None, help="Team root (default: repo root).")
    p.add_argument("--create-agents", action="store_true", help="Also scaffold every member via create-team-agent.")
    p.add_argument("--save-input", dest="save_input", action="store_true", default=True)
    p.add_argument("--no-save-input", dest="save_input", action="store_false", help="Do not write team-setup.json back.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    team_root = Path(args.team_root).expanduser() if args.team_root else default_team_root()
    try:
        setup = normalize_setup(load_setup(args.input))
        if args.save_input:
            _atomic_write_json(team_root / "team-setup.json", {
                "team": setup["team"], "members": setup["members"], "roles": setup["roles"],
                "authoring_owner": setup["authoring_owner"], "min_distinct_agents": setup["min_distinct_agents"],
                "reminders_list": setup["reminders_list"],
            })
        result = init_team(team_root, setup, create_agents=args.create_agents)
    except TeamInitError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    json.dump({"ok": True, "op": "init", "result": result}, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
