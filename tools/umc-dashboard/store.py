"""Read-only view over the .team/ shared store (the single source of truth).

This module ONLY reads files — it never mutates the store. All writes go through
the verified CLIs (see adapters.py). Parsing is defensive: a malformed or
half-written file (atomic rename means we may catch a tmp file mid-flight) yields
an empty/skip result rather than crashing the TUI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def repo_root(start: Path | None = None) -> Path:
    """Walk up to the repo root (the dir holding .team/team.json or AGENTS.md)."""
    here = (start or Path(__file__)).resolve()
    for base in (here, *here.parents):
        if (base / ".team" / "team.json").is_file() or (base / "AGENTS.md").is_file():
            return base
    return here.parent


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------- roster / subteams ----------------

@dataclass
class Worker:
    name: str
    role: str
    team: str
    is_orchestrator: bool = False


@dataclass
class Subteam:
    name: str
    members: list[str]
    orchestrator: str
    reminders_list: str | None = None


def load_team(root: Path) -> tuple[list[Worker], list[Subteam]]:
    """Workers (with team + role) and subteams from team.json."""
    data = _load_json(root / ".team" / "team.json") or {}
    roles = data.get("roles") or {}
    subteams_raw = data.get("subteams") or []
    subteams = [
        Subteam(
            name=s.get("name", "?"),
            members=list(s.get("members") or []),
            orchestrator=s.get("orchestrator") or (s.get("members") or [""])[0],
            reminders_list=s.get("reminders_list"),
        )
        for s in subteams_raw
        if isinstance(s, dict)
    ]
    team_of: dict[str, Subteam] = {m: st for st in subteams for m in st.members}
    workers: list[Worker] = []
    for name in data.get("members") or []:
        st = team_of.get(name)
        workers.append(
            Worker(
                name=name,
                role=(roles.get(name) or "").split(".")[0][:80],
                team=st.name if st else "?",
                is_orchestrator=bool(st and st.orchestrator == name),
            )
        )
    return workers, subteams


# ---------------- inbox (peer message bus) ----------------

@dataclass
class InboxMessage:
    id: str
    sender: str
    to: str
    subject: str
    body: str
    ts_ns: int
    consumed: bool


def load_inbox(root: Path, *, include_consumed: bool = True, limit: int = 200) -> list[InboxMessage]:
    """All inbox messages across recipients, newest first.

    Unread live directly under inbox/<recipient>/; consumed move to
    inbox/<recipient>/.consumed/ (team_inbox ack). We tag each accordingly.
    """
    inbox = root / ".team" / "inbox"
    msgs: list[InboxMessage] = []
    if not inbox.is_dir():
        return msgs
    for recipient_dir in inbox.iterdir():
        if not recipient_dir.is_dir() or recipient_dir.name.startswith("."):
            continue
        # unread
        for f in recipient_dir.glob("*.json"):
            m = _to_message(f, consumed=False)
            if m:
                msgs.append(m)
        # consumed
        if include_consumed:
            cdir = recipient_dir / ".consumed"
            if cdir.is_dir():
                for f in cdir.glob("*.json"):
                    m = _to_message(f, consumed=True)
                    if m:
                        msgs.append(m)
    msgs.sort(key=lambda m: m.ts_ns, reverse=True)
    return msgs[:limit]


def _to_message(path: Path, *, consumed: bool) -> InboxMessage | None:
    d = _load_json(path)
    if not d:
        return None
    return InboxMessage(
        id=d.get("id", path.stem),
        sender=d.get("from", "?"),
        to=d.get("to") or ((d.get("recipients") or ["?"])[0]),
        subject=d.get("subject", ""),
        body=d.get("body", ""),
        ts_ns=int(d.get("ts_ns") or 0),
        consumed=consumed,
    )


# ---------------- goals ----------------

@dataclass
class Goal:
    id: str
    title: str
    objective: str
    success_criteria: list[str]
    status: str


def load_goals(root: Path) -> list[Goal]:
    gdir = root / ".team" / "goals"
    out: list[Goal] = []
    if not gdir.is_dir():
        return out
    for f in sorted(gdir.glob("*.json")):
        d = _load_json(f)
        if not d:
            continue
        sc = d.get("success_criteria") or []
        sc = [str(x) for x in sc] if isinstance(sc, list) else [str(sc)]
        out.append(
            Goal(
                id=d.get("id", f.stem),
                title=d.get("title", f.stem),
                objective=str(d.get("objective", "")),
                success_criteria=sc,
                status=str(d.get("status", "")),
            )
        )
    return out


# ---------------- promotion / derivation candidates (approval queue) ----------------

@dataclass
class Candidate:
    kind: str          # skill | agent | term | preference | memory
    key: str
    detail: str
    source: str        # which detector


def _load_candidates_file(path: Path) -> list[dict[str, Any]]:
    """Candidate files are ``{<bucket>: [candidate, ...], ...}`` — e.g.
    {"agent": [...], "skill": []} for promotions, {"team_agent": [], "team_skill": []}
    for team-tier, {"preference": [...], "term": [...]} for derivations. We flatten
    every list-valued bucket. (A legacy top-level list / {"candidates": [...]} is also
    tolerated.)"""
    d = _load_json(path)
    if d is None:
        return []
    if isinstance(d, list):
        return [c for c in d if isinstance(c, dict)]
    if not isinstance(d, dict):
        return []
    out: list[dict[str, Any]] = []
    for v in d.values():
        if isinstance(v, list):
            out.extend(c for c in v if isinstance(c, dict))
    return out


def load_candidates(root: Path) -> list[Candidate]:
    """Open promotion/derivation/feedback candidates the detectors have surfaced.

    Paths verified against the live store: single-tier under .context/, team-tier
    per-worker under .team/<kind>/candidates/. The TUI surfaces these so a human can
    promote/decline — replacing the per-turn hook reminders that only reached the model.
    """
    out: list[Candidate] = []
    search = [
        (root / ".context" / "promotions" / "candidates.json", "promotion"),
        (root / ".context" / "memory-promotions" / "candidates.json", "derivation"),
        (root / ".context" / "feedback" / "candidates.json", "feedback"),
        (root / ".team" / "promotions" / "candidates", "team-promotion"),
        (root / ".team" / "derivations" / "candidates", "team-derivation"),
    ]
    for path, source in search:
        files: list[Path] = []
        if path.is_dir():
            files = sorted(path.glob("*.json"))
        elif path.is_file():
            files = [path]
        for f in files:
            for c in _load_candidates_file(f):
                skills = c.get("skills")
                detail = c.get("reason") or c.get("detail") or c.get("note") or ""
                if not detail and isinstance(skills, list):
                    detail = (
                        f"co-used {c.get('cousage', '?')}x across "
                        f"{c.get('distinct_sessions', '?')} sessions"
                    )
                out.append(
                    Candidate(
                        kind=str(c.get("kind", "?")),
                        key=str(c.get("key") or c.get("name") or "?"),
                        detail=str(detail),
                        source=f"{source}:{f.stem}" if path.is_dir() else source,
                    )
                )
    return out


# ---------------- aggregate snapshot ----------------

@dataclass
class Snapshot:
    workers: list[Worker] = field(default_factory=list)
    subteams: list[Subteam] = field(default_factory=list)
    inbox: list[InboxMessage] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)

    def unread_count_for(self, name: str) -> int:
        return sum(1 for m in self.inbox if m.to == name and not m.consumed)


def read_snapshot(root: Path) -> Snapshot:
    """One consistent read of the whole store for a render frame."""
    workers, subteams = load_team(root)
    return Snapshot(
        workers=workers,
        subteams=subteams,
        inbox=load_inbox(root),
        goals=load_goals(root),
        candidates=load_candidates(root),
    )
