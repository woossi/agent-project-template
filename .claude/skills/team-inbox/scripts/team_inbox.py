#!/usr/bin/env python3
"""Team inbox — a many-to-many message channel for homogeneous peer agents.

Model Y: one shared template root, N agents distinguished only by identity
(``CLAUDE_AGENT_NAME``). Peers coordinate through a shared store on the same
filesystem (default ``.team/``), NOT through subagent return values.

Design constraints (verified against the workspace audit):
- **No shared mutable file.** Each message is one immutable file written to the
  recipient's own directory: ``<store>/inbox/<recipient>/<msgid>.json``. There is
  no single append log or JSON array to corrupt under concurrent writers.
- **Atomic publish.** A message is written to a temp file and ``os.replace``d into
  place (POSIX rename is atomic), so a reader never sees a half-written message.
- **Sortable, unique ids.** ``<ns>__<sender>__<rand>`` sorts chronologically by the
  nanosecond prefix and stays unique across peers via a random suffix.
- **Identity-addressed.** ``post`` fans out one file per recipient; ``--broadcast``
  resolves the recipient set from the team roster (``<store>/team.json``) minus
  the sender. Each recipient consumes only its own directory.
- **Guard-friendly.** Invoked via Bash (the path guard only gates Read/Edit/Write),
  so agents reach the shared store through this CLI without per-path policy edits.

Read ops (``read``) are side-effect free. ``post`` and ``ack`` mutate the store.
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


class InboxError(RuntimeError):
    """Raised on bad identity, missing roster, or unknown recipient."""


def _find_anchored_store(name: str) -> Path:
    """Resolve a relative store name against the team root, not the cwd.

    Peers run this CLI from anywhere under the repo (agent folders, skill dirs).
    A bare ``.team`` resolved against the cwd lands in the wrong place and
    messages are silently lost. So for a relative store name we walk up from the
    cwd looking for a directory that already contains ``<name>/team.json`` (the
    canonical shared store), and anchor there. If none is found we fall back to
    the cwd-relative path (original behaviour), which keeps fresh/empty trees and
    tests working.
    """
    cwd = Path.cwd()
    for base in (cwd, *cwd.parents):
        candidate = base / name
        if (candidate / "team.json").is_file():
            return candidate
    return cwd / name


def resolve_store(explicit: str | None) -> Path:
    raw = explicit or os.environ.get("CLAUDE_TEAM_STORE") or ".team"
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return _find_anchored_store(raw)


def resolve_identity(explicit: str | None) -> str:
    name = explicit or os.environ.get("CLAUDE_AGENT_NAME")
    if not name:
        raise InboxError(
            "no agent identity: pass --from/--as or export CLAUDE_AGENT_NAME"
        )
    return name


def _safe(name: str) -> str:
    """Filesystem-safe segment for an agent name (defensive; names are short)."""
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)


def new_msgid(sender: str, *, clock=time.time_ns, rand=lambda: uuid.uuid4().hex[:8]) -> str:
    return f"{clock():020d}__{_safe(sender)}__{rand()}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # atomic publish


def load_roster(store: Path) -> list[str]:
    team_file = store / "team.json"
    if not team_file.exists():
        raise InboxError(f"team roster not found: {team_file} (needed for --broadcast)")
    data = json.loads(team_file.read_text(encoding="utf-8"))
    members = data.get("members")
    if not isinstance(members, list):
        raise InboxError(f"team roster has no 'members' list: {team_file}")
    return [m for m in members if isinstance(m, str)]


def load_subteams(store: Path) -> dict[str, list[str]]:
    """{team_name: [members]} from team.json (empty if no subteams field)."""
    team_file = store / "team.json"
    if not team_file.exists():
        return {}
    try:
        data = json.loads(team_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, list[str]] = {}
    for st in data.get("subteams") or []:
        if isinstance(st, dict) and isinstance(st.get("name"), str):
            out[st["name"]] = [m for m in (st.get("members") or []) if isinstance(m, str)]
    return out


def team_of(store: Path, agent: str) -> str | None:
    """The subteam an agent belongs to (each worker is in exactly one), or None."""
    for name, members in load_subteams(store).items():
        if agent in members:
            return name
    return None


def is_team(store: Path, name: str) -> bool:
    """True if name is a subteam name (vs a worker/individual recipient)."""
    return name in load_subteams(store)


def resolve_recipients(store: Path, sender: str, to: list[str], broadcast: bool) -> list[str]:
    if broadcast:
        recipients = [m for m in load_roster(store) if m != sender]
        if not recipients:
            raise InboxError("broadcast resolved to zero recipients (roster empty or self-only)")
        return recipients
    if not to:
        raise InboxError("no recipient: pass --to <agent> (repeatable) or --broadcast")
    return list(dict.fromkeys(to))  # dedupe, preserve order


def _quality_fields(quality_gate, verdict, work_ref) -> dict[str, Any]:
    """The optional quality-loop fields (가). All None by default so existing messages and
    callers are byte-identical to before; promoter edge resolution ignores these (structured,
    not endpoints), so signal accounting is unaffected.
      quality_gate : {"axes":[...], "kind":"manuscript|stats"}  — attached on ASSIGNMENT
      verdict      : {"result":"PASS|PARTIAL|FAIL", ...}        — attached on REVIEW reply
      work_ref     : msgid of the assignment a verdict refers to (traceability)
    """
    return {"quality_gate": quality_gate, "verdict": verdict, "work_ref": work_ref}


def post(
    store: Path,
    sender: str,
    to: list[str],
    *,
    subject: str,
    body: str,
    broadcast: bool = False,
    reply_to: str | None = None,
    to_team: str | None = None,
    quality_gate: dict[str, Any] | None = None,
    verdict: dict[str, Any] | None = None,
    work_ref: str | None = None,
    msgid_factory=new_msgid,
) -> dict[str, Any]:
    msgid = msgid_factory(sender)
    ts = int(msgid.split("__", 1)[0])
    sender_team = team_of(store, sender)
    qf = _quality_fields(quality_gate, verdict, work_ref)

    # 팀 메일박스: 팀당 1부(fan-out 아님). 팀의 누구든 claim해서 처리.
    if to_team is not None:
        members = load_subteams(store).get(to_team)
        if members is None:
            raise InboxError(f"unknown team '{to_team}' (not a subteam in team.json)")
        message = {
            "id": msgid, "from": sender, "sender_team": sender_team,
            "to": to_team, "to_team": to_team, "recipients": members,
            "claimed_by": None,
            "subject": subject, "body": body, "reply_to": reply_to, "ts_ns": ts,
            **qf,
        }
        target = store / "inbox" / _safe(to_team) / f"{msgid}.json"
        _atomic_write_json(target, message)
        return {"id": msgid, "from": sender, "delivered_to_team": to_team,
                "members": members, "subject": subject}

    # 개인(워커) 주소: 기존 fan-out 유지. 스키마는 팀 메시지와 통일(to_team=None, claimed_by=None).
    recipients = resolve_recipients(store, sender, to, broadcast)
    delivered = []
    for recipient in recipients:
        message = {
            "id": msgid,
            "from": sender,
            "sender_team": sender_team,
            "to": recipient,
            "to_team": None,
            "recipients": recipients,
            "claimed_by": None,
            "subject": subject,
            "body": body,
            "reply_to": reply_to,
            "ts_ns": ts,
            **qf,
        }
        target = store / "inbox" / _safe(recipient) / f"{msgid}.json"
        _atomic_write_json(target, message)
        delivered.append(recipient)
    return {"id": msgid, "from": sender, "delivered_to": delivered, "subject": subject}


def _inbox_dir(store: Path, agent: str) -> Path:
    return store / "inbox" / _safe(agent)


def read(store: Path, agent: str, *, include_consumed: bool = False) -> list[dict[str, Any]]:
    box = _inbox_dir(store, agent)
    if not box.exists():
        return []
    files = sorted(p for p in box.glob("*.json") if p.is_file())
    out = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    for msg in out:
        msg["_state"] = "unread"
    if include_consumed:
        cbox = box / CONSUMED_DIRNAME
        if cbox.exists():
            for p in sorted(cbox.glob("*.json")):
                msg = json.loads(p.read_text(encoding="utf-8"))
                msg["_state"] = "read"
                out.append(msg)
    return out


def _box(store: Path, name: str) -> Path:
    """Inbox dir for either a worker (individual) or a team (mailbox)."""
    return store / "inbox" / _safe(name)


def claim(store: Path, team: str, msgid: str, claimer: str) -> dict[str, Any]:
    """Atomically claim a team-mailbox message. Competing claimers: only one wins.

    The race point is a single ``os.replace`` of the source file. The winner renames
    it into ``.claimed/<claimer>__<msgid>.json``; losers hit FileNotFoundError because
    the source is already gone. No lock/DB needed — same atomicity as ``ack``.
    """
    box = _box(store, team)
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


def read_team(store: Path, team: str, *, include_claimed: bool = False,
              include_consumed: bool = False) -> list[dict[str, Any]]:
    """Read a team mailbox: unclaimed (root), claimed (.claimed/), consumed (.consumed/)."""
    box = _box(store, team)
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


def ack(store: Path, agent: str, msgid: str, *, team: str | None = None) -> dict[str, Any]:
    """Mark a message consumed (atomic move to .consumed/). Idempotent.

    Individual inbox: source is ``inbox/<agent>/<msgid>.json``.
    Team mailbox (``team`` set): source is the claimed file
    ``inbox/<team>/.claimed/<agent>__<msgid>.json`` (a worker consumes what it claimed).
    """
    if team is not None:
        box = _box(store, team)
        src = box / CLAIMED_DIRNAME / f"{_safe(agent)}__{msgid}.json"
        consumed_dir = box / CONSUMED_DIRNAME
        dst = consumed_dir / f"{msgid}.json"
    else:
        box = _inbox_dir(store, agent)
        src = box / f"{msgid}.json"
        consumed_dir = box / CONSUMED_DIRNAME
        dst = consumed_dir / f"{msgid}.json"
    if not src.exists():
        # Idempotent: already consumed (or never existed) is not an error.
        already = dst.exists()
        return {"id": msgid, "agent": agent, "acked": already,
                "note": "already consumed" if already else "not found"}
    consumed_dir.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)  # atomic move out of the unread/claimed set
    return {"id": msgid, "agent": agent, "acked": True}


# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team_inbox.py", description="Team inbox channel for peer agents.")
    parser.add_argument("--store", default=None, help="Shared store dir (default: $CLAUDE_TEAM_STORE or .team).")
    sub = parser.add_subparsers(dest="op", required=True)

    p_post = sub.add_parser("post", help="Send a message to peers, a team mailbox, or broadcast.")
    p_post.add_argument("--from", dest="sender", default=None, help="Sender (default: $CLAUDE_AGENT_NAME).")
    p_post.add_argument("--to", action="append", default=[], help="Recipient agent (repeatable).")
    p_post.add_argument("--to-team", dest="to_team", default=None,
                        help="Deliver one copy to a team mailbox (inbox/<team>/); team members claim it.")
    p_post.add_argument("--broadcast", action="store_true", help="Send to all roster members except sender.")
    p_post.add_argument("--subject", required=True)
    p_post.add_argument("--body", required=True)
    p_post.add_argument("--reply-to", default=None, help="msgid this replies to.")
    p_post.add_argument("--quality-gate", dest="quality_gate", default=None,
                        help='JSON quality contract for an assignment, e.g. {"axes":["A","E"],"kind":"manuscript"}.')
    p_post.add_argument("--verdict", default=None,
                        help='JSON review verdict, e.g. {"result":"FAIL","majors":1,"by":"quality-reviewer"}.')
    p_post.add_argument("--work-ref", dest="work_ref", default=None,
                        help="msgid of the assignment this verdict refers to (traceability).")

    p_read = sub.add_parser("read", help="Read an individual inbox, or a team mailbox with --team.")
    p_read.add_argument("--as", dest="agent", default=None, help="Whose inbox (default: $CLAUDE_AGENT_NAME).")
    p_read.add_argument("--team", default=None, help="Read this team's mailbox instead of an individual inbox.")
    p_read.add_argument("--all", action="store_true", help="Include claimed + consumed messages.")

    p_claim = sub.add_parser("claim", help="Atomically claim a team-mailbox message (only one claimer wins).")
    p_claim.add_argument("--team", default=None, help="Team mailbox (default: claimer's own team).")
    p_claim.add_argument("--as", dest="claimer", default=None, help="Claiming worker (default: $CLAUDE_AGENT_NAME).")
    p_claim.add_argument("--id", required=True, help="msgid to claim.")

    p_ack = sub.add_parser("ack", help="Mark a message consumed (idempotent). --team for a claimed team message.")
    p_ack.add_argument("--as", dest="agent", default=None)
    p_ack.add_argument("--team", default=None, help="Consume a message claimed from this team mailbox.")
    p_ack.add_argument("--id", required=True, help="msgid to acknowledge.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = resolve_store(args.store)
    try:
        if args.op == "post":
            if args.to_team and (args.to or args.broadcast):
                raise InboxError("--to-team is mutually exclusive with --to/--broadcast")

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

            result = post(
                store,
                resolve_identity(args.sender),
                args.to,
                subject=args.subject,
                body=args.body,
                broadcast=args.broadcast,
                reply_to=args.reply_to,
                to_team=args.to_team,
                quality_gate=_parse_json_arg(args.quality_gate, "quality-gate"),
                verdict=_parse_json_arg(args.verdict, "verdict"),
                work_ref=args.work_ref,
            )
        elif args.op == "read":
            if args.team:
                result = read_team(store, args.team,
                                   include_claimed=args.all, include_consumed=args.all)
            else:
                result = read(store, resolve_identity(args.agent), include_consumed=args.all)
        elif args.op == "claim":
            claimer = resolve_identity(args.claimer)
            team = args.team or team_of(store, claimer)
            if not team:
                raise InboxError(f"no team for '{claimer}': pass --team or fix roster subteams")
            result = claim(store, team, args.id, claimer)
        elif args.op == "ack":
            result = ack(store, resolve_identity(args.agent), args.id, team=args.team)
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
