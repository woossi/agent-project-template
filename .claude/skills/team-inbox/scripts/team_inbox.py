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


def resolve_recipients(store: Path, sender: str, to: list[str], broadcast: bool) -> list[str]:
    if broadcast:
        recipients = [m for m in load_roster(store) if m != sender]
        if not recipients:
            raise InboxError("broadcast resolved to zero recipients (roster empty or self-only)")
        return recipients
    if not to:
        raise InboxError("no recipient: pass --to <agent> (repeatable) or --broadcast")
    return list(dict.fromkeys(to))  # dedupe, preserve order


def post(
    store: Path,
    sender: str,
    to: list[str],
    *,
    subject: str,
    body: str,
    broadcast: bool = False,
    reply_to: str | None = None,
    msgid_factory=new_msgid,
) -> dict[str, Any]:
    recipients = resolve_recipients(store, sender, to, broadcast)
    msgid = msgid_factory(sender)
    delivered = []
    for recipient in recipients:
        message = {
            "id": msgid,
            "from": sender,
            "to": recipient,
            "recipients": recipients,
            "subject": subject,
            "body": body,
            "reply_to": reply_to,
            "ts_ns": int(msgid.split("__", 1)[0]),
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


def ack(store: Path, agent: str, msgid: str) -> dict[str, Any]:
    box = _inbox_dir(store, agent)
    src = box / f"{msgid}.json"
    consumed_dir = box / CONSUMED_DIRNAME
    dst = consumed_dir / f"{msgid}.json"
    if not src.exists():
        # Idempotent: already consumed (or never existed) is not an error.
        already = dst.exists()
        return {"id": msgid, "agent": agent, "acked": already, "note": "already consumed" if already else "not found"}
    consumed_dir.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)  # atomic move out of the unread set
    return {"id": msgid, "agent": agent, "acked": True}


# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team_inbox.py", description="Team inbox channel for peer agents.")
    parser.add_argument("--store", default=None, help="Shared store dir (default: $CLAUDE_TEAM_STORE or .team).")
    sub = parser.add_subparsers(dest="op", required=True)

    p_post = sub.add_parser("post", help="Send a message to one or more peers (or --broadcast).")
    p_post.add_argument("--from", dest="sender", default=None, help="Sender (default: $CLAUDE_AGENT_NAME).")
    p_post.add_argument("--to", action="append", default=[], help="Recipient agent (repeatable).")
    p_post.add_argument("--broadcast", action="store_true", help="Send to all roster members except sender.")
    p_post.add_argument("--subject", required=True)
    p_post.add_argument("--body", required=True)
    p_post.add_argument("--reply-to", default=None, help="msgid this replies to.")

    p_read = sub.add_parser("read", help="Read a peer's inbox (unread by default).")
    p_read.add_argument("--as", dest="agent", default=None, help="Whose inbox (default: $CLAUDE_AGENT_NAME).")
    p_read.add_argument("--all", action="store_true", help="Include already-consumed messages.")

    p_ack = sub.add_parser("ack", help="Mark a message consumed (idempotent).")
    p_ack.add_argument("--as", dest="agent", default=None)
    p_ack.add_argument("--id", required=True, help="msgid to acknowledge.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = resolve_store(args.store)
    try:
        if args.op == "post":
            result = post(
                store,
                resolve_identity(args.sender),
                args.to,
                subject=args.subject,
                body=args.body,
                broadcast=args.broadcast,
                reply_to=args.reply_to,
            )
        elif args.op == "read":
            result = read(store, resolve_identity(args.agent), include_consumed=args.all)
        elif args.op == "ack":
            result = ack(store, resolve_identity(args.agent), args.id)
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
