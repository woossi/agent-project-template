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


def normalize_subteams(data: dict[str, Any], members: list[str]) -> list[dict[str, Any]]:
    """Validate and normalize the optional ``subteams`` field (company -> team -> worker).

    Subteams are a LOGICAL grouping layer on top of the flat roster — they do NOT
    change sibling isolation (that stays per-worker N^2). Each subteam binds a set of
    member workers to a Reminders list and a team orchestrator. The strict scope-split
    rule is enforced here: every subteam member must be in the roster, the orchestrator
    must be one of that subteam's members, and a worker belongs to at most one subteam
    (no overlap — the company splits roles across teams without ambiguity).

    Absent/empty ``subteams`` returns ``[]`` and the team stays flat (back-compat).
    """
    raw = data.get("subteams")
    if raw in (None, [], {}):
        return []
    if not isinstance(raw, list):
        raise TeamInitError("subteams must be a list of {name, members, reminders_list?, orchestrator?} objects")

    member_set = set(members)
    seen_workers: dict[str, str] = {}
    seen_names: set[str] = set()
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise TeamInitError("each subteam must be an object")
        name = str(entry.get("name") or "").strip()
        if not name:
            raise TeamInitError("each subteam needs a non-empty 'name'")
        if name in seen_names:
            raise TeamInitError(f"duplicate subteam name '{name}'")
        seen_names.add(name)

        sub_members = entry.get("members")
        if not isinstance(sub_members, list) or not sub_members or not all(isinstance(m, str) and m.strip() for m in sub_members):
            raise TeamInitError(f"subteam '{name}' needs 'members': a non-empty list of worker names")
        sub_members = [m.strip() for m in sub_members]
        for w in sub_members:
            if w not in member_set:
                raise TeamInitError(f"subteam '{name}' member '{w}' is not in the roster {members}")
            if w in seen_workers:
                raise TeamInitError(f"worker '{w}' is in two subteams ('{seen_workers[w]}' and '{name}'); scope split forbids overlap")
            seen_workers[w] = name

        orch = str(entry.get("orchestrator") or "").strip() or sub_members[0]
        if orch not in sub_members:
            raise TeamInitError(f"subteam '{name}' orchestrator '{orch}' must be one of its members {sub_members}")

        reminders_list = entry.get("reminders_list")
        reminders_list = str(reminders_list).strip() if isinstance(reminders_list, str) and reminders_list.strip() else None

        out.append({"name": name, "members": sub_members, "orchestrator": orch, "reminders_list": reminders_list})
    return out


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

    subteams = normalize_subteams(data, members)

    return {
        "team": team,
        "members": members,
        "roles": roles,
        "authoring_owner": owner,
        "min_distinct_agents": min_agents,
        "reminders_list": reminders_list,
        "subteams": subteams,
    }


def build_team_json(setup: dict[str, Any]) -> dict[str, Any]:
    out = {
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
    # Subteams are the logical company -> team -> worker layer. Only emit the key
    # when present so a flat team's team.json stays byte-identical to before.
    if setup.get("subteams"):
        out["subteams"] = setup["subteams"]
    return out


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


def _worker_path(setup: dict[str, Any], name: str) -> str:
    """The repo-relative folder of a worker: teams/<team>/<name> if it's in a subteam,
    else flat agents/<name>. Drives the isolation deny patterns so they point at the
    worker's REAL location regardless of topology."""
    for st in setup.get("subteams") or []:
        if isinstance(st, dict) and name in (st.get("members") or []):
            return f"teams/{st['name']}/{name}"
    return f"agents/{name}"


def build_agent_workspace_policy(setup: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Regenerate the guard's worker-isolation policy from the roster.

    The ``agents`` map is 100% derivable from the members: each worker denies every OTHER
    worker's folder (full N^2 isolation — same-team peers are isolated too, per the strict
    scope-split rule). Deny patterns target each worker's REAL path via _worker_path, so a
    flat tree yields ``agents/<other>/**`` and a 2-tier tree yields ``teams/<team>/<other>/**``.

    Because patterns target worker FOLDERS (not team roots), a worker's own team shared
    resources (``teams/<team>/.claude`` and ``.context``) are NOT denied — they fall outside
    every sibling's worker-folder pattern and stay readable.

    ``defaults`` (the project work boundaries, NOT in team-setup.json) are preserved from the
    existing policy so regeneration never drops a configured allow path.
    """
    members = setup["members"]
    agents = {
        name: {"deny": [f"{_worker_path(setup, other)}/**" for other in members if other != name]}
        for name in members
    }
    base = existing if isinstance(existing, dict) else {}
    defaults = base.get("defaults")
    if not isinstance(defaults, dict):
        defaults = {"allow": ["."], "bash": {"allow": [], "deny": []}, "deny": []}
    version = base.get("version", 1)
    return {"agents": agents, "defaults": defaults, "version": version}


def _load_json_or_none(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


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

    # The guard's sibling-isolation policy is project-scoped (.claude/policies), not in
    # the team store, but its agents map is pure roster output — regenerate it here so it
    # can never drift out of step with the members again. Preserve existing work boundaries.
    workspace_policy_path = team_root / ".claude/policies/agent-workspace.json"
    _atomic_write_json(
        workspace_policy_path,
        build_agent_workspace_policy(setup, _load_json_or_none(workspace_policy_path)),
    )

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
            ".claude/policies/agent-workspace.json",
        ],
        "agents_created": [a.get("name") for a in agents if a.get("created")],
    }


# ---------------- CLI ----------------

def setup_to_input(setup: dict[str, Any]) -> dict[str, Any]:
    """Serialize a normalized setup back to a team-setup.json input shape.

    Only emit ``subteams`` when non-empty so a flat team's saved input stays
    byte-identical to the pre-subteam format (back-compat for existing repos).
    """
    out = {
        "team": setup["team"], "members": setup["members"], "roles": setup["roles"],
        "authoring_owner": setup["authoring_owner"], "min_distinct_agents": setup["min_distinct_agents"],
        "reminders_list": setup["reminders_list"],
    }
    if setup.get("subteams"):
        out["subteams"] = setup["subteams"]
    return out


def add_subteam(team_root: Path, entry: dict[str, Any], *, create_agents: bool = False) -> dict[str, Any]:
    """Incrementally add ONE subteam to the existing team definition.

    Reads the current ``team-setup.json``, appends the new subteam (adding any of
    its members that are not yet in the roster), then re-runs the full normalize +
    init so all derived files (team.json, isolation policy, optional agent scaffolds)
    stay consistent. This is the flexible "grow the company by one team" path — no
    need to hand-rewrite the whole setup JSON.
    """
    setup_path = team_root / "team-setup.json"
    if not setup_path.exists():
        raise TeamInitError(f"no team-setup.json at {setup_path}; run 'init' first")
    data = json.loads(setup_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TeamInitError("existing team-setup.json is not a JSON object")

    if not isinstance(entry, dict):
        raise TeamInitError("subteam to add must be an object")
    name = str(entry.get("name") or "").strip()
    if not name:
        raise TeamInitError("subteam to add needs a non-empty 'name'")

    existing_subteams = data.get("subteams") if isinstance(data.get("subteams"), list) else []
    if any(isinstance(s, dict) and str(s.get("name") or "").strip() == name for s in existing_subteams):
        raise TeamInitError(f"subteam '{name}' already exists")

    sub_members = entry.get("members")
    if not isinstance(sub_members, list) or not sub_members or not all(isinstance(m, str) and m.strip() for m in sub_members):
        raise TeamInitError(f"subteam '{name}' needs 'members': a non-empty list of worker names")
    sub_members = [m.strip() for m in sub_members]

    # Grow the roster with any brand-new workers this subteam introduces (order-stable).
    members = [m.strip() for m in data.get("members", []) if isinstance(m, str) and m.strip()]
    roles = dict(data.get("roles") or {})
    new_roles = entry.get("roles") if isinstance(entry.get("roles"), dict) else {}
    for w in sub_members:
        if w not in members:
            members.append(w)
        if w in new_roles:
            roles[w] = str(new_roles[w])

    data["members"] = members
    data["roles"] = roles
    data["subteams"] = existing_subteams + [{
        k: v for k, v in entry.items() if k in ("name", "members", "orchestrator", "reminders_list")
    }]

    setup = normalize_setup(data)
    _atomic_write_json(setup_path, setup_to_input(setup))
    result = init_team(team_root, setup, create_agents=create_agents)
    result["added_subteam"] = name
    result["subteams"] = [s["name"] for s in setup["subteams"]]
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team_init.py", description="Initialize a team from team-setup.json.")
    sub = parser.add_subparsers(dest="op", required=True)
    p = sub.add_parser("init", help="Write .team/ definition from a team-setup.json (file or stdin).")
    p.add_argument("--input", default=None, help="team-setup.json path (default: stdin).")
    p.add_argument("--team-root", default=None, help="Team root (default: repo root).")
    p.add_argument("--create-agents", action="store_true", help="Also scaffold every member via create-team-agent.")
    p.add_argument("--save-input", dest="save_input", action="store_true", default=True)
    p.add_argument("--no-save-input", dest="save_input", action="store_false", help="Do not write team-setup.json back.")

    a = sub.add_parser("add-subteam", help="Incrementally add ONE subteam (company grows by a team).")
    a.add_argument("--input", default=None, help="JSON for the single subteam {name, members, reminders_list?, orchestrator?, roles?} (default: stdin).")
    a.add_argument("--team-root", default=None, help="Team root (default: repo root).")
    a.add_argument("--create-agents", action="store_true", help="Scaffold any brand-new workers this subteam introduces.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    team_root = Path(args.team_root).expanduser() if args.team_root else default_team_root()
    try:
        if args.op == "add-subteam":
            entry = load_setup(args.input)
            result = add_subteam(team_root, entry, create_agents=args.create_agents)
            json.dump({"ok": True, "op": "add-subteam", "result": result}, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

        setup = normalize_setup(load_setup(args.input))
        if args.save_input:
            _atomic_write_json(team_root / "team-setup.json", setup_to_input(setup))
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
