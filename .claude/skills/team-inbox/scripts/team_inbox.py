#!/usr/bin/env python3
"""Team inbox — a TEAM-only message channel for homogeneous peer agents (Model Y).

Single channel (2026-06-27 재설계, 사용자 결정 "개인 인박스 폐지, 개인→개인 메시지 제거"):
every message is addressed to a TEAM mailbox. There is no individual/worker address,
no broadcast. A team's members compete to ``claim`` a message; exactly one wins and
then ``ack``s it. Cross-team handoff = post to the other team's mailbox (scout→data).

Layout — the team mailbox lives in the TEAM folder (same tier as the team's memory/
skills/tasks), NOT in a central store:

    teams/<team>/.claude/inbox/<msgid>.json              (unclaimed)
    teams/<team>/.claude/inbox/.claimed/<worker>__<msgid>.json   (claimed, os.replace)
    teams/<team>/.claude/inbox/.consumed/<msgid>.json    (acked)

The company orchestrator is not a team; it has a dedicated mailbox treated as a virtual
team named ``orchestrator`` at ``teams/.orchestrator/inbox/`` so the same code path serves
"team lead → orchestrator" replies. (post --to-team orchestrator / read --team orchestrator)

Design constraints (verified against the workspace audit):
- **No shared mutable file.** Each message is one immutable file; no append log/array.
- **Atomic publish & claim.** temp + ``os.replace`` (POSIX rename is atomic).
- **Sortable, unique ids.** ``<ns>__<sender>__<rand>`` sorts chronologically, unique.
- **Isolation via guard.** The path guard lets a worker WRITE another team's inbox
  (drop-off) but blocks READ (``deny_read``); reads of one's own team pass. This CLI is
  invoked via Bash, so drop-off works through it.

``read`` is side-effect free. ``post``/``claim``/``ack`` mutate the store.
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

CONSUMED_DIRNAME = ".consumed"
CLAIMED_DIRNAME = ".claimed"
ORCHESTRATOR = "orchestrator"  # virtual team mailbox for the company orchestrator


class InboxError(RuntimeError):
    """Raised on bad identity, missing roster, or unknown team."""


def find_team_root(start: Path | None = None) -> Path:
    """Walk up to the repo root, anchored ONLY on ``.project/team.json``.

    Workers run this CLI from anywhere under the repo (their folder, a skill dir). The
    team mailbox is resolved relative to this root, never to the cwd, so a message is
    never silently written to the wrong place.

    NB: we do NOT anchor on AGENTS.md — every worker folder holds an AGENTS.md *symlink*,
    so anchoring on it would stop at the worker folder and yield a wrong nested mailbox
    path (teams/<team>/<worker>/teams/<team>/...). The real shared store has the only
    ``.project/team.json``, so that is the sole reliable anchor.
    """
    cur = (start or Path.cwd()).resolve()
    for d in (cur, *cur.parents):
        if (d / ".project" / "team.json").is_file():
            return d
    return cur


def resolve_root(explicit: str | None) -> Path:
    """Team root. ``explicit`` (or $CLAUDE_TEAM_ROOT) overrides the anchored search —
    used by tests to point at a temp tree."""
    raw = explicit or os.environ.get("CLAUDE_TEAM_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    return find_team_root()


def resolve_identity(explicit: str | None) -> str:
    name = explicit or os.environ.get("CLAUDE_AGENT_NAME")
    if not name:
        raise InboxError("no agent identity: pass --from/--as or export CLAUDE_AGENT_NAME")
    return name


def _safe(name: str) -> str:
    """Filesystem-safe segment for a name (defensive; names are short)."""
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)


def new_msgid(sender: str, *, clock=time.time_ns, rand=lambda: uuid.uuid4().hex[:8]) -> str:
    return f"{clock():020d}__{_safe(sender)}__{rand()}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # atomic publish


def _team_json(root: Path) -> dict[str, Any]:
    f = root / ".project" / "team.json"
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_subteams(root: Path) -> dict[str, list[str]]:
    """{team_name: [members]} from team.json (empty if no subteams field)."""
    out: dict[str, list[str]] = {}
    for st in _team_json(root).get("subteams") or []:
        if isinstance(st, dict) and isinstance(st.get("name"), str):
            out[st["name"]] = [m for m in (st.get("members") or []) if isinstance(m, str)]
    return out


def team_of(root: Path, agent: str) -> str | None:
    """The subteam an agent belongs to (each worker is in exactly one), or None."""
    for name, members in load_subteams(root).items():
        if agent in members:
            return name
    return None


def is_team(root: Path, name: str) -> bool:
    """True if name is a known team mailbox (a subteam, or the orchestrator mailbox)."""
    return name == ORCHESTRATOR or name in load_subteams(root)


def mailbox_dir(root: Path, team: str) -> Path:
    """The team mailbox directory. A real subteam lives in its team folder; the
    orchestrator's virtual mailbox lives at teams/.orchestrator/inbox/."""
    if team == ORCHESTRATOR:
        return root / "teams" / ".orchestrator" / "inbox"
    return root / "teams" / _safe(team) / ".claude" / "inbox"


# ---------------- post ----------------

def _quality_fields(quality_gate, verdict, work_ref) -> dict[str, Any]:
    """Optional quality-loop fields (가). All None by default; promoter edge resolution
    ignores these (structured, not endpoints), so signal accounting is unaffected."""
    return {"quality_gate": quality_gate, "verdict": verdict, "work_ref": work_ref}


def post(
    root: Path,
    sender: str,
    *,
    to_team: str,
    subject: str,
    body: str,
    reply_to: str | None = None,
    quality_gate: dict[str, Any] | None = None,
    verdict: dict[str, Any] | None = None,
    work_ref: str | None = None,
    msgid_factory=new_msgid,
) -> dict[str, Any]:
    """Deliver ONE copy to a team mailbox. The team's members claim it. (No fan-out,
    no individual address.)"""
    if not is_team(root, to_team):
        raise InboxError(f"unknown team '{to_team}' (not a subteam in team.json)")
    msgid = msgid_factory(sender)
    ts = int(msgid.split("__", 1)[0])
    members = load_subteams(root).get(to_team, []) if to_team != ORCHESTRATOR else []
    message = {
        "id": msgid, "from": sender, "sender_team": team_of(root, sender),
        "to_team": to_team, "recipients": members, "claimed_by": None,
        "subject": subject, "body": body, "reply_to": reply_to, "ts_ns": ts,
        **_quality_fields(quality_gate, verdict, work_ref),
    }
    _atomic_write_json(mailbox_dir(root, to_team) / f"{msgid}.json", message)
    return {"id": msgid, "from": sender, "delivered_to_team": to_team,
            "members": members, "subject": subject}


# ---------------- claim ----------------

def claim(root: Path, team: str, msgid: str, claimer: str) -> dict[str, Any]:
    """Atomically claim a team-mailbox message. Competing claimers: only one wins.

    The race point is a single ``os.replace``. The winner renames the message into
    ``.claimed/<claimer>__<msgid>.json``; losers hit FileNotFoundError (source gone).
    """
    box = mailbox_dir(root, team)
    src = box / f"{msgid}.json"
    cdir = box / CLAIMED_DIRNAME
    cdir.mkdir(parents=True, exist_ok=True)
    dst = cdir / f"{_safe(claimer)}__{msgid}.json"

    def _existing_claimer() -> str | None:
        owned = sorted(cdir.glob(f"*__{msgid}.json"))
        return owned[0].name.split("__", 1)[0] if owned else None

    if not src.exists():  # already claimed or never existed — idempotent info
        return {"id": msgid, "claimed": False, "claimed_by": _existing_claimer(),
                "note": "already claimed or not found"}
    try:
        os.replace(src, dst)  # atomic; loser gets FileNotFoundError
    except FileNotFoundError:
        return {"id": msgid, "claimed": False, "claimed_by": _existing_claimer(),
                "note": "lost race"}
    try:
        msg = json.loads(dst.read_text(encoding="utf-8"))
        msg["claimed_by"] = claimer
        _atomic_write_json(dst, msg)  # record claimer inside the file (winner only)
    except (OSError, json.JSONDecodeError):
        pass
    return {"id": msgid, "claimed": True, "claimed_by": claimer}


# ---------------- read ----------------

def read_team(root: Path, team: str, *, include_claimed: bool = False,
              include_consumed: bool = False) -> list[dict[str, Any]]:
    """Read a team mailbox: unclaimed (root), claimed (.claimed/), consumed (.consumed/)."""
    box = mailbox_dir(root, team)
    out: list[dict[str, Any]] = []
    if not box.exists():
        return out
    for p in sorted(box.glob("*.json")):
        if p.is_file():
            msg = json.loads(p.read_text(encoding="utf-8"))
            msg["_state"] = "unclaimed"
            out.append(msg)
    if include_claimed:
        cdir = box / CLAIMED_DIRNAME
        if cdir.exists():
            for p in sorted(cdir.glob("*.json")):
                msg = json.loads(p.read_text(encoding="utf-8"))
                msg["_state"] = "claimed"
                out.append(msg)
    if include_consumed:
        cdir = box / CONSUMED_DIRNAME
        if cdir.exists():
            for p in sorted(cdir.glob("*.json")):
                msg = json.loads(p.read_text(encoding="utf-8"))
                msg["_state"] = "consumed"
                out.append(msg)
    return out


# ---------------- ack ----------------

def ack(root: Path, team: str, msgid: str, *, agent: str) -> dict[str, Any]:
    """Mark a claimed team message consumed (atomic move to .consumed/). Idempotent.

    Source is the claimed file ``inbox/.claimed/<agent>__<msgid>.json`` — a worker
    consumes what it claimed.
    """
    box = mailbox_dir(root, team)
    src = box / CLAIMED_DIRNAME / f"{_safe(agent)}__{msgid}.json"
    consumed_dir = box / CONSUMED_DIRNAME
    dst = consumed_dir / f"{msgid}.json"
    if not src.exists():
        already = dst.exists()
        return {"id": msgid, "agent": agent, "acked": already,
                "note": "already consumed" if already else "not found"}
    consumed_dir.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)  # atomic move out of the claimed set
    return {"id": msgid, "agent": agent, "acked": True}


# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team_inbox.py",
                                     description="Team-only inbox channel for peer agents.")
    parser.add_argument("--root", default=None,
                        help="Team root (default: anchored on .project/team.json, or $CLAUDE_TEAM_ROOT).")
    sub = parser.add_subparsers(dest="op", required=True)

    p_post = sub.add_parser("post", help="Deliver one message to a team mailbox.")
    p_post.add_argument("--from", dest="sender", default=None, help="Sender (default: $CLAUDE_AGENT_NAME).")
    p_post.add_argument("--to-team", dest="to_team", required=True,
                        help="Team mailbox to deliver to (a subteam, or 'orchestrator').")
    p_post.add_argument("--subject", required=True)
    p_post.add_argument("--body", required=True)
    p_post.add_argument("--reply-to", default=None, help="msgid this replies to.")
    p_post.add_argument("--quality-gate", dest="quality_gate", default=None,
                        help='JSON quality contract, e.g. {"axes":["A","E"],"kind":"manuscript"}.')
    p_post.add_argument("--verdict", default=None,
                        help='JSON review verdict, e.g. {"result":"FAIL","majors":1,"by":"quality-reviewer"}.')
    p_post.add_argument("--work-ref", dest="work_ref", default=None,
                        help="msgid of the assignment this verdict refers to (traceability).")

    p_read = sub.add_parser("read", help="Read a team mailbox.")
    p_read.add_argument("--team", default=None, help="Team mailbox (default: reader's own team).")
    p_read.add_argument("--as", dest="agent", default=None,
                        help="Reader identity, used to default --team (default: $CLAUDE_AGENT_NAME).")
    p_read.add_argument("--all", action="store_true", help="Include claimed + consumed messages.")

    p_claim = sub.add_parser("claim", help="Atomically claim a team-mailbox message (only one claimer wins).")
    p_claim.add_argument("--team", default=None, help="Team mailbox (default: claimer's own team).")
    p_claim.add_argument("--as", dest="claimer", default=None, help="Claiming worker (default: $CLAUDE_AGENT_NAME).")
    p_claim.add_argument("--id", required=True, help="msgid to claim.")

    p_ack = sub.add_parser("ack", help="Mark a claimed team message consumed (idempotent).")
    p_ack.add_argument("--team", default=None, help="Team mailbox (default: acker's own team).")
    p_ack.add_argument("--as", dest="agent", default=None, help="Acking worker (default: $CLAUDE_AGENT_NAME).")
    p_ack.add_argument("--id", required=True, help="msgid to acknowledge.")

    return parser


def _parse_json_arg(raw, label):
    if raw is None:
        return None
    try:
        val = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InboxError(f"--{label} must be valid JSON: {exc}")
    if not isinstance(val, dict):
        raise InboxError(f"--{label} must be a JSON object")
    return val


def _default_team(root: Path, explicit: str | None, identity: str | None) -> str:
    """Team for read/claim/ack: explicit --team, else the identity's own team."""
    if explicit:
        return explicit
    who = identity or os.environ.get("CLAUDE_AGENT_NAME")
    t = team_of(root, who) if who else None
    if not t:
        raise InboxError(f"no team for '{who}': pass --team or fix roster subteams")
    return t


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_root(args.root)
    try:
        if args.op == "post":
            result = post(
                root, resolve_identity(args.sender), to_team=args.to_team,
                subject=args.subject, body=args.body, reply_to=args.reply_to,
                quality_gate=_parse_json_arg(args.quality_gate, "quality-gate"),
                verdict=_parse_json_arg(args.verdict, "verdict"),
                work_ref=args.work_ref,
            )
        elif args.op == "read":
            team = _default_team(root, args.team, args.agent)
            result = read_team(root, team, include_claimed=args.all, include_consumed=args.all)
        elif args.op == "claim":
            claimer = resolve_identity(args.claimer)
            team = _default_team(root, args.team, claimer)
            result = claim(root, team, args.id, claimer)
        elif args.op == "ack":
            agent = resolve_identity(args.agent)
            team = _default_team(root, args.team, agent)
            result = ack(root, team, args.id, agent=agent)
        else:  # pragma: no cover - argparse guards
            raise InboxError(f"unhandled op: {args.op}")
    except InboxError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    json.dump({"ok": True, "op": args.op, "result": result}, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
