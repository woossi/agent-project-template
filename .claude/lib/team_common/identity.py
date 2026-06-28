"""Forge-resistant identity helpers shared by team tools."""
from __future__ import annotations

import os
from pathlib import Path

from .roster import TeamIndex

CWD_FAILCLOSED = "__cwd_failclosed__"


def identity_from_cwd(team_root: Path, *, failclosed: str = CWD_FAILCLOSED) -> str | None:
    """Derive worker identity from logical+physical cwd.

    Returns a worker name, ``None`` when cwd is outside ``teams/``, or ``failclosed``
    when cwd is inside ``teams/`` but not a registered logical/physical worker match.
    """
    pwd_env = os.environ.get("PWD")
    logical_raw = Path(pwd_env) if pwd_env else Path.cwd()
    physical_raw = Path.cwd()
    logical_raw = logical_raw if logical_raw.is_absolute() else (team_root / logical_raw)
    physical_raw = physical_raw if physical_raw.is_absolute() else (team_root / physical_raw)
    logical = Path(os.path.normpath(str(logical_raw)))
    physical = physical_raw.resolve()
    root_res = team_root.resolve()

    inside = False
    for base in (team_root, root_res):
        try:
            rel = logical.relative_to(base)
            if rel.parts and rel.parts[0] == "teams":
                inside = True
                break
        except ValueError:
            continue
    if not inside:
        try:
            rel = physical.relative_to(root_res)
            inside = bool(rel.parts) and rel.parts[0] == "teams"
        except ValueError:
            inside = False
    if not inside:
        return None

    index = TeamIndex.load(team_root)
    physical_index = TeamIndex.load(root_res)
    log_w = index.worker_at(logical) or physical_index.worker_at(logical)
    phys_w = physical_index.worker_at(physical) or index.worker_at(physical)
    if log_w and phys_w and log_w == phys_w:
        return log_w
    return failclosed


def resolve_actor(team_root: Path, explicit: str | None, *, fallback: str = "team") -> str:
    cwd_id = identity_from_cwd(team_root)
    if cwd_id is not None:
        return cwd_id
    return explicit or os.environ.get("CLAUDE_AGENT_NAME") or fallback

