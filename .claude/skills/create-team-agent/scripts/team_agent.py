#!/usr/bin/env python3
"""Create a homogeneous team peer agent (Model Y).

The user decides WHEN to create an agent; this scaffolds the 1-tier folder so that
all of its assets are auto-managed by the existing per-agent loops, identically to
every other peer. It references the template-conversion idea of agent-clone-setup but
does NOT rewrite the role contract (peers must stay byte-identical in structure).

Layout produced under ``agents/<name>/`` (project root when that agent runs):

    agents/<name>/
      .claude/
        memory/       (REAL, private)  memory.md, user_preferences.md, word.json
        tasks/        (REAL, private)  tasks.md
        hooks      -> ../../../.claude/hooks       (SYMLINK, shared single source)
        policies   -> ../../../.claude/policies    (SYMLINK)
        skills/    (REAL dir) per-skill: <shared> -> ../../../../.claude/skills/<shared>
                   (SYMLINK each) + <private>/ (REAL dir, isolated to this agent)
        settings.json -> ../../../.claude/settings.json (SYMLINK)
        CLAUDE.md  -> ../../../.claude/CLAUDE.md    (SYMLINK)
      AGENTS.md    -> ../../AGENTS.md               (SYMLINK)
      AGENT.md     (role descriptor)
      .context/    (REAL, private, gitignored)

Identity is injected at launch via ``export CLAUDE_AGENT_NAME=<name>`` (read by the
guard and every team CLI) — it is NOT baked into the shared settings.json.

Shared dirs are symlinks so the team-single-source stays drift-free. NOTE: reading a
symlinked *skill file* via the Read tool escapes the agent root and is blocked by the
guard; agents reference shared skills via the Skill tool / autoload, and skill-use is
recorded by the team-tier recorder (see the team-tier plan §3.6). hooks/policies are
consumed by Python (not the Read tool), so their symlinks are fine.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

# Shared subtrees symlinked into each agent's .claude, keyed by the link name to the
# REAL subpath under the team root. The relative symlink target is COMPUTED from the
# link's actual depth (see _rel) — never hardcoded — so a worker at agents/<name>/ (depth 2)
# and one at teams/<team>/<name>/ (depth 3) both get a correct ../-count from the same code.
# NOTE: ``skills`` is NOT here — it is wired per-skill by _wire_skills so an agent can
# hold PRIVATE skills (real dirs) alongside SHARED ones (symlinks). A whole-dir symlink
# would force all-or-nothing and leak any private skill into the shared single source.
SHARED_IN_CLAUDE = {
    "hooks": ".claude/hooks",
    "policies": ".claude/policies",
    "settings.json": ".claude/settings.json",
    "CLAUDE.md": ".claude/CLAUDE.md",
}


def _rel(target_abs: Path, link: Path) -> str:
    """Relative POSIX symlink target from ``link`` to ``target_abs``, depth-independent.

    Uses os.path.relpath against the link's PARENT (where the link physically lives) so
    the ``../`` count is always correct regardless of how deep the agent folder is nested.
    Normalized to POSIX ``/`` because symlink targets must not carry OS separators.
    """
    rel = os.path.relpath(os.fspath(target_abs), start=os.fspath(link.parent))
    return PurePosixPath(rel).as_posix() if os.sep == "/" else rel.replace(os.sep, "/")


# --- Skill compartmentalization (3-tier company) ---
# GOVERNANCE skills re-/define the team itself (roster, goals, derivation authoring).
# They are linked ONLY to the governance authoring_owner — a non-owner worker has no
# business re-defining the team, so these stay off every other worker's skills folder.
GOVERNANCE_SHARED = frozenset({
    "team-init", "create-team-agent", "agent-clone-setup", "set-team-goal", "team-derive-author",
})


def _governance_owner(team_root: Path) -> str | None:
    """The single worker allowed to hold governance skills (team-promotion.json owner)."""
    pol = team_root / ".project" / "policies" / "team-promotion.json"
    data = _load_json_or_none(pol)
    if isinstance(data, dict):
        gov = data.get("governance")
        if isinstance(gov, dict):
            owner = gov.get("authoring_owner")
            if isinstance(owner, str) and owner.strip():
                return owner.strip()
    return None


def _allowed_shared_skills(team_root: Path, name: str) -> set[str] | None:
    """The set of SHARED root skills this worker may link, or None for "all" (back-compat).

    Every shared skill is allowed EXCEPT governance skills, which are allowed only for the
    governance owner. When no governance owner is resolvable (e.g. a fresh/flat team with no
    team-promotion.json), return None so behavior is unchanged (link everything).
    """
    root_skills = team_root / ".claude" / "skills"
    if not root_skills.is_dir():
        return None
    owner = _governance_owner(team_root)
    if owner is None:
        return None  # no governance policy => preserve legacy "link all"
    all_shared = {
        c.name for c in root_skills.iterdir()
        if c.is_dir() and not c.name.startswith((".", "_"))
    }
    if name == owner:
        return all_shared  # owner gets everything, including governance
    return all_shared - GOVERNANCE_SHARED  # non-owner: governance withheld


class AgentError(RuntimeError):
    """Raised on a bad team root or an existing agent without --force."""


def default_team_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _load_json_or_none(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _ensure_symlink(link: Path, target: str, *, force: bool) -> str:
    if link.is_symlink():
        if os.readlink(link) == target:
            return "ok"
        if not force:
            return "differs"
        link.unlink()
    elif link.exists():
        if not force:
            return "blocked-real-file"
        if link.is_dir():
            return "blocked-real-dir"
        link.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, link)
    return "created"


def _wire_skills(team_root: Path, agent_claude: Path, *, force: bool, allowed: set[str] | None = None) -> dict[str, str]:
    """Wire ``.claude/skills`` as a REAL directory of per-skill symlinks to the
    shared root skills, preserving any PRIVATE (real) skill dirs this agent holds.

    Why not a single whole-dir symlink: that makes shared and private skills
    mutually exclusive — anything added lands in the shared single source and
    leaks to every peer. Per-skill symlinks keep shared skills drift-free (one
    source) while leaving room for private real dirs isolated to this agent.

    ``allowed``: when None (default), every shared skill is linked (back-compat).
    When a set, ONLY those shared skills are linked — this is how governance skills
    are kept off non-owner workers (compartmentalization). Pruning of now-disallowed
    links is done by _prune_stale_skill_symlinks, which takes the same allowlist.

    Per-skill targets are COMPUTED via _rel, so the same code wires a worker at
    agents/<name>/ (depth 2) or teams/<team>/<name>/ (depth 3) correctly.

    Idempotent: re-running links in any newly added shared skills and leaves a
    same-named private real dir untouched (it shadows the shared name on purpose).
    A legacy whole-dir symlink is migrated to a real dir only under ``force``.
    """
    root_skills = team_root / ".claude" / "skills"
    agent_skills = agent_claude / "skills"
    out: dict[str, str] = {}

    if agent_skills.is_symlink():
        if not force:
            out["skills"] = "whole-symlink (use --force to migrate)"
            return out
        agent_skills.unlink()  # migrate legacy whole-dir symlink -> real dir
    if agent_skills.exists() and not agent_skills.is_dir():
        out["skills"] = "blocked-real-file"
        return out
    agent_skills.mkdir(parents=True, exist_ok=True)

    if not root_skills.is_dir():
        out["skills"] = "no-shared-skills"
        return out

    for child in sorted(root_skills.iterdir(), key=lambda p: p.name):
        # Only skill folders are linked; skip generated index files (skills.md)
        # and private/hidden entries (leading "." or "_").
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        if allowed is not None and child.name not in allowed:
            out[f"skills/{child.name}"] = "not-allowed (skipped)"  # compartmentalized off this worker
            continue
        link = agent_skills / child.name
        if link.exists() and not link.is_symlink():
            out[f"skills/{child.name}"] = "private (kept)"  # private dir shadows shared name
            continue
        target = _rel(root_skills / child.name, link)
        out[f"skills/{child.name}"] = _ensure_symlink(link, target, force=True)
    out["skills"] = "wired"
    return out


def _seed_private_assets(agent_claude: Path, name: str) -> None:
    mem = agent_claude / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    memory_md = mem / "memory.md"
    if not memory_md.exists():
        memory_md.write_text(
            f"# Memory — agent: {name}\n\n"
            "Private working memory (facts this agent learns while working).\n"
            "Team-wide decisions and goals live in the team store (.project/memory, .project/goals).\n\n"
            "## Durable Facts\n",
            encoding="utf-8",
        )
    prefs = mem / "user_preferences.md"
    if not prefs.exists():
        prefs.write_text(
            f"# User Preferences — agent: {name}\n\n"
            "Private, agent-scoped preferences. Team-wide preferences live in the team store.\n\n"
            "## Active Preferences\n\nNo preferences recorded yet.\n",
            encoding="utf-8",
        )
    word = mem / "word.json"
    if not word.exists():
        word.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "description": f"Private terminology for agent {name}. Team-shared terms live in .project/word.json.",
                    "terms": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    tasks = agent_claude / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    tasks_md = tasks / "tasks.md"
    if not tasks_md.exists():
        tasks_md.write_text(
            "# 작업\n\n## 상태\n대기\n\n## 목표\n(아직 할당된 작업 없음)\n",
            encoding="utf-8",
        )


def _subteam_of(team_root: Path, name: str) -> str | None:
    """The subteam a worker belongs to, from team.json's ``subteams`` (single source)."""
    data = _load_json_or_none(team_root / ".project" / "team.json")
    if not isinstance(data, dict):
        return None
    for st in data.get("subteams") or []:
        if isinstance(st, dict) and name in (st.get("members") or []):
            tname = st.get("name")
            if isinstance(tname, str) and tname.strip():
                return tname.strip()
    return None


def agent_dir_for(team_root: Path, name: str) -> Path:
    """Resolve a worker's folder, 2-tier (teams/<team>/<name>) or flat (agents/<name>).

    Prefers the subteam location from team.json. Falls back to flat ``agents/<name>``
    when the worker is not in any subteam (a flat team, or a fresh/CI root with no
    subteams) — this fallback is what keeps every existing test green after this
    generalization, since their fake roots have no subteams.
    """
    sub = _subteam_of(team_root, name)
    if sub:
        return team_root / "teams" / sub / name
    return team_root / "agents" / name


def _wire_shared(team_root: Path, agent_dir: Path, name: str, *, force: bool) -> dict[str, str]:
    """(Re)wire the SHARED symlinks + AGENTS.md + per-skill skills for one worker.

    Shared by create and sync so both produce byte-identical wiring. All targets are
    COMPUTED with _rel, so this is depth-independent (flat or 2-tier). Skills honor the
    governance allowlist so non-owner workers never get governance skills linked.
    """
    agent_claude = agent_dir / ".claude"
    out: dict[str, str] = {}
    for rel, real_subpath in SHARED_IN_CLAUDE.items():
        link = agent_claude / rel
        out[rel] = _ensure_symlink(link, _rel(team_root / real_subpath, link), force=force)
    allowed = _allowed_shared_skills(team_root, name)
    out.update(_wire_skills(team_root, agent_claude, force=force, allowed=allowed))
    agents_link = agent_dir / "AGENTS.md"
    out["AGENTS.md"] = _ensure_symlink(agents_link, _rel(team_root / "AGENTS.md", agents_link), force=force)
    return out


def _register_in_roster(team_root: Path, name: str) -> bool:
    team_file = team_root / ".project" / "team.json"
    if team_file.exists():
        data = json.loads(team_file.read_text(encoding="utf-8"))
    else:
        data = {"version": 1, "members": []}
    members = data.get("members")
    if not isinstance(members, list):
        members = []
    if name in members:
        data["members"] = members
        return False
    members.append(name)
    data["members"] = members
    _atomic_write_json(team_file, data)
    return True


def create_agent(team_root: Path, name: str, *, role: str | None = None, force: bool = False) -> dict[str, Any]:
    if not (team_root / ".claude").is_dir():
        raise AgentError(f"team root has no .claude/: {team_root}")
    agent_dir = agent_dir_for(team_root, name)
    existed = agent_dir.exists()
    if existed and not force:
        return {"name": name, "dir": str(agent_dir), "created": False, "exists": True}

    agent_claude = agent_dir / ".claude"
    agent_claude.mkdir(parents=True, exist_ok=True)
    (agent_dir / ".context").mkdir(parents=True, exist_ok=True)

    _seed_private_assets(agent_claude, name)

    symlinks = _wire_shared(team_root, agent_dir, name, force=force)

    descriptor = agent_dir / "AGENT.md"
    if not descriptor.exists():
        descriptor.write_text(
            f"# Agent: {name}\n\n"
            f"Role: {role or 'homogeneous team peer'}\n\n"
            f"Launch: `export CLAUDE_AGENT_NAME={name}` then run `claude` from this folder.\n\n"
            "Shared (symlinked to team root, identical across peers): .claude/{hooks,policies,skills,"
            "settings.json,CLAUDE.md}, AGENTS.md.\n"
            "Private (this agent only): .claude/memory, .claude/tasks, .context.\n",
            encoding="utf-8",
        )

    roster_added = _register_in_roster(team_root, name)

    return {
        "name": name,
        "dir": str(agent_dir),
        "created": True,
        "reused": existed,
        "symlinks": symlinks,
        "roster_added": roster_added,
    }


def discover_worker_dirs(team_root: Path) -> dict[str, Path]:
    """Map every worker NAME to its folder, scanning both topologies.

    A WORKER is identified by holding ``.claude/memory/`` (create always seeds it). This
    distinguishes workers from team folders (their ``.claude`` lives at the team root, and
    dot-prefixed entries are skipped) and from non-worker folders (``.context`` only, no
    ``.claude``). Scans teams/<team>/<worker>/ AND flat agents/<worker>/ so a half-migrated
    or flat tree both resolve. Worker names are globally unique, so name is a safe key.
    """
    def _is_worker(c: Path) -> bool:
        # A worker holds a seeded .claude/memory; a TEAM folder also does, but carries a
        # .team-folder sentinel that excludes it. dot-prefixed entries are skipped.
        return (c.is_dir() and not c.name.startswith(".")
                and not (c / ".team-folder").exists()
                and (c / ".claude" / "memory").is_dir())

    found: dict[str, Path] = {}
    teams_dir = team_root / "teams"
    if teams_dir.is_dir():
        for team in sorted(teams_dir.iterdir(), key=lambda p: p.name):
            if not team.is_dir() or team.name.startswith("."):
                continue
            for child in sorted(team.iterdir(), key=lambda p: p.name):
                if _is_worker(child):
                    found.setdefault(child.name, child)
    agents_dir = team_root / "agents"
    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir(), key=lambda p: p.name):
            if _is_worker(child):
                found.setdefault(child.name, child)
    return found


def list_agents(team_root: Path) -> dict[str, Any]:
    folders = sorted(discover_worker_dirs(team_root))
    team_file = team_root / ".project" / "team.json"
    roster = []
    if team_file.exists():
        roster = json.loads(team_file.read_text(encoding="utf-8")).get("members", [])
    return {"agent_folders": folders, "roster": roster, "out_of_sync": sorted(set(folders) ^ set(roster))}


def _prune_stale_skill_symlinks(team_root: Path, agent_claude: Path, *, allowed: set[str] | None = None) -> list[str]:
    """Remove per-skill symlinks that should no longer exist for this worker.

    Two reasons to prune (both keep the single source authoritative):
      1. the shared source skill was deleted/renamed (dangling link), or
      2. ``allowed`` is a set and this skill is no longer permitted for this worker
         (governance withheld) — this is the execution point that RECLAIMS a skill.

    Resolves each symlink's target to an absolute path and checks it points under
    root ``.claude/skills`` — depth-independent, unlike the old ``../``-prefix match.
    Private real dirs are never pruned.
    """
    agent_skills = agent_claude / "skills"
    root_skills = (team_root / ".claude" / "skills").resolve()
    pruned: list[str] = []
    if not agent_skills.is_dir() or agent_skills.is_symlink():
        return pruned
    for child in sorted(agent_skills.iterdir(), key=lambda p: p.name):
        if not child.is_symlink():
            continue  # private real dirs are never pruned
        target = os.readlink(child)
        # A shared per-skill link always points at ``.../.claude/skills/<child.name>``. We
        # match on the TARGET STRING (not a resolve) so a link broken by a folder move —
        # whose ``../`` count is now wrong and won't resolve — is still recognized and can
        # be reclaimed. Links pointing elsewhere (user-made) don't match and are left alone.
        posix = PurePosixPath(target.replace(os.sep, "/"))
        if posix.name != child.name or ".claude/skills/" not in target.replace(os.sep, "/"):
            continue  # not a managed shared-skill link
        shared_name = child.name
        disallowed = allowed is not None and shared_name not in allowed
        missing = not (root_skills / shared_name).is_dir()
        if disallowed or missing:
            child.unlink()
            pruned.append(child.name)
    return pruned


def sync_agent(team_root: Path, agent_dir: Path, name: str, *, force: bool = False, prune: bool = True) -> dict[str, Any]:
    """Reconcile ONE existing worker against the shared single source.

    Rewires the SHARED symlinks + AGENTS.md + per-skill skills (depth-independent, honoring
    the governance allowlist), then prunes any skill symlink that is now stale OR no longer
    permitted for this worker. This is the reproduce/sync entry point that also fixes broken
    SHARED links after a folder move (previously sync touched only skills).
    """
    wired = _wire_shared(team_root, agent_dir, name, force=True)  # force: repair broken links after a move
    allowed = _allowed_shared_skills(team_root, name)
    pruned = _prune_stale_skill_symlinks(team_root, agent_dir / ".claude", allowed=allowed) if prune else []
    return {"wired": wired, "pruned": pruned}


def sync_agents(team_root: Path, name: str | None = None, *, all_agents: bool = False, force: bool = False) -> dict[str, Any]:
    """Reconcile one or every worker's wiring against the shared single source.

    The reproduce/sync tool: after a shared skill is added/removed, a folder move, or a
    governance change, run ``sync --all`` to re-wire every peer identically, or
    ``sync <name>`` for one. Discovers workers across both topologies (teams/ and agents/).
    """
    if not (team_root / ".claude").is_dir():
        raise AgentError(f"team root has no .claude/: {team_root}")
    worker_dirs = discover_worker_dirs(team_root)
    if all_agents:
        targets = sorted(worker_dirs)
    elif name:
        if name not in worker_dirs:
            raise AgentError(f"no such worker folder: {name}")
        targets = [name]
    else:
        raise AgentError("sync needs an agent NAME or --all")
    return {"synced": targets, "skills": {n: sync_agent(team_root, worker_dirs[n], n, force=force) for n in targets}}


# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team_agent.py", description="Create a homogeneous team peer agent (Model Y).")
    parser.add_argument("--team-root", default=None, help="Team root (default: repo root inferred from this script).")
    sub = parser.add_subparsers(dest="op", required=True)

    p_create = sub.add_parser("create", help="Scaffold a new peer agent folder and register it.")
    p_create.add_argument("name")
    p_create.add_argument("--role", default=None, help="Short role descriptor (does NOT rewrite the shared contract).")
    p_create.add_argument("--force", action="store_true", help="Re-wire symlinks on an existing agent (keeps private seeds).")

    sub.add_parser("list", help="List agent folders vs roster and any drift.")

    p_sync = sub.add_parser("sync", help="Re-wire an agent's skills against the shared set (add/prune symlinks, keep private).")
    p_sync.add_argument("name", nargs="?", default=None, help="Agent to sync (omit with --all).")
    p_sync.add_argument("--all", dest="all_agents", action="store_true", help="Sync every agent folder.")
    p_sync.add_argument("--force", action="store_true", help="Migrate a legacy whole-dir 'skills' symlink to a real dir.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    team_root = Path(args.team_root).expanduser() if args.team_root else default_team_root()
    try:
        if args.op == "create":
            result = create_agent(team_root, args.name, role=args.role, force=args.force)
        elif args.op == "list":
            result = list_agents(team_root)
        elif args.op == "sync":
            result = sync_agents(team_root, args.name, all_agents=args.all_agents, force=args.force)
        else:  # pragma: no cover
            raise AgentError(f"unhandled op: {args.op}")
    except AgentError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    json.dump({"ok": True, "op": args.op, "result": result}, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
