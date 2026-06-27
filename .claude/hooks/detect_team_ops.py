#!/usr/bin/env python3
"""Surface a team lead's pending *mechanical* ops at session start.

This hook closes the gap between the lead's L1 judgment (who to assign, pass/fail,
spawn a worker — never automated) and the L0 mechanical loop steps that are easy to
*forget* but trivial to *detect*:

- **unclaimed mailbox messages** waiting to be triaged,
- **claimed-but-not-acked** messages (the loop's closing step left undone — the
  observed failure mode where data/review/analysis stacked up claimed mail),
- **quality-ledger signals** (>=2 consecutive non-PASS for a (worker,kind) key) the
  lead has not yet acted on.

It is **read-only**: it never claims, acks, posts, or writes any mailbox/board state.
It only *surfaces* counts so the lead acts. It speaks only to a team lead (its own team)
or the company orchestrator (all teams); for a plain worker — who cannot even read a
mailbox — it stays silent.

Wired as a SessionStart hook (startup|resume|clear), mirroring detect_promotions.py.
Optional ``--annotate`` writes the same summary to the team's reminders list note
channel (an external side effect, so it is OFF by default and only runs on demand,
never inside the SessionStart path).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hooklib import find_repo_root as _find_repo_root  # noqa: E402

CONSUMED_DIRNAME = ".consumed"
CLAIMED_DIRNAME = ".claimed"
ORCHESTRATOR_TEAM = "orchestrator"  # virtual team mailbox at teams/.orchestrator/inbox
QUALITY_THRESHOLD = 2


def _team_json(root: Path) -> dict[str, Any]:
    f = root / ".project" / "team.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _subteams(root: Path) -> list[dict[str, Any]]:
    return [st for st in (_team_json(root).get("subteams") or []) if isinstance(st, dict)]


def _company_owner(root: Path) -> str | None:
    """Company orchestrator name from team-promotion.json governance (may read all teams)."""
    f = root / ".project" / "policies" / "team-promotion.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    gov = data.get("governance") if isinstance(data, dict) else None
    if not isinstance(gov, dict):
        return None
    owner = gov.get("company_owner") or gov.get("authoring_owner")
    return owner if isinstance(owner, str) else None


def _teams_for(root: Path, identity: str) -> list[str]:
    """Which team mailboxes ``identity`` is allowed to triage.

    - A subteam lead (orchestrator key) -> that one team.
    - The company owner -> every subteam plus the virtual ``orchestrator`` mailbox.
    - Anyone else (a plain worker) -> none (workers do not read mailboxes).
    """
    owner = _company_owner(root)
    if identity and identity == owner:
        return [st["name"] for st in _subteams(root) if isinstance(st.get("name"), str)] + [
            ORCHESTRATOR_TEAM
        ]
    for st in _subteams(root):
        if st.get("orchestrator") == identity and isinstance(st.get("name"), str):
            return [st["name"]]
    return []


def _inbox_dir(root: Path, team: str) -> Path:
    if team == ORCHESTRATOR_TEAM:
        return root / "teams" / ".orchestrator" / "inbox"
    return root / "teams" / team / ".claude" / "inbox"


def _count_json(d: Path) -> int:
    """Count *.json files directly in d (not recursive), ignoring dotfiles/tmp."""
    if not d.is_dir():
        return 0
    return sum(
        1
        for p in d.iterdir()
        if p.is_file() and p.suffix == ".json" and not p.name.startswith(".tmp-")
    )


def inspect_mailbox(root: Path, team: str) -> dict[str, int]:
    """Read-only mailbox census: unclaimed (root), claimed (.claimed/, awaiting ack)."""
    box = _inbox_dir(root, team)
    return {
        "unclaimed": _count_json(box),
        "claimed_pending_ack": _count_json(box / CLAIMED_DIRNAME),
    }


def _quality_ledger_path(root: Path, team: str, lead: str) -> Path:
    """The lead's private append-only quality ledger (2-tier or flat worker folder)."""
    teams_dir = root / "teams"
    base = teams_dir / team / lead
    if not base.is_dir():
        base = root / "agents" / lead  # flat fallback
    return base / ".context" / "quality-ledger.jsonl"


def _consecutive_non_pass(records: list[dict[str, Any]]) -> int:
    """Trailing run of non-PASS verdicts (PARTIAL and FAIL both count as failures)."""
    run = 0
    for rec in reversed(records):
        result = str(rec.get("result", "")).lower()
        if result == "pass":
            break
        run += 1
    return run


def inspect_quality(root: Path, team: str, lead: str) -> list[dict[str, Any]]:
    """Per-(worker,kind) keys at >= threshold trailing non-PASS, not yet spawned."""
    path = _quality_ledger_path(root, team, lead)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    spawned: set[tuple[str, str]] = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        key = (str(rec.get("worker", "")), str(rec.get("kind", "")))
        if rec.get("event") == "spawned" or rec.get("op") == "mark-spawned":
            spawned.add(key)
            continue
        by_key.setdefault(key, []).append(rec)
    signals = []
    for (worker, kind), recs in by_key.items():
        if (worker, kind) in spawned:
            continue
        run = _consecutive_non_pass(recs)
        if run >= QUALITY_THRESHOLD:
            signals.append({"worker": worker, "kind": kind, "consecutive_failures": run})
    return signals


def gather(root: Path, identity: str) -> dict[str, Any]:
    teams = _teams_for(root, identity)
    report: dict[str, Any] = {"identity": identity, "teams": {}}
    for team in teams:
        mb = inspect_mailbox(root, team)
        entry: dict[str, Any] = dict(mb)
        # quality signals only for real subteams (the orchestrator mailbox has no ledger)
        if team != ORCHESTRATOR_TEAM:
            lead = identity if team != ORCHESTRATOR_TEAM else None
            # find the team's lead for the ledger path (owner may inspect others' teams)
            for st in _subteams(root):
                if st.get("name") == team and isinstance(st.get("orchestrator"), str):
                    lead = st["orchestrator"]
                    break
            if lead:
                sig = inspect_quality(root, team, lead)
                if sig:
                    entry["quality_signals"] = sig
        report["teams"][team] = entry
    return report


def _has_pending(report: dict[str, Any]) -> bool:
    for entry in report["teams"].values():
        if entry.get("unclaimed") or entry.get("claimed_pending_ack") or entry.get("quality_signals"):
            return True
    return False


def format_surface(report: dict[str, Any]) -> str:
    lines = ["[team-ops] 미처리 운영 단계 — 판단은 팀장이, 아래는 기계적 감지입니다:"]
    for team, e in sorted(report["teams"].items()):
        parts = []
        if e.get("unclaimed"):
            parts.append(f"미처리(claim 대기) {e['unclaimed']}건")
        if e.get("claimed_pending_ack"):
            parts.append(f"claim 후 ack 미완료 {e['claimed_pending_ack']}건")
        if e.get("quality_signals"):
            keys = ", ".join(f"{s['worker']}/{s['kind']}({s['consecutive_failures']}연속)" for s in e["quality_signals"])
            parts.append(f"품질 2연속 실패 → 조치 검토: {keys}")
        if parts:
            lines.append(f"  · {team}: " + " / ".join(parts))
    lines.append("  처리: team-inbox read/claim/ack · 품질신호는 rebalance 또는 create-team-agent 검토(무한생성 금지).")
    return "\n".join(lines)


def run_hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    identity = os.environ.get("CLAUDE_AGENT_NAME") or ""
    if not identity:
        return 0  # no identity -> stay silent (single-agent / unconfigured)
    explicit = os.environ.get("CLAUDE_PROJECT_DIR")
    start = Path(str(payload.get("cwd") or os.getcwd())).expanduser().resolve()
    root = Path(explicit).expanduser().resolve() if explicit else _find_repo_root(start)
    report = gather(root, identity)
    if not report["teams"]:
        return 0  # not a lead/owner -> silent (workers never see mailboxes)
    if not _has_pending(report):
        return 0  # nothing pending -> no noise
    print(format_surface(report))
    return 0


def run_annotate(argv: list[str]) -> int:
    """On-demand: mirror the pending-ops summary to each team's reminders note channel.

    External side effect (osascript), so it is never in the SessionStart path. Best-effort:
    a missing bridge or reminders failure is reported but never raises.
    """
    parser = argparse.ArgumentParser(prog="detect_team_ops.py annotate")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--identity", default=None)
    args = parser.parse_args(argv)
    root = (
        Path(args.project_root).expanduser().resolve()
        if args.project_root
        else _find_repo_root(Path.cwd())
    )
    identity = args.identity or os.environ.get("CLAUDE_AGENT_NAME") or ""
    report = gather(root, identity)
    if not _has_pending(report):
        print("no pending ops to annotate")
        return 0
    bridge = root / ".claude/skills/reminders-team-bridge/scripts/reminders_bridge.py"
    if not bridge.is_file():
        print(f"reminders bridge not found at {bridge}", file=sys.stderr)
        return 0
    import subprocess  # local import: only needed on this explicit path

    subteam_lists = {st.get("name"): st.get("reminders_list") for st in _subteams(root)}
    wrote = 0
    for team, e in report["teams"].items():
        if not (e.get("unclaimed") or e.get("claimed_pending_ack") or e.get("quality_signals")):
            continue
        rlist = subteam_lists.get(team) or "umc"
        note = f"[team-ops] {team}: 미처리 {e.get('unclaimed', 0)} / ack대기 {e.get('claimed_pending_ack', 0)}"
        try:
            subprocess.run(
                [sys.executable, str(bridge), "annotate", str(rlist), note],
                check=False, capture_output=True, timeout=30,
            )
            wrote += 1
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"annotate {team} failed: {exc}", file=sys.stderr)
    print(f"annotated {wrote} team(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "annotate":
        return run_annotate(argv[1:])
    try:
        return run_hook()
    except Exception:  # noqa: BLE001 — a detector must never break session start
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
