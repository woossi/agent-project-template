#!/usr/bin/env python3
"""Initialize a team from a team-setup.json (the team-DEFINITION conversion step).

Mirrors how ``agent-clone-setup`` turns ``agent-setup.json`` into a converted project
and how ``create-team-agent`` scaffolds one peer — but at the TEAM level. Given a
single ``team-setup.json``, it writes the shared team state:

    .project/team.json                    roster + Reminders binding + goals dir
    .project/policies/team-promotion.json team-tier thresholds + governance owner
    .project/policies/team-derivation.json
    .project/goals/.gitkeep               (durable goal records land here)
    .project/inbox/.gitkeep               (runtime channel; contents git-ignored)

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

        raw_allow = entry.get("allow_paths")
        if raw_allow in (None, []):
            allow_paths: list[str] = []
        elif isinstance(raw_allow, list) and all(isinstance(p, str) and p.strip() for p in raw_allow):
            allow_paths = [p.strip() for p in raw_allow]
        else:
            raise TeamInitError(f"subteam '{name}' allow_paths must be a list of non-empty strings")

        out.append({"name": name, "members": sub_members, "orchestrator": orch,
                    "reminders_list": reminders_list, "allow_paths": allow_paths})
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

    # authoring_owner (= company governance owner). Normally a roster member, but the
    # reserved company total — "orchestrator" — is allowed even though it has no worker
    # folder (it operates via CLI with its identity env; governance権限 is by name, not by a
    # symlinked skill folder). See team-only-inbox spec §5-B.
    owner = str(data.get("authoring_owner") or "").strip() or members[0]
    if owner != "orchestrator" and owner not in members:
        raise TeamInitError(
            f"authoring_owner '{owner}' must be one of members {members} or 'orchestrator'")

    try:
        min_agents = int(data.get("min_distinct_agents", 2))
    except (TypeError, ValueError):
        raise TeamInitError("min_distinct_agents must be an integer")
    if min_agents < 1:
        raise TeamInitError("min_distinct_agents must be >= 1")

    reminders_list = data.get("reminders_list")
    reminders_list = str(reminders_list).strip() if isinstance(reminders_list, str) and reminders_list.strip() else None

    subteams = normalize_subteams(data, members)

    # Optional governance-tier overrides; default split lives in build_promotion_policy.
    def _str_list(key: str) -> list[str] | None:
        v = data.get(key)
        if isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v):
            return [x.strip() for x in v]
        return None

    return {
        "team": team,
        "members": members,
        "roles": roles,
        "authoring_owner": owner,
        "company_skills": _str_list("company_skills"),
        "team_skills": _str_list("team_skills"),
        "min_distinct_agents": min_agents,
        "reminders_list": reminders_list,
        "subteams": subteams,
    }


def build_team_json(setup: dict[str, Any]) -> dict[str, Any]:
    out = {
        "version": 1,
        "team": setup["team"],
        "topology": "model-y",
        "shared_store": ".project",
        "reminders_list": setup["reminders_list"],
        "members": setup["members"],
        "roles": setup["roles"],
        "goals_dir": ".project/goals",
        "inbox_model": "team-only",
        "team_inbox_glob": "teams/<team>/.claude/inbox",
        "orchestrator_inbox": "teams/.orchestrator/inbox",
        "legacy_inbox_archive": ".project/inbox/.archive",
    }
    # Subteams are the logical company -> team -> worker layer. Only emit the key
    # when present so a flat team's team.json stays byte-identical to before.
    # ``allow_paths`` is a workspace-policy concern (it flows into agent-workspace.json),
    # not a roster concern, so it is dropped from team.json to keep the two stores'
    # responsibilities separate. Empty allow_paths is omitted entirely.
    if setup.get("subteams"):
        out["subteams"] = [
            {k: v for k, v in s.items() if k in ("name", "members", "orchestrator", "reminders_list")}
            for s in setup["subteams"]
        ]
    return out


# Default tiered governance split (user decision 2026-06-27, "거버넌스 팀장 분산"):
# COMPANY-tier stays with the single company owner; TEAM-tier is distributed to each
# subteam orchestrator (team lead). team-setup.json may override either list.
DEFAULT_COMPANY_SKILLS = ["team-init", "agent-clone-setup"]
DEFAULT_TEAM_SKILLS = ["create-team-agent", "set-team-goal", "team-derive-author"]


def _governance_block(setup: dict[str, Any]) -> dict[str, Any]:
    """Tiered governance for team-promotion.json. ``authoring_owner`` is kept as the legacy
    alias of ``company_owner`` so older readers (team-derivation.json, _company_owner's
    fallback) keep working unchanged."""
    owner = setup["authoring_owner"]
    return {
        "mode": "tiered",
        "company_owner": owner,
        "authoring_owner": owner,  # legacy alias, back-compat
        "company_skills": list(setup.get("company_skills") or DEFAULT_COMPANY_SKILLS),
        "team_skills": list(setup.get("team_skills") or DEFAULT_TEAM_SKILLS),
    }


def build_promotion_policy(setup: dict[str, Any]) -> dict[str, Any]:
    n = setup["min_distinct_agents"]
    return {
        "version": 1,
        "agent_ledger": {"tasks": ".context/task-log/tasks.jsonl", "events": ".context/task-log/events.jsonl"},
        "log": {"candidates_dir": ".project/promotions/candidates", "decisions_dir": ".project/promotions/decisions"},
        "team_skill_promotion": {"min_distinct_agents": n, "min_total_recurrence": 2, "skip_if_skill_exists": True, "max_candidates": 20},
        "team_agent_promotion": {"min_package_size": 2, "min_distinct_agents": n, "skip_if_agent_exists": True, "max_candidates": 20},
        "governance": _governance_block(setup),
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
        "team_store": {"word": ".project/word.json", "preferences": ".project/user_preferences.md", "memory_dir": ".project/memory"},
        "log": {"candidates_dir": ".project/derivations/candidates", "decisions_dir": ".project/derivations/decisions"},
        "term_derivation": {"min_distinct_agents": n, "skip_if_registered": True, "max_candidates": 20},
        "preference_derivation": {"min_distinct_agents": n, "skip_if_recorded": True, "max_candidates": 20},
        "memory_derivation": {"min_distinct_agents": n, "skip_if_recorded": True, "max_candidates": 20},
        "governance": {"mode": "orchestrator-authors", "authoring_owner": owner},
    }


# Team-agnostic common baseline prepended to EVERY worker's allow. These are the paths
# that are not specific to any one team: the project root, the scratchpad, and the
# workflow-output dir. The guard's merged_config REPLACES defaults.allow with the
# agent's own allow when present (it does NOT union), so this baseline must be baked into
# each worker's allow directly or that worker loses '.'/scratchpad/workflow access.
BASELINE_ALLOW = [
    ".",
    "/private/tmp/claude-501/-Users-ujunbin-team-umc/**",
    "/Users/ujunbin/.claude/projects/-Users-ujunbin-team-umc/**",
]


def _team_allow_paths(setup: dict[str, Any], name: str) -> list[str]:
    """The allow_paths of the subteam a worker belongs to (empty if none). Uses the same
    worker -> subteam lookup axis as _worker_path."""
    for st in setup.get("subteams") or []:
        if isinstance(st, dict) and name in (st.get("members") or []):
            return list(st.get("allow_paths") or [])
    return []


def _other_team_allow_paths(setup: dict[str, Any], name: str) -> list[str]:
    """External work paths owned by OTHER teams (every team's allow_paths minus this
    worker's own team). These are added to the worker's deny so the team-external
    whitelist is enforced on EVERY tool (Read/Edit/Write AND Bash) via the deny side,
    without an allow-side check that would over-block unrelated paths like /tmp."""
    mine = set(_team_allow_paths(setup, name))
    others: list[str] = []
    seen: set[str] = set()
    for st in setup.get("subteams") or []:
        if not isinstance(st, dict):
            continue
        for path in st.get("allow_paths") or []:
            if path not in mine and path not in seen:
                seen.add(path)
                others.append(path)
    return others


def _worker_path(setup: dict[str, Any], name: str) -> str:
    """The repo-relative folder of a worker: teams/<team>/<name> if it's in a subteam,
    else flat agents/<name>. Drives the isolation deny patterns so they point at the
    worker's REAL location regardless of topology."""
    for st in setup.get("subteams") or []:
        if isinstance(st, dict) and name in (st.get("members") or []):
            return f"teams/{st['name']}/{name}"
    return f"agents/{name}"


def _other_team_inbox_globs(setup: dict[str, Any], name: str) -> list[str]:
    """Team-only inbox model (2026-06-27): each OTHER team's mailbox is a READ-blocked
    drop-off slot for this worker. Returned for ``deny_read`` — the guard lets this worker
    WRITE (post) to another team's inbox but never READ it (no cross-team context bleed).
    A worker's OWN team inbox is intentionally NOT listed (read+write allowed). Skips the
    worker's own team; covers every subteam folder mailbox."""
    my_team = None
    for st in setup.get("subteams") or []:
        if isinstance(st, dict) and name in (st.get("members") or []):
            my_team = st.get("name")
            break
    globs: list[str] = []
    for st in setup.get("subteams") or []:
        if not isinstance(st, dict):
            continue
        tname = st.get("name")
        if not tname or tname == my_team:
            continue
        globs.append(f"teams/{tname}/.claude/inbox/**")
    globs.append("teams/.orchestrator/inbox/**")
    return sorted(globs)


def build_agent_workspace_policy(setup: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Regenerate the guard's worker-isolation policy from the roster.

    The ``agents`` map is 100% derivable from the members: each worker denies every OTHER
    worker's folder (full N^2 isolation — same-team peers are isolated too, per the strict
    scope-split rule). Deny patterns target each worker's REAL path via _worker_path, so a
    flat tree yields ``agents/<other>/**`` and a 2-tier tree yields ``teams/<team>/<other>/**``.

    Because patterns target worker FOLDERS (not team roots), a worker's own team shared
    resources (``teams/<team>/.claude`` and ``.context``) are NOT denied — they fall outside
    every sibling's worker-folder pattern and stay readable.

    Each worker's ``allow`` is BASELINE_ALLOW + its subteam's ``allow_paths`` (team external
    work boundaries). The guard REPLACES defaults.allow with this when present, so the full
    effective allow is visible per worker in this file alone. ``defaults.allow`` is pinned to
    baseline-only: a registered worker never reads it, but an unregistered/typo/empty/``main``
    name falls back to it — baseline-only means such a name gets zero external team paths
    (fail-safe against team-whitelist bypass). ``bash``/``deny`` defaults are preserved.
    """
    members = setup["members"]
    agents = {
        name: {
            # deny = N^2 peer worker folders + OTHER teams' external work paths. Both are
            # checked by the guard on every tool (Read/Edit/Write/Bash), so the team-external
            # whitelist is symmetric across channels (no Bash bypass).
            "deny": [f"{_worker_path(setup, other)}/**" for other in members if other != name]
                    + _other_team_allow_paths(setup, name),
            # deny_read = OTHER teams' inbox mailboxes: WRITE-OK (post to them), READ-blocked
            # (no cross-team mail bleed). Own-team inbox is absent → read+write allowed.
            "deny_read": _other_team_inbox_globs(setup, name),
            "allow": BASELINE_ALLOW + _team_allow_paths(setup, name),
        }
        for name in members
    }
    # The company governance owner (``authoring_owner``) may be a NON-member virtual
    # identity — the reserved "orchestrator" total — which never appears in ``members`` and
    # so is skipped by the comprehension above. Without this its workspace entry was added by
    # hand and wiped on every regen (drift). Inject it from the same roster axis so it is a
    # single source of truth. A member owner already has its entry from the loop, so only
    # inject when the owner is NOT a member.
    owner = setup.get("authoring_owner")
    if isinstance(owner, str) and owner and owner not in members:
        agents[owner] = {
            # deny = [] — the company total is NOT plain-denied any worker folder, because
            # plain deny blocks BOTH read and write and would contradict its read-only mandate.
            "deny": [],
            # deny_read = [] — the company total may READ every team mailbox (the exact
            # opposite of a worker, which is read-blocked on other teams' inboxes) AND every
            # worker's private folder (read-only coordination, user decision 2026-06-28).
            "deny_read": [],
            # deny_write = every worker's REAL folder (full roster). This is the "read-only
            # window": the coordinator may READ each worker's private folder (memory/.context)
            # via Read/Grep/Glob and the shell, but Edit/Write/MultiEdit into them are blocked,
            # so it never authors a worker's deliverables directly (read-only orchestration).
            "deny_write": [f"{_worker_path(setup, m)}/**" for m in members],
            # allow = BASELINE_ALLOW only: no team external work boundaries.
            "allow": list(BASELINE_ALLOW),
        }
    base = existing if isinstance(existing, dict) else {}
    base_defaults = base.get("defaults") if isinstance(base.get("defaults"), dict) else {}
    defaults = {
        "allow": list(BASELINE_ALLOW),
        "bash": base_defaults.get("bash") if isinstance(base_defaults.get("bash"), dict) else {"allow": [], "deny": []},
        "deny": base_defaults.get("deny") if isinstance(base_defaults.get("deny"), list) else [],
    }
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
    store = team_root / ".project"
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

    for keep in ("goals/.gitkeep", "inbox/.archive/.gitkeep"):
        p = store / keep
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text("", encoding="utf-8")
    orch_keep = team_root / "teams" / ".orchestrator" / "inbox" / ".gitkeep"
    orch_keep.parent.mkdir(parents=True, exist_ok=True)
    if not orch_keep.exists():
        orch_keep.write_text("", encoding="utf-8")
    for st in setup.get("subteams") or []:
        if not isinstance(st, dict) or not st.get("name"):
            continue
        team_keep = team_root / "teams" / str(st["name"]) / ".claude" / "inbox" / ".gitkeep"
        team_keep.parent.mkdir(parents=True, exist_ok=True)
        if not team_keep.exists():
            team_keep.write_text("", encoding="utf-8")

    agents = _create_members(team_root, setup) if create_agents else []
    return {
        "team": setup["team"],
        "members": setup["members"],
        "authoring_owner": setup["authoring_owner"],
        "min_distinct_agents": setup["min_distinct_agents"],
        "reminders_list": setup["reminders_list"],
        "files": [
            ".project/team.json",
            ".project/policies/team-promotion.json",
            ".project/policies/team-derivation.json",
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
        k: v for k, v in entry.items() if k in ("name", "members", "orchestrator", "reminders_list", "allow_paths")
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
    p = sub.add_parser("init", help="Write .project/ definition from a team-setup.json (file or stdin).")
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
