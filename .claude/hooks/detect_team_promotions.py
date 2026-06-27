#!/usr/bin/env python3
"""Team/project-tier promotion: surface signals along the TIER BOUNDARY axis.

A sibling of ``detect_promotions.py`` (the per-WORKER loop, left byte-untouched). Where
the per-worker loop asks "did one worker repeat a signature across its sessions", this
hook reads the **inbox handoff structure** (who passes work to whom) and asks tier
questions. The trigger is the recurrence of a HANDOFF STRUCTURE, not of a task signature.

Five signals (the boundary axis = subteam membership from ``.project/team.json``):
- ``team_skill``    — branch ①: an INTRA-team workflow recurs (>= ``min_intra_handoffs``
                      across >=2 same-team workers) -> author a team skill.
- ``project_skill`` — an INTER-team flow recurs (>= ``min_inter_handoffs`` between two
                      teams) -> author a project-tier skill in ``.project/skills``.
- ``new_worker``    — branch ②, SIGNAL only: a team's intra flow is sparse but one worker
                      is overloaded (task-log ``worker_load``) -> consider adding a worker.
- ``rebalance``     — branch ③, SIGNAL only: a sparse team funnels all intra flow through
                      one worker pair -> review the role boundary between them.
- ``team_agent``    — DEPRECATED/read-only: team-tier sub-agents are not operated; new
                      candidates short-circuit to [], but the kind stays loadable so the
                      existing decisions survive (see policy ``_deprecated``).

How it stays conflict-free and non-invasive (inherited, all verified):
- **Read-only.** Reads the inbox and every worker's private ledger read-only; never
  writes a worker ledger. The per-worker loop (``detect_promotions.py``) is untouched (R2).
- **Per-record immutable store.** Candidates -> per-runner shard
  (``.project/promotions/candidates/<runner>.json``); decisions -> one immutable file per
  ``(kind, key)`` via atomic ``os.replace`` — never a shared JSON array edited by N writers.
- **Tier-scoped sync-back.** ``skip_if_skill_exists`` scans ``teams/<team>/.claude/skills``
  (team) / ``.project/skills`` (project), so a promoted asset is skipped at its own tier.

Run modes: hook (stdin payload, SessionStart), ``evaluate`` (CLI inspect), and
``resolve`` (record a promote/decline decision). Hooks never crash the agent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hooklib import merge as _merge, project_dir_simple as project_dir  # noqa: E402

DEFAULTS: dict[str, Any] = {
    "agent_ledger": {
        "tasks": ".context/task-log/tasks.jsonl",
        "events": ".context/task-log/events.jsonl",
    },
    "log": {
        "candidates_dir": ".project/promotions/candidates",
        "decisions_dir": ".project/promotions/decisions",
    },
    "team_skill_promotion": {
        "min_distinct_agents": 2,
        "min_total_recurrence": 2,
        "skip_if_skill_exists": True,
        "max_candidates": 20,
    },
    "team_agent_promotion": {
        "min_package_size": 2,
        "min_distinct_agents": 2,
        "skip_if_agent_exists": True,
        "max_candidates": 20,
    },
    "governance": {"mode": "owner-authors", "company_owner": "orchestrator", "authoring_owner": "orchestrator"},
}

MAX_SKILLS_PER_OCCURRENCE = 6
# Promotion kinds. team_skill/project_skill author SHARED skills; new_worker/rebalance
# are SIGNAL-only diagnoses (no auto-author). team_agent is retained READ-ONLY so the two
# existing team_agent decisions still load and `resolve --kind team_agent` keeps working;
# new team_agent candidates are no longer minted (policy marks it _deprecated, evaluate
# short-circuits) because team-tier sub-agents are not operated (3-tier arch §2-1).
KINDS = ("team_skill", "team_agent", "project_skill", "new_worker", "rebalance")
ORCHESTRATOR = "orchestrator"  # inbox node name; never a worker (no private ledger)
# Edge classes between two inbox endpoints, keyed on subteam membership.
EDGE_INTRA, EDGE_INTER, EDGE_EXT, EDGE_ORCH = "INTRA", "INTER", "EXT", "ORCH"
CONTEXT_EVENTS = {"PostToolUse", "PreToolUse", "SessionStart", "UserPromptSubmit", "Stop"}


# ---------------- roots & policy ----------------

def find_team_root(start: Path) -> Path | None:
    """Nearest ancestor (or self) that holds a ``.project/`` directory, else ``None``.

    When run from a peer agent (project root agents/<name>/), walk up to the team
    root; when run from the team root itself, return it. Returning ``None`` when no
    ``.project/`` exists is load-bearing: it stops the SessionStart hook from minting a
    fake ``.project/`` skeleton (and self-pollinating the search) in a non-team clone.
    """
    cur = start.resolve()
    for _ in range(10):
        if (cur / ".project").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def load_policy(team_root: Path) -> dict[str, Any]:
    policy_path = team_root / ".project/policies/team-promotion.json"
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    return _merge(DEFAULTS, raw)


def governance_owner(policy: dict[str, Any]) -> str:
    gov = policy.get("governance")
    if isinstance(gov, dict):
        owner = gov.get("company_owner") or gov.get("authoring_owner")
        if isinstance(owner, str) and owner.strip():
            return owner.strip()
    return ORCHESTRATOR


def _subteam_members(team_root: Path) -> dict[str, list[str]]:
    try:
        data = json.loads((team_root / ".project" / "team.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, list[str]] = {}
    if isinstance(data, dict):
        for st in data.get("subteams") or []:
            if isinstance(st, dict) and isinstance(st.get("name"), str):
                out[st["name"]] = [m for m in (st.get("members") or []) if isinstance(m, str)]
    return out


def _worker_at(team_root: Path, candidate: Path) -> str | None:
    try:
        rel = candidate.relative_to(team_root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 3 or parts[0] != "teams":
        return None
    team, worker = parts[1], parts[2]
    return worker if worker in _subteam_members(team_root).get(team, []) else None


def _identity_from_cwd(team_root: Path) -> str | None:
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
    log_w = _worker_at(team_root, logical) or _worker_at(root_res, logical)
    phys_w = _worker_at(root_res, physical) or _worker_at(team_root, physical)
    if log_w and phys_w and log_w == phys_w:
        return log_w
    return "__cwd_failclosed__"


def resolve_actor(team_root: Path, explicit: str | None) -> str:
    cwd_id = _identity_from_cwd(team_root)
    if cwd_id is not None:
        return cwd_id
    return explicit or os.environ.get("CLAUDE_AGENT_NAME") or "team"


# ---------------- shared readers (self-contained copies) ----------------

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return records
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def existing_skills(team_root: Path) -> set[str]:
    skills_dir = team_root / ".claude/skills"
    names: set[str] = set()
    if not skills_dir.is_dir():
        return names
    for child in skills_dir.iterdir():
        if child.is_dir() and (child / "SKILL.md").exists():
            names.add(child.name)
    return names


def agent_texts(team_root: Path) -> list[str]:
    agents_dir = team_root / ".claude/agents"
    texts: list[str] = []
    if not agents_dir.is_dir():
        return texts
    for child in sorted(agents_dir.glob("*.md")):
        if child.name == "agents.md":
            continue
        try:
            texts.append(child.read_text(encoding="utf-8"))
        except OSError:
            continue
    return texts


def _covered_by_agent(skills: list[str], texts: list[str]) -> bool:
    return any(all(skill in text for skill in skills) for text in texts)


def _is_worker_dir(p: Path) -> bool:
    """A roll-up worker is a folder carrying a private LEDGER (.context/task-log or
    .context/memory-log). That is the exact surface this roll-up reads, and it cleanly
    excludes non-worker folders that hold only handoff notes under .context (e.g. an
    orchestrator scratch folder) as well as TEAM folders, which are explicitly marked
    with a ``.team-folder`` sentinel so they are never counted as workers."""
    if not p.is_dir() or p.name.startswith(".") or (p / ".team-folder").exists():
        return False
    ctx = p / ".context"
    return (ctx / "task-log").is_dir() or (ctx / "memory-log").is_dir()


def worker_dirs(team_root: Path) -> dict[str, Path]:
    """Map worker NAME -> folder across both topologies (teams/<team>/<w> and agents/<w>).

    Worker names are globally unique, so name is a safe key. See _is_worker_dir for the
    identification rule (ledger-bearing folder)."""
    found: dict[str, Path] = {}
    teams_dir = team_root / "teams"
    if teams_dir.is_dir():
        for team in sorted(teams_dir.iterdir(), key=lambda p: p.name):
            if not team.is_dir() or team.name.startswith("."):
                continue
            for child in sorted(team.iterdir(), key=lambda p: p.name):
                if _is_worker_dir(child):
                    found.setdefault(child.name, child)
    agents_dir = team_root / "agents"
    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir(), key=lambda p: p.name):
            if _is_worker_dir(child):
                found.setdefault(child.name, child)
    return found


def list_agents(team_root: Path) -> list[str]:
    return sorted(worker_dirs(team_root))


def load_agent_ledgers(team_root: Path, policy: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read every peer's private ledger read-only, tagging each record with its agent."""
    rel = policy["agent_ledger"]
    tasks: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for agent, adir in sorted(worker_dirs(team_root).items()):
        for rec in load_jsonl(adir / rel["tasks"]):
            rec = dict(rec)
            rec["_agent"] = agent
            tasks.append(rec)
        for rec in load_jsonl(adir / rel["events"]):
            rec = dict(rec)
            rec["_agent"] = agent
            events.append(rec)
    return tasks, events


# ---------------- tier topology + inbox handoff signal ----------------

def team_of(team_root: Path) -> dict[str, str]:
    """Map worker NAME -> subteam NAME from the roster (``.project/team.json``).

    The roster (not the folder layout) is the single source of truth for tier
    membership. Workers absent from any ``subteams[].members`` (e.g. ``orchestrator``,
    a removed worker) get no mapping and fall to ORCH/EXT in ``classify_edge``.
    """
    data: Any = None
    for cand in (team_root / ".project" / "team.json", team_root / "team.json"):
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
            break
        except (OSError, json.JSONDecodeError):
            data = None
    if not isinstance(data, dict):
        return {}
    mapping: dict[str, str] = {}
    for sub in data.get("subteams") or []:
        if not isinstance(sub, dict):
            continue
        tname = str(sub.get("name") or "").strip()
        for member in sub.get("members") or []:
            if isinstance(member, str) and member.strip():
                mapping.setdefault(member.strip(), tname)  # a worker belongs to exactly one team
    return mapping


def is_team_name(name: str, team_map: dict[str, str]) -> bool:
    """True if ``name`` is a subteam name (a value in the worker->team map), not a worker."""
    return name in set(team_map.values())


def inbox_edges(
    team_root: Path, team_map: dict[str, str] | None = None, *,
    exclude_self: bool = True, exclude_orchestrator: bool = True,
    orchestrator_name: str = ORCHESTRATOR,
) -> tuple["Counter[tuple[str, str]]", dict[tuple[str, str], list[int]]]:
    """Aggregate inbox handoffs as a directed ``from -> to`` multigraph (WORKER-keyed).

    The team/project promotion trigger is the RECURRENCE OF A HANDOFF STRUCTURE
    (who passes work to whom), not the recurrence of a single task signature. This
    reads that structure from the inbox, keeping endpoints at the WORKER granularity so
    the tier-boundary axis (classify_edge) stays accurate.

    - Team-only inbox model (2026-06-27): mailboxes live in each TEAM folder
      ``teams/<team>/.claude/inbox`` (+ the orchestrator's virtual box and the legacy
      ``.project/inbox/.archive``). Walks ALL of them with ``os.walk`` so hidden
      ``.consumed/``/``.claimed/`` shards are traversed (``glob('**')`` skips dotted dirs).
    - Team-mailbox message (``to_team`` set): if claimed, the single ``claimed_by`` worker
      is the real target; if not yet claimed, fan out over team members (recipients). A bare
      team name in ``to`` is NOT treated as a worker (skipped) so it can't pollute edges.
    - Returns the per-edge count AND a list of ``ts_ns`` per edge so a consumer can judge
      *temporal* recurrence (``len >= 2`` = handoff happened on at least two occasions).
    """
    team_map = team_map or {}
    # Collect every mailbox root: per-team folders + orchestrator virtual box + legacy
    # central inbox (archive of pre-migration mail). Missing dirs are skipped.
    inbox_roots: list[Path] = []
    teams_dir = team_root / "teams"
    if teams_dir.is_dir():
        for child in sorted(teams_dir.iterdir()):
            box = child / ".claude" / "inbox"
            if box.is_dir():
                inbox_roots.append(box)
        orch = teams_dir / ".orchestrator" / "inbox"
        if orch.is_dir():
            inbox_roots.append(orch)
    legacy = team_root / ".project" / "inbox"
    if legacy.is_dir():
        inbox_roots.append(legacy)
    edges: "Counter[tuple[str, str]]" = Counter()
    edge_ts: dict[tuple[str, str], list[int]] = {}
    if not inbox_roots:
        return edges, edge_ts
    all_files = [
        Path(dirpath) / name
        for inbox_root in inbox_roots
        for dirpath, _dirs, filenames in os.walk(inbox_root)
        for name in filenames
        if name.endswith(".json")
    ]
    for fpath in all_files:
        try:
            rec = json.loads(fpath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rec, dict):
            continue
        sender = str(rec.get("from") or "").strip()
        if not sender:
            continue
        # Team-mailbox message (to_team set): resolve destinations to WORKERS so the
        # tier-boundary axis stays worker-accurate. If claimed, the single claimer is
        # the real handoff target; if unclaimed yet, fan out over the team members
        # (recipients) as the candidate handlers. A plain individual message just uses
        # its recipients/to as before (legacy archive mail).
        claimed_by = str(rec.get("claimed_by") or "").strip()
        if rec.get("to_team") and claimed_by:
            dests = [claimed_by]
        else:
            dests = [d.strip() for d in (rec.get("recipients") or []) if isinstance(d, str) and d.strip()]
            if not dests:
                to = str(rec.get("to") or "").strip()
                # A team name in `to` (unclaimed, no recipients) isn't a worker — skip
                # rather than misclassify it as EXT and pollute the edge set.
                dests = [to] if (to and not is_team_name(to, team_map)) else []
        try:
            ts = int(rec.get("ts_ns") or 0)
        except (TypeError, ValueError):
            ts = 0
        for dest in dests:
            if exclude_self and dest == sender:
                continue
            if exclude_orchestrator and (sender == orchestrator_name or dest == orchestrator_name):
                continue
            edges[(sender, dest)] += 1
            edge_ts.setdefault((sender, dest), []).append(ts)
    return edges, edge_ts


def classify_edge(a: str, b: str, team_map: dict[str, str], orchestrator_name: str = ORCHESTRATOR) -> str:
    """Classify a handoff edge: ORCH > EXT > (INTRA|INTER).

    INTRA = both endpoints in the SAME subteam (team-skill signal); INTER = different
    subteams (project-skill signal); EXT = an endpoint not on the roster; ORCH = an
    endpoint is the orchestrator (a coordination edge, never a team/project signal).
    """
    if a == orchestrator_name or b == orchestrator_name:
        return EDGE_ORCH
    ta, tb = team_map.get(a, ""), team_map.get(b, "")
    if not ta or not tb:
        return EDGE_EXT
    return EDGE_INTRA if ta == tb else EDGE_INTER


def _fmt_pairs(pairs: dict[tuple[str, str], int], top: int = 3) -> list[str]:
    # Sort by count desc, then by the edge tuple asc as a tie-breaker so the displayed
    # order is fully deterministic regardless of os.walk traversal order.
    items = sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    return [f"{a}->{b}({n})" for (a, b), n in items]


def _team_skill_present(team: str, team_root: Path) -> bool:
    """True if the team already has an authored team skill (a SKILL.md under its
    ``teams/<team>/.claude/skills``). Mirrors ``existing_skills`` but per-team."""
    skills_dir = team_root / "teams" / team / ".claude" / "skills"
    if not skills_dir.is_dir():
        return False
    return any(child.is_dir() and (child / "SKILL.md").exists() for child in skills_dir.iterdir())


def existing_project_skills(team_root: Path) -> set[str]:
    """Project-tier skills authored under ``.project/skills``. The directory is absent
    until the first project_skill is promoted (None-safe: returns the empty set)."""
    skills_dir = team_root / ".project" / "skills"
    names: set[str] = set()
    if not skills_dir.is_dir():
        return names
    for child in skills_dir.iterdir():
        if child.is_dir() and (child / "SKILL.md").exists():
            names.add(child.name)
    return names


# ---------------- candidate detection (TIER-boundary axis) ----------------

def team_skill_candidates_inbox(
    edges: "Counter[tuple[str, str]]",
    edge_ts: dict[tuple[str, str], list[int]],
    team_map: dict[str, str],
    rules: dict[str, Any],
    team_root: Path,
    decided: dict[str, Any],
) -> list[dict[str, Any]]:
    """Branch ① (normal): a shared INTRA-team workflow.

    Several workers in the SAME subteam hand work to each other often enough that the
    workflow should be frozen into a team skill. Keyed on TEAM (the boundary axis), not
    on the company-wide distinct-agent count.
    """
    min_intra = int(rules.get("min_intra_handoffs", 8))
    min_agents = int(rules.get("min_distinct_agents", 2))
    skip_existing = bool(rules.get("skip_if_skill_exists", True))

    per_team: dict[str, dict[str, Any]] = {}
    for (a, b), n in edges.items():
        if classify_edge(a, b, team_map) != EDGE_INTRA:
            continue
        group = per_team.setdefault(
            team_map[a], {"total": 0, "workers": set(), "pairs": {}, "recurring": 0}
        )
        group["total"] += n
        group["workers"].update((a, b))
        group["pairs"][(a, b)] = n
        if len(edge_ts.get((a, b), [])) >= 2:
            group["recurring"] += 1

    out: list[dict[str, Any]] = []
    for team in sorted(per_team):
        group = per_team[team]
        if group["total"] < min_intra or len(group["workers"]) < min_agents:
            continue
        if skip_existing and _team_skill_present(team, team_root):
            continue
        if team in decided:
            continue
        out.append({
            "kind": "team_skill", "key": team, "team": team,
            "intra_handoffs": group["total"], "distinct_agents": len(group["workers"]),
            "agents": sorted(group["workers"]), "recurring_pairs": group["recurring"],
            "top_pairs": _fmt_pairs(group["pairs"], 3), "evidence": "inbox-intra",
        })
    out.sort(key=lambda c: (-c["intra_handoffs"], -c["distinct_agents"], c["key"]))
    return out[: int(rules.get("max_candidates", 20))]


def project_skill_candidates(
    edges: "Counter[tuple[str, str]]",
    team_map: dict[str, str],
    rules: dict[str, Any],
    project_skills: set[str],
    decided: dict[str, Any],
) -> list[dict[str, Any]]:
    """Project tier: a recurring CROSS-team data handoff.

    Two distinct subteams exchange work (INTER) often enough that the cross-team flow
    should be frozen into a project-tier skill (orchestrator single-entry). Keyed on the
    sorted team pair ``"teamA+teamB"``.
    """
    min_inter = int(rules.get("min_inter_handoffs", 20))
    min_dirs = int(rules.get("min_directions", 1))
    skip_existing = bool(rules.get("skip_if_skill_exists", True))

    per_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for (a, b), n in edges.items():
        if classify_edge(a, b, team_map) != EDGE_INTER:
            continue
        ta, tb = team_map[a], team_map[b]
        pair = tuple(sorted((ta, tb)))
        group = per_pair.setdefault(pair, {"total": 0, "dirs": set(), "edges": {}})
        group["total"] += n
        group["dirs"].add((ta, tb))
        group["edges"][(a, b)] = n

    out: list[dict[str, Any]] = []
    for pair in sorted(per_pair):
        group = per_pair[pair]
        if group["total"] < min_inter or len(group["dirs"]) < min_dirs:
            continue
        key = "+".join(pair)
        if skip_existing and key in project_skills:
            continue
        if key in decided:
            continue
        out.append({
            "kind": "project_skill", "key": key, "teams": list(pair),
            "inter_handoffs": group["total"], "directions": len(group["dirs"]),
            "top_pairs": _fmt_pairs(group["edges"], 3), "evidence": "inbox-inter",
        })
    out.sort(key=lambda c: (-c["inter_handoffs"], -c["directions"], c["key"]))
    return out[: int(rules.get("max_candidates", 20))]


def worker_load(team_root: Path, worker: str, adir: Path, policy: dict[str, Any]) -> dict[str, Any]:
    """Load metric for one worker, from its private task-log ledger (deterministic).

    load = task_weight*tasks + skill_event_weight*skill_uses + signature_weight*signatures.
    Used by the sparsity diagnosis to tell "this worker is overloaded" from
    "this team is just quiet".
    """
    rel = policy["agent_ledger"]
    tasks = load_jsonl(adir / rel["tasks"])
    events = load_jsonl(adir / rel["events"])
    skill_uses = sum(1 for e in events if str(e.get("skill") or "").strip())
    sigs = {str(t.get("signature") or "").strip() for t in tasks if str(t.get("signature") or "").strip()}
    weights = policy.get("load_metric", {})
    load = (
        float(weights.get("task_weight", 1.0)) * len(tasks)
        + float(weights.get("skill_event_weight", 0.5)) * skill_uses
        + float(weights.get("signature_weight", 0.5)) * len(sigs)
    )
    return {
        "worker": worker, "tasks": len(tasks), "skill_uses": skill_uses,
        "signatures": len(sigs), "load": round(load, 3),
    }


def diagnose_sparse_teams(
    team_root: Path,
    edges: "Counter[tuple[str, str]]",
    team_map: dict[str, str],
    workers: dict[str, Path],
    policy: dict[str, Any],
    decided_new_worker: dict[str, Any],
    decided_rebalance: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Branches ②/③: when a team's INTRA handoff volume is sparse, diagnose WHY.

    A quiet team is not automatically fine. Two failure modes are surfaced as SIGNALS
    (no auto-author):
      ② new_worker  — one worker carries a heavy task-log load while the team barely
                       hands off internally -> the team likely needs another worker.
                       A solo team (no intra possible) qualifies on the load floor alone.
      ③ rebalance   — a single worker pair funnels all the intra flow and the rest of
                       the team is idle -> the role boundary between that pair may be wrong.

    Absolute floors (not ratio-to-mean) are used so the diagnosis stays deterministic
    when many workers have an empty ledger (mean collapses toward zero).
    """
    cfg = policy.get("sparsity_diagnosis", {})
    if not cfg.get("enable", True):
        return [], []
    sparsity = int(cfg.get("sparsity_threshold", 8))
    overload_ratio = float(cfg.get("overload_ratio", 2.0))
    min_overload = float(cfg.get("min_overload_load", 6.0))
    pair_conc = int(cfg.get("pair_concentration", 5))

    members_by_team: dict[str, list[str]] = {}
    for worker, team in team_map.items():
        if team:
            members_by_team.setdefault(team, []).append(worker)

    intra_by_team: dict[str, dict[tuple[str, str], int]] = {}
    total_by_team: dict[str, int] = {}
    for (a, b), n in edges.items():
        if classify_edge(a, b, team_map) == EDGE_INTRA:
            team = team_map[a]
            intra_by_team.setdefault(team, {})[(a, b)] = n
            total_by_team[team] = total_by_team.get(team, 0) + n

    new_worker: list[dict[str, Any]] = []
    rebalance: list[dict[str, Any]] = []
    for team in sorted(members_by_team):
        members = members_by_team[team]
        if total_by_team.get(team, 0) >= sparsity:
            continue  # branch ① (normal, handled by team_skill_candidates_inbox)

        loads = [worker_load(team_root, w, workers[w], policy) for w in members if w in workers]
        if loads:
            mean = sum(l["load"] for l in loads) / len(loads)
            top = max(loads, key=lambda l: l["load"])
            overloaded = top["load"] >= min_overload and (
                len(loads) == 1 or (mean > 0 and top["load"] >= overload_ratio * mean)
            )
            if overloaded:
                key = f"{team}:{top['worker']}"
                if key not in decided_new_worker:
                    new_worker.append({
                        "kind": "new_worker", "key": key, "team": team,
                        "overloaded_worker": top["worker"], "load": top["load"],
                        "team_mean_load": round(mean, 3), "members": sorted(members),
                        "reason": "solo-overload" if len(loads) == 1 else "intra-sparse-overload",
                    })

        if len(members) >= 2:
            pairs = intra_by_team.get(team, {})
            if pairs:
                (pa, pb), pn = max(pairs.items(), key=lambda kv: kv[1])
                other = sum(n for edge, n in pairs.items() if edge != (pa, pb))
                if pn >= pair_conc and other == 0:
                    key = f"{team}:{pa}->{pb}"
                    if key not in decided_rebalance:
                        rebalance.append({
                            "kind": "rebalance", "key": key, "team": team,
                            "pair": [pa, pb], "concentration": pn, "other_intra": other,
                            "members": sorted(members), "reason": "single-pair-funnel",
                        })

    new_worker.sort(key=lambda c: (-c["load"], c["key"]))
    rebalance.sort(key=lambda c: (-c["concentration"], c["key"]))
    mx = int(cfg.get("max_candidates", 20))
    return new_worker[:mx], rebalance[:mx]


# ---------------- legacy candidate detection (distinct-AGENT axis, read-only) ----------------

def team_skill_candidates(
    tasks: list[dict[str, Any]], rules: dict[str, Any], skills: set[str], decided: dict[str, Any]
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for task in tasks:
        signature = str(task.get("signature") or "").strip()
        if not signature:
            continue
        group = groups.setdefault(
            signature, {"count": 0, "agents": set(), "objectives": [], "skills": set()}
        )
        group["count"] += 1
        group["agents"].add(str(task.get("_agent") or task.get("agent") or ""))
        objective = str(task.get("objective") or "").strip()
        if objective and objective not in group["objectives"]:
            group["objectives"].append(objective)
        for skill in task.get("skills") or []:
            if isinstance(skill, str) and skill:
                group["skills"].add(skill)

    min_agents = int(rules.get("min_distinct_agents", 2))
    min_total = int(rules.get("min_total_recurrence", 2))
    skip_existing = bool(rules.get("skip_if_skill_exists", True))

    candidates: list[dict[str, Any]] = []
    for signature in sorted(groups):
        group = groups[signature]
        agents = {a for a in group["agents"] if a}
        if skip_existing and signature in skills:
            continue
        if signature in decided:
            continue
        if len(agents) < min_agents or group["count"] < min_total:
            continue
        candidates.append(
            {
                "kind": "team_skill",
                "key": signature,
                "signature": signature,
                "recurrence": group["count"],
                "distinct_agents": len(agents),
                "agents": sorted(agents),
                "objectives": group["objectives"][:3],
                "related_skills": sorted(group["skills"]),
            }
        )
    candidates.sort(key=lambda c: (-c["distinct_agents"], -c["recurrence"], c["key"]))
    return candidates[: int(rules.get("max_candidates", 20))]


def _team_occurrences(
    tasks: list[dict[str, Any]], events: list[dict[str, Any]], min_size: int
) -> list[tuple[str, set[str]]]:
    """Skill bundles keyed by AGENT (not session). Session bucketing here would
    collapse distinct agents into one bucket and break the distinct-agent count."""
    occurrences: list[tuple[str, set[str]]] = []
    for task in tasks:
        skills = {s for s in (task.get("skills") or []) if isinstance(s, str) and s}
        if len(skills) >= min_size:
            occurrences.append((str(task.get("_agent") or ""), skills))

    by_agent: dict[str, set[str]] = {}
    for event in events:
        skill = event.get("skill")
        if isinstance(skill, str) and skill:
            by_agent.setdefault(str(event.get("_agent") or ""), set()).add(skill)
    for agent, skills in by_agent.items():
        if len(skills) >= min_size:
            occurrences.append((agent, skills))
    return occurrences


def team_agent_candidates(
    tasks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    rules: dict[str, Any],
    agent_text_blobs: list[str],
    decided: dict[str, Any],
) -> list[dict[str, Any]]:
    min_size = int(rules.get("min_package_size", 2))
    min_agents = int(rules.get("min_distinct_agents", 2))
    skip_existing = bool(rules.get("skip_if_agent_exists", True))

    occurrences = _team_occurrences(tasks, events, min_size)

    counts: dict[frozenset[str], set[str]] = {}
    for agent, skills in occurrences:
        if not agent:
            continue
        ordered = sorted(skills)[:MAX_SKILLS_PER_OCCURRENCE]
        for size in range(min_size, len(ordered) + 1):
            for combo in combinations(ordered, size):
                counts.setdefault(frozenset(combo), set()).add(agent)

    qualifying = {pkg: agents for pkg, agents in counts.items() if len(agents) >= min_agents}
    keys = list(qualifying)
    maximal = [pkg for pkg in keys if not any(other != pkg and pkg < other for other in keys)]

    candidates: list[dict[str, Any]] = []
    for package in maximal:
        skills = sorted(package)
        key = "+".join(skills)
        if key in decided:
            continue
        if skip_existing and _covered_by_agent(skills, agent_text_blobs):
            continue
        agents = qualifying[package]
        candidates.append(
            {
                "kind": "team_agent",
                "key": key,
                "skills": skills,
                "distinct_agents": len(agents),
                "agents": sorted(agents),
            }
        )
    candidates.sort(key=lambda c: (-c["distinct_agents"], c["key"]))
    return candidates[: int(rules.get("max_candidates", 20))]


# ---------------- decisions (per-record immutable, folded) ----------------

def _safe(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z가-힣._-]+", "_", text).strip("_")
    return (slug or "x")[:120]


def _roster_members(team_root: Path) -> set[str]:
    """The set of registered worker identities from .project/team.json.

    Returns an empty set if the roster is unreadable — callers treat that as
    "cannot validate" and fall back to fail-open so a missing roster never blocks
    legitimate work (the guard only fires when the roster IS readable).
    """
    try:
        data = json.loads((team_root / ".project" / "team.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    members = data.get("members") if isinstance(data, dict) else None
    roster = {m for m in (members or []) if isinstance(m, str)}
    # The company-wide coordinator is a legitimate identity that is not in the
    # subteam member list but owns its own inbox; always treat it as registered.
    return roster | {"orchestrator"}


def _validated_runner(team_root: Path, runner: str) -> str:
    """Fold an unregistered identity into the shared ``team`` bucket.

    A typo in ``CLAUDE_AGENT_NAME`` (e.g. ``paper-socut``) used to mint a ghost
    candidate shard alongside the real worker's. Validating against the roster
    folds such typos into ``team`` so no per-runner ghost file is created while the
    signal is still counted. The ``team`` fallback itself is always allowed; an
    empty/unreadable roster also passes through (fail-open, no roster = no guard).
    """
    if runner == "team":
        return runner
    roster = _roster_members(team_root)
    if not roster or runner in roster:
        return runner
    return "team"


def load_team_decisions(decisions_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {kind: {} for kind in KINDS}
    if not decisions_dir.is_dir():
        return out
    for path in sorted(decisions_dir.glob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        kind = rec.get("kind")
        key = rec.get("key")
        if kind in out and isinstance(key, str) and key:
            out[kind][key] = rec
    return out


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# ---------------- evaluate / surface / persist ----------------

def evaluate(team_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    """Surface five tier-aware promotion signals from the inbox handoff structure + task-log loads.

    - team_skill   (branch ①): recurring INTRA-team workflow -> author a team skill.
    - project_skill          : recurring INTER-team flow      -> author a project skill.
    - new_worker   (branch ②): sparse team + overloaded worker -> SIGNAL: add a worker.
    - rebalance    (branch ③): sparse team + single-pair funnel -> SIGNAL: review boundaries.
    - team_agent             : read-only/deprecated (team-tier sub-agents not operated);
                               new candidates short-circuit to [] when policy marks it _deprecated,
                               but the kind stays loadable so the two existing decisions survive.
    """
    decisions = load_team_decisions(team_root / policy["log"]["decisions_dir"])
    team_map = team_of(team_root)
    workers = worker_dirs(team_root)
    inbox_cfg = policy.get("inbox", {})
    edges, edge_ts = inbox_edges(
        team_root, team_map,
        exclude_self=bool(inbox_cfg.get("exclude_self", True)),
        exclude_orchestrator=bool(inbox_cfg.get("exclude_orchestrator", True)),
        orchestrator_name=str(inbox_cfg.get("orchestrator_name", ORCHESTRATOR)),
    )

    team_skill = team_skill_candidates_inbox(
        edges, edge_ts, team_map, policy.get("team_skill_inbox_promotion", {}),
        team_root, decisions["team_skill"],
    )
    project_skill = project_skill_candidates(
        edges, team_map, policy.get("project_skill_promotion", {}),
        existing_project_skills(team_root), decisions["project_skill"],
    )
    new_worker, rebalance = diagnose_sparse_teams(
        team_root, edges, team_map, workers, policy,
        decisions["new_worker"], decisions["rebalance"],
    )

    agent_rules = policy.get("team_agent_promotion", {})
    if agent_rules.get("_deprecated"):
        team_agent: list[dict[str, Any]] = []
    else:
        tasks, events = load_agent_ledgers(team_root, policy)
        team_agent = team_agent_candidates(
            tasks, events, agent_rules, agent_texts(team_root), decisions["team_agent"]
        )

    return {
        "team_skill": team_skill, "team_agent": team_agent, "project_skill": project_skill,
        "new_worker": new_worker, "rebalance": rebalance,
    }


def write_candidates_shard(team_root: Path, policy: dict[str, Any], candidates: dict[str, Any], runner: str) -> Path:
    runner = _validated_runner(team_root, runner)
    path = team_root / policy["log"]["candidates_dir"] / f"{_safe(runner)}.json"
    _atomic_write_json(path, candidates)
    return path


def format_surface(candidates: dict[str, Any], governance: dict[str, Any]) -> str:
    lines: list[str] = []
    for cand in candidates.get("team_skill", []):
        pairs = ", ".join(cand.get("top_pairs", []))
        lines.append(
            f"- [team_skill] team '{cand['key']}': intra-handoffs {cand['intra_handoffs']} "
            f"across {cand['distinct_agents']} workers ({pairs}) -> author a shared team workflow skill"
        )
    for cand in candidates.get("team_agent", []):  # deprecated -> empty list -> no lines
        package = ", ".join(cand.get("skills", []))
        lines.append(
            f"- [team_agent] skill package [{package}] used by "
            f"{cand['distinct_agents']} agents ({', '.join(cand['agents'])})"
        )
    for cand in candidates.get("project_skill", []):
        pairs = ", ".join(cand.get("top_pairs", []))
        lines.append(
            f"- [project_skill] cross-team flow '{cand['key']}': inter-handoffs {cand['inter_handoffs']} "
            f"({pairs}) -> author a project-tier skill"
        )
    for cand in candidates.get("new_worker", []):
        lines.append(
            f"- [new_worker] team '{cand['team']}' sparse but worker '{cand['overloaded_worker']}' "
            f"overloaded (load {cand['load']}, team-mean {cand['team_mean_load']}) "
            f"-> SIGNAL: consider adding a worker to this team"
        )
    for cand in candidates.get("rebalance", []):
        pair = cand.get("pair", ["?", "?"])
        lines.append(
            f"- [rebalance] team '{cand['team']}' sparse but pair {pair[0]}->{pair[1]} "
            f"concentrates {cand['concentration']} of intra flow "
            f"-> SIGNAL: review role boundaries for this pair"
        )
    if not lines:
        return ""
    owner = governance.get("authoring_owner", "data-curator")
    mode = governance.get("mode", "owner-authors")
    header = (
        "Team-promotion conditions were met (signals recur across distinct workers/teams). "
        f"Governance: {mode} (owner: {owner}). Anyone proposes via the inbox; the owner authors once and closes:\n"
        "- team_skill    -> `write-skill` into teams/<team>/.claude/skills (team-tier workflow).\n"
        "- project_skill -> `write-skill` into .project/skills (project-tier; created on first promotion).\n"
        "- new_worker    -> SIGNAL only: review `team-init add-subteam` / `create-team-agent`. No auto-author.\n"
        "- rebalance     -> SIGNAL only: review role boundaries in .project/team.json. No auto-author.\n"
        "- close any: `.claude/hooks/detect_team_promotions.py resolve --kind <kind> --key <key> --decision promote|decline`.\n"
    )
    return header + "\n".join(lines)


def emit_hook_context(message: str, event_name: str = "SessionStart") -> None:
    if not message:
        return
    if event_name not in CONTEXT_EVENTS:
        event_name = "SessionStart"
    payload = {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": message}}
    print(json.dumps(payload, ensure_ascii=False))


# ---------------- run modes ----------------

def run_hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    team_root = find_team_root(project_dir(payload))
    if team_root is None:
        return 0  # not a team checkout: write nothing, surface nothing
    policy = load_policy(team_root)
    candidates = evaluate(team_root, policy)
    runner = os.environ.get("CLAUDE_AGENT_NAME") or "team"
    write_candidates_shard(team_root, policy, candidates, runner)
    event_name = str(payload.get("hook_event_name") or "SessionStart")
    emit_hook_context(format_surface(candidates, policy.get("governance", {})), event_name)
    return 0


def run_evaluate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_team_promotions.py evaluate")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--check", action="store_true", help="Exit 1 when any team candidate exists")
    args = parser.parse_args(argv)
    start = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    team_root = find_team_root(start)
    if team_root is None:
        print(f"no team root (.project/) found from {start}")
        return 0
    policy = load_policy(team_root)
    candidates = evaluate(team_root, policy)
    runner = os.environ.get("CLAUDE_AGENT_NAME") or "team"
    path = write_candidates_shard(team_root, policy, candidates, runner)
    total = sum(len(candidates.get(kind, [])) for kind in KINDS)
    if args.check and total:
        print(f"{total} team-promotion candidate(s) pending", file=sys.stderr)
        return 1
    breakdown = " / ".join(f"{len(candidates.get(kind, []))} {kind}" for kind in KINDS)
    print(f"{breakdown} -> {path}")
    return 0


def run_resolve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_team_promotions.py resolve")
    parser.add_argument("--kind", required=True, choices=list(KINDS))
    parser.add_argument("--key", required=True, help="Candidate key (signature or skill+skill)")
    parser.add_argument("--decision", required=True, choices=["promote", "decline"])
    parser.add_argument("--reason", default="")
    parser.add_argument("--by", default=None, help="Who decided (default: $CLAUDE_AGENT_NAME)")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)
    start = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    team_root = find_team_root(start)
    if team_root is None:
        print(f"no team root (.project/) found from {start}; cannot resolve", file=sys.stderr)
        return 1
    policy = load_policy(team_root)
    by = resolve_actor(team_root, args.by)
    owner = governance_owner(policy)
    if by != owner:
        print(f"only the governance owner '{owner}' may resolve team promotions (you are '{by}')", file=sys.stderr)
        return 1
    record = {
        "kind": args.kind,
        "key": args.key,
        "decision": args.decision,
        "reason": args.reason.strip(),
        "by": by,
        "ts_ns": time.time_ns(),
    }
    # Filename must be unique per EXACT (kind, key). _safe() is many-to-one, so a
    # short hash of the exact key prevents distinct keys (e.g. "a+b+c" vs "a_b+c")
    # from colliding to one file and silently overwriting each other's decision.
    digest = hashlib.sha1(args.key.encode("utf-8")).hexdigest()[:8]
    filename = f"{args.kind}__{_safe(args.key)}__{digest}.json"
    path = team_root / policy["log"]["decisions_dir"] / filename
    _atomic_write_json(path, record)
    # Refresh this runner's shard so the resolved candidate stops surfacing immediately.
    write_candidates_shard(team_root, policy, evaluate(team_root, policy), by)
    print(f"resolved {args.kind} '{args.key}' as {args.decision} -> {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "resolve":
        return run_resolve(argv[1:])
    if argv and argv[0] == "evaluate":
        return run_evaluate(argv[1:])
    try:
        return run_hook()
    except Exception:  # noqa: BLE001 - hooks must not crash the agent
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
