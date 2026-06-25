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
from pathlib import Path
from typing import Any

# Shared subtrees symlinked into each agent's .claude (target relative to agents/<name>/.claude/).
# NOTE: ``skills`` is NOT here — it is wired per-skill by _wire_skills so an agent can
# hold PRIVATE skills (real dirs) alongside SHARED ones (symlinks). A whole-dir symlink
# would force all-or-nothing and leak any private skill into the shared single source.
SHARED_IN_CLAUDE = {
    "hooks": "../../../.claude/hooks",
    "policies": "../../../.claude/policies",
    "settings.json": "../../../.claude/settings.json",
    "CLAUDE.md": "../../../.claude/CLAUDE.md",
}


class AgentError(RuntimeError):
    """Raised on a bad team root or an existing agent without --force."""


def default_team_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


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


def _wire_skills(team_root: Path, agent_claude: Path, *, force: bool) -> dict[str, str]:
    """Wire ``.claude/skills`` as a REAL directory of per-skill symlinks to the
    shared root skills, preserving any PRIVATE (real) skill dirs this agent holds.

    Why not a single whole-dir symlink: that makes shared and private skills
    mutually exclusive — anything added lands in the shared single source and
    leaks to every peer. Per-skill symlinks keep shared skills drift-free (one
    source) while leaving room for private real dirs isolated to this agent.

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
        link = agent_skills / child.name
        if link.exists() and not link.is_symlink():
            out[f"skills/{child.name}"] = "private (kept)"  # private dir shadows shared name
            continue
        target = f"../../../../.claude/skills/{child.name}"
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
            "Team-wide decisions and goals live in the team store (.team/memory, .team/goals).\n\n"
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
                    "description": f"Private terminology for agent {name}. Team-shared terms live in .team/word.json.",
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


def _register_in_roster(team_root: Path, name: str) -> bool:
    team_file = team_root / ".team" / "team.json"
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
    agent_dir = team_root / "agents" / name
    existed = agent_dir.exists()
    if existed and not force:
        return {"name": name, "dir": str(agent_dir), "created": False, "exists": True}

    agent_claude = agent_dir / ".claude"
    agent_claude.mkdir(parents=True, exist_ok=True)
    (agent_dir / ".context").mkdir(parents=True, exist_ok=True)

    _seed_private_assets(agent_claude, name)

    symlinks = {}
    for rel, target in SHARED_IN_CLAUDE.items():
        symlinks[rel] = _ensure_symlink(agent_claude / rel, target, force=force)
    symlinks.update(_wire_skills(team_root, agent_claude, force=force))
    symlinks["AGENTS.md"] = _ensure_symlink(agent_dir / "AGENTS.md", "../../AGENTS.md", force=force)

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


def list_agents(team_root: Path) -> dict[str, Any]:
    agents_dir = team_root / "agents"
    folders = sorted(p.name for p in agents_dir.glob("*") if p.is_dir()) if agents_dir.exists() else []
    team_file = team_root / ".team" / "team.json"
    roster = []
    if team_file.exists():
        roster = json.loads(team_file.read_text(encoding="utf-8")).get("members", [])
    return {"agent_folders": folders, "roster": roster, "out_of_sync": sorted(set(folders) ^ set(roster))}


def _prune_stale_skill_symlinks(team_root: Path, agent_claude: Path) -> list[str]:
    """Remove per-skill symlinks whose shared source no longer exists.

    _wire_skills only ADDS shared skills (shared -> agent); when a shared skill is
    deleted or renamed, every peer keeps a dangling symlink. This is the reverse
    direction (agent -> shared) that keeps the single source authoritative.
    """
    agent_skills = agent_claude / "skills"
    root_skills = team_root / ".claude" / "skills"
    pruned: list[str] = []
    if not agent_skills.is_dir() or agent_skills.is_symlink():
        return pruned
    prefix = "../../../../.claude/skills/"
    for child in sorted(agent_skills.iterdir(), key=lambda p: p.name):
        if not child.is_symlink():
            continue  # private real dirs are never pruned
        target = os.readlink(child)
        if target.startswith(prefix):
            shared_name = target[len(prefix):].strip("/")
            if not (root_skills / shared_name).is_dir():
                child.unlink()
                pruned.append(child.name)
    return pruned


def sync_agent(team_root: Path, agent_dir: Path, *, force: bool = False, prune: bool = True) -> dict[str, Any]:
    """Reconcile ONE existing agent's skills against the shared single source.

    Reuses ``_wire_skills`` (adds any new shared skill, keeps private dirs, migrates a
    legacy whole-dir symlink under ``force``) and additionally prunes stale per-skill
    symlinks whose shared source was removed. This is the reproduce/sync entry point
    that ``_wire_skills`` (create-time only) never exposed for existing agents.
    """
    agent_claude = agent_dir / ".claude"
    wired = _wire_skills(team_root, agent_claude, force=force)
    pruned = _prune_stale_skill_symlinks(team_root, agent_claude) if prune else []
    return {"wired": wired, "pruned": pruned}


def sync_agents(team_root: Path, name: str | None = None, *, all_agents: bool = False, force: bool = False) -> dict[str, Any]:
    """Reconcile one or every agent's skills folder against the shared single source.

    The missing reproduce/sync tool: after a shared skill is added or removed, run
    ``sync --all`` to re-wire every peer identically (and migrate any agent still on the
    legacy whole-dir ``skills`` symlink), or ``sync <name>`` for one.
    """
    if not (team_root / ".claude").is_dir():
        raise AgentError(f"team root has no .claude/: {team_root}")
    agents_dir = team_root / "agents"
    if all_agents:
        targets = sorted(p.name for p in agents_dir.glob("*") if p.is_dir()) if agents_dir.exists() else []
    elif name:
        if not (agents_dir / name).is_dir():
            raise AgentError(f"no such agent folder: agents/{name}")
        targets = [name]
    else:
        raise AgentError("sync needs an agent NAME or --all")
    return {"synced": targets, "skills": {n: sync_agent(team_root, agents_dir / n, force=force) for n in targets}}


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
