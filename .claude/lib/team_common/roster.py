"""Roster parsing and worker discovery."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from .io import load_json_dict


@dataclass(frozen=True)
class TeamIndex:
    """Cached view of ``team.json`` membership and subteam topology."""

    root: Path
    subteams: dict[str, list[str]]
    leads: dict[str, str]
    worker_to_team: dict[str, str]
    members: set[str]

    @classmethod
    def load(cls, root: Path) -> "TeamIndex":
        root = root.expanduser()
        return _load_team_index(str(root), _stamp(root / ".project" / "team.json"), _stamp(root / "team.json"))

    def worker_at(self, candidate: Path) -> str | None:
        """Return the registered worker owning ``candidate`` if under teams/<team>/<worker>."""
        try:
            rel = candidate.relative_to(self.root)
        except ValueError:
            return None
        parts = rel.parts
        if len(parts) < 3 or parts[0] != "teams":
            return None
        team, worker = parts[1], parts[2]
        return worker if worker in self.subteams.get(team, []) else None

    def registered_members(self, *extra: str) -> set[str]:
        return self.members | {name for name in extra if name}


def discover_worker_dirs(team_root: Path, is_worker_dir: Callable[[Path], bool]) -> dict[str, Path]:
    """Map worker name to folder across ``teams/<team>/<worker>`` and ``agents/<worker>``."""
    found: dict[str, Path] = {}
    teams_dir = team_root / "teams"
    if teams_dir.is_dir():
        for team in sorted(teams_dir.iterdir(), key=lambda p: p.name):
            if not team.is_dir() or team.name.startswith("."):
                continue
            for child in sorted(team.iterdir(), key=lambda p: p.name):
                if is_worker_dir(child):
                    found.setdefault(child.name, child)
    agents_dir = team_root / "agents"
    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir(), key=lambda p: p.name):
            if is_worker_dir(child):
                found.setdefault(child.name, child)
    return found


def _stamp(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=64)
def _load_team_index(
    root_text: str,
    _project_stamp: tuple[int, int] | None,
    _flat_stamp: tuple[int, int] | None,
) -> TeamIndex:
    root = Path(root_text)
    data = {}
    for candidate in (root / ".project" / "team.json", root / "team.json"):
        data = load_json_dict(candidate)
        if data:
            break
    return _team_index_from_data(root, data)


def _team_index_from_data(root: Path, data: dict) -> TeamIndex:
    subteams: dict[str, list[str]] = {}
    leads: dict[str, str] = {}
    worker_to_team: dict[str, str] = {}
    if isinstance(data.get("subteams"), list):
        for entry in data.get("subteams") or []:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                continue
            team = entry["name"]
            members = [m for m in (entry.get("members") or []) if isinstance(m, str)]
            subteams[team] = members
            lead = entry.get("orchestrator")
            if isinstance(lead, str) and lead:
                leads[team] = lead
            for member in members:
                worker_to_team.setdefault(member, team)

    raw_members = data.get("members")
    members = {m for m in (raw_members or []) if isinstance(raw_members, list) and isinstance(m, str)}
    members.update(worker_to_team)
    return TeamIndex(root=root, subteams=subteams, leads=leads, worker_to_team=worker_to_team, members=members)
