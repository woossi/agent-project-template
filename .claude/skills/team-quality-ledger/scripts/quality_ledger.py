#!/usr/bin/env python3
"""Team quality ledger — the (가)+(나) counter that turns review-gate verdicts into a
2-consecutive-FAIL signal a team lead acts on.

The orchestrator (team lead) of a subteam runs this. A verdict produced by the verification
team (quality-reviewer for manuscript, stats-validator for data/analysis — user decision
2026-06-27, "종류별 분담") is RECORDED here keyed by (worker, kind). When the most recent two
verdicts for the SAME key are both non-PASS, ``signal`` fires — telling the lead to consider
spawning a specialized worker (via the TEAM-tier create-team-agent skill distributed in (다)).

Counting rule (user decision Q1, 2026-06-27): **only PASS resets the counter; PARTIAL and
FAIL both count as a failure.** So "2 consecutive failures" = the last two verdicts for a key
are each PARTIAL or FAIL with no PASS between them.

Autonomy is L1 (user decision Q3): this surfaces a SIGNAL; the lead decides whether to spawn.
Nothing here calls create-team-agent — it only reads/writes the ledger and computes signals.

Storage: append-only JSONL at ``teams/<team>/<lead>/.context/quality-ledger.jsonl`` (the lead's
own private folder — isolation-safe; only the lead reads/writes it). Each line:
    {"worker": str, "kind": str, "result": "PASS|PARTIAL|FAIL",
     "work_ref": str|None, "by": str|None, "round": str|None,
     "ts_ns": int, "spawned_for": bool}
The optional ``spawned_for`` marks that a specialized worker was already created for this
(worker, kind) so the lead doesn't spawn twice for the same boundary (anti-thrash, §3.3).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
PARTIAL = "PARTIAL"
RESULTS = (PASS, PARTIAL, FAIL)

# A non-PASS verdict is a "failure" for counting (Q1: PARTIAL and FAIL both count).
def is_failure(result: str) -> bool:
    return result.upper() != PASS


class LedgerError(RuntimeError):
    pass


def default_team_root() -> Path:
    # scripts/ -> team-quality-ledger -> skills -> .claude -> repo root
    return Path(__file__).resolve().parents[4]


def _lead_of(team_root: Path, team: str) -> str | None:
    data = _load_json_or_none(team_root / ".project" / "team.json")
    if isinstance(data, dict):
        for st in data.get("subteams") or []:
            if isinstance(st, dict) and str(st.get("name") or "").strip() == team:
                orch = st.get("orchestrator")
                if isinstance(orch, str) and orch.strip():
                    return orch.strip()
    return None


def _team_of_worker(team_root: Path, worker: str) -> str | None:
    data = _load_json_or_none(team_root / ".project" / "team.json")
    if isinstance(data, dict):
        for st in data.get("subteams") or []:
            if isinstance(st, dict) and worker in (st.get("members") or []):
                name = st.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    return None


def _load_json_or_none(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _worker_dir(team_root: Path, team: str, name: str) -> Path:
    """Where a worker's folder lives (2-tier teams/<team>/<name>)."""
    return team_root / "teams" / team / name


def ledger_path(team_root: Path, team: str) -> Path:
    """The lead's private quality ledger for ``team``."""
    lead = _lead_of(team_root, team)
    if not lead:
        raise LedgerError(f"team '{team}' has no orchestrator in team.json")
    return _worker_dir(team_root, team, lead) / ".context" / "quality-ledger.jsonl"


def _append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _read_all(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def record(
    team_root: Path,
    team: str,
    *,
    worker: str,
    kind: str,
    result: str,
    work_ref: str | None = None,
    by: str | None = None,
    round_: str | None = None,
    clock=time.time_ns,
) -> dict[str, Any]:
    """Append one verdict for (worker, kind). Validates result and that worker is in team."""
    result = result.upper()
    if result not in RESULTS:
        raise LedgerError(f"result must be one of {RESULTS}, got {result!r}")
    if not worker.strip() or not kind.strip():
        raise LedgerError("worker and kind are required")
    rec = {
        "worker": worker.strip(), "kind": kind.strip(), "result": result,
        "work_ref": work_ref, "by": by, "round": round_,
        "ts_ns": clock(), "spawned_for": False,
    }
    _append(ledger_path(team_root, team), rec)
    return rec


def _by_key(records: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    keyed: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in records:
        key = (str(r.get("worker") or ""), str(r.get("kind") or ""))
        keyed.setdefault(key, []).append(r)
    for recs in keyed.values():
        recs.sort(key=lambda r: int(r.get("ts_ns") or 0))
    return keyed


def consecutive_failures(records: list[dict[str, Any]]) -> int:
    """Trailing run of non-PASS results (PASS resets). Operates on one key's ordered list."""
    n = 0
    for r in reversed(records):
        if is_failure(str(r.get("result") or "")):
            n += 1
        else:
            break
    return n


def already_spawned(records: list[dict[str, Any]]) -> bool:
    return any(bool(r.get("spawned_for")) for r in records)


def signal(team_root: Path, team: str, *, threshold: int = 2) -> list[dict[str, Any]]:
    """(나) trigger: keys whose trailing failure run >= threshold. L1 — a signal, not an act.

    A key that already has a ``spawned_for`` mark is downgraded to a SECOND-ORDER signal
    ("a worker was already spawned for this boundary; the split may be wrong — consider
    rebalance instead of another spawn"), never a fresh spawn trigger (§3.3 anti-thrash).
    """
    keyed = _by_key(_read_all(ledger_path(team_root, team)))
    out: list[dict[str, Any]] = []
    for (worker, kind), recs in sorted(keyed.items()):
        run = consecutive_failures(recs)
        if run < threshold:
            continue
        spawned = already_spawned(recs)
        out.append({
            "team": team, "worker": worker, "kind": kind,
            "consecutive_failures": run, "threshold": threshold,
            "already_spawned": spawned,
            "recommend": "rebalance" if spawned else "spawn_specialized_worker",
            "last_results": [str(r.get("result")) for r in recs[-threshold:]],
        })
    return out


def mark_spawned(team_root: Path, team: str, *, worker: str, kind: str,
                 clock=time.time_ns) -> dict[str, Any]:
    """Record that a specialized worker was created for (worker, kind). Appended as a marker
    record (append-only ledger; we never rewrite past lines) with spawned_for=True."""
    rec = {
        "worker": worker.strip(), "kind": kind.strip(), "result": PASS,
        "work_ref": None, "by": None, "round": None,
        "ts_ns": clock(), "spawned_for": True,
    }
    _append(ledger_path(team_root, team), rec)
    return {"marked": True, "worker": worker, "kind": kind}


# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quality_ledger.py",
                                description="Team quality ledger: record verdicts, signal 2x consecutive failures.")
    p.add_argument("--team-root", default=None, help="Repo root (default: inferred).")
    p.add_argument("--team", default=None, help="Subteam (default: team of $CLAUDE_AGENT_NAME).")
    sub = p.add_subparsers(dest="op", required=True)

    pr = sub.add_parser("record", help="Append one verification verdict for (worker, kind).")
    pr.add_argument("--worker", required=True)
    pr.add_argument("--kind", required=True, help="Work kind (e.g. manuscript-intro, stats-spatial).")
    pr.add_argument("--result", required=True, choices=[r.lower() for r in RESULTS] + list(RESULTS))
    pr.add_argument("--work-ref", dest="work_ref", default=None)
    pr.add_argument("--by", default=None, help="Verifier (quality-reviewer | stats-validator).")
    pr.add_argument("--round", dest="round_", default=None)

    ps = sub.add_parser("signal", help="List (worker, kind) keys at >= N consecutive failures.")
    ps.add_argument("--threshold", type=int, default=2)

    pl = sub.add_parser("list", help="Dump the ledger (raw records).")

    pm = sub.add_parser("mark-spawned", help="Mark that a specialized worker was created for (worker, kind).")
    pm.add_argument("--worker", required=True)
    pm.add_argument("--kind", required=True)

    return p


def _resolve_team(team_root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    me = os.environ.get("CLAUDE_AGENT_NAME")
    if me:
        t = _team_of_worker(team_root, me)
        if t:
            return t
    raise LedgerError("no --team and could not infer from $CLAUDE_AGENT_NAME")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    team_root = Path(args.team_root).expanduser() if args.team_root else default_team_root()
    try:
        team = _resolve_team(team_root, args.team)
        if args.op == "record":
            result = record(team_root, team, worker=args.worker, kind=args.kind,
                            result=args.result, work_ref=args.work_ref, by=args.by, round_=args.round_)
        elif args.op == "signal":
            result = {"signals": signal(team_root, team, threshold=args.threshold)}
        elif args.op == "list":
            result = {"records": _read_all(ledger_path(team_root, team))}
        elif args.op == "mark-spawned":
            result = mark_spawned(team_root, team, worker=args.worker, kind=args.kind)
        else:  # pragma: no cover
            raise LedgerError(f"unhandled op: {args.op}")
    except LedgerError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    json.dump({"ok": True, "op": args.op, "team": team, "result": result},
              sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
