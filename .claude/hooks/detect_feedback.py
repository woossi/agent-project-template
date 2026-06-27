#!/usr/bin/env python3
"""Route and surface inter-agent task feedback as an enforced loop.

Two peer agent projects (this one and its peer) review each other's outputs and
exchange quality feedback. This hook makes that exchange a measured, self-closing
loop instead of a promise, mirroring the Tasks -> Skills -> Agents promotion chain
(`task_ledger.py` + `detect_promotions.py`).

- ``record-feedback`` (write) appends a feedback record to the *peer* project's
  ``inbox.jsonl`` (via an absolute path the workspace guard allows) and keeps a
  copy in this project's ``outbox.jsonl``.
- Hook mode (PostToolUse / SessionStart) folds this project's inbox by id,
  evaluates the open items against ``.claude/policies/feedback.json``, writes them
  to ``candidates.json``, and emits ``additionalContext`` so every turn
  re-surfaces unresolved feedback until it is resolved or declined.
- ``resolve`` records a decision and appends a status line so the item stops
  surfacing.

The surfaced guidance deliberately wires feedback into the existing promotion and
derivation chains: processing work should be recorded with ``task_ledger.py
record-task`` (recurrence -> skill/agent promotion) and recurring feedback should
be recorded with ``detect_derivations.py record-signal --kind preference``.

Like every hook here it is append-only, idempotent, swallows errors, and exits 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hooklib import merge as _merge, project_dir_simple as project_dir  # noqa: E402

DEFAULTS: dict[str, Any] = {
    "agent": {"self": "", "peer": "", "peer_inbox": ""},
    "log": {
        "inbox": ".context/feedback/inbox.jsonl",
        "outbox": ".context/feedback/outbox.jsonl",
        "candidates": ".context/feedback/candidates.json",
        "decisions": ".context/feedback/decisions.json",
    },
    "surface": {
        "max_open": 10,
        "min_severity": "minor",
        "recurrence_signal": {"min_recurrence": 2, "min_distinct_sessions": 1},
    },
    "kinds": ["praise", "issue", "request_change", "question"],
    "severity_order": ["info", "minor", "major", "critical"],
}

OPEN_STATUS = "open"
CLOSED_STATUSES = {"ack", "resolved", "decline"}


def load_policy(root: Path) -> dict[str, Any]:
    policy_path = root / ".claude/policies/feedback.json"
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    return _merge(DEFAULTS, raw)


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


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_decisions(path: Path) -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    out = {"feedback": {}}
    if isinstance(raw, dict):
        value = raw.get("feedback")
        if isinstance(value, dict):
            out["feedback"] = value
    return out


def split_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    for value in values:
        for piece in value.split(","):
            piece = piece.strip()
            if piece and piece not in items:
                items.append(piece)
    return items


def make_id(rec: dict[str, Any]) -> str:
    basis = "\x1f".join(
        str(rec.get(key) or "").strip()
        for key in ("from_agent", "to_agent", "task_ref", "kind", "message")
    )
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
    return f"fb-{digest}"


def fold_inbox(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Collapse an append-only inbox to current state, last write wins by id."""
    folded: dict[str, dict[str, Any]] = {}
    for rec in records:
        rec_id = str(rec.get("id") or "").strip()
        if not rec_id:
            rec_id = make_id(rec)
            rec = {**rec, "id": rec_id}
        if rec_id in folded:
            folded[rec_id] = {**folded[rec_id], **rec}
        else:
            folded[rec_id] = dict(rec)
    return folded


def _severity_rank(order: list[str], severity: str) -> int:
    try:
        return order.index(severity)
    except ValueError:
        return 0


def evaluate(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    log = policy["log"]
    surface = policy["surface"]
    order = policy["severity_order"]
    min_rank = _severity_rank(order, str(surface.get("min_severity", "minor")))

    inbox = fold_inbox(load_jsonl(root / log["inbox"]))
    decisions = load_decisions(root / log["decisions"])["feedback"]

    # Recurrence over the full inbox history feeds the preference-derivation link.
    rec_rule = surface.get("recurrence_signal", {})
    min_rec = int(rec_rule.get("min_recurrence", 2))
    min_sessions = int(rec_rule.get("min_distinct_sessions", 1))
    groups: dict[str, dict[str, Any]] = {}
    for rec in inbox.values():
        key = str(rec.get("task_ref") or "") + "\x1f" + str(rec.get("kind") or "")
        group = groups.setdefault(key, {"count": 0, "sessions": set()})
        group["count"] += 1
        group["sessions"].add(str(rec.get("session") or ""))

    def is_recurring(rec: dict[str, Any]) -> bool:
        key = str(rec.get("task_ref") or "") + "\x1f" + str(rec.get("kind") or "")
        group = groups.get(key, {"count": 0, "sessions": set()})
        return group["count"] >= min_rec and len(group["sessions"]) >= min_sessions

    open_items: list[dict[str, Any]] = []
    for rec in inbox.values():
        if str(rec.get("status") or OPEN_STATUS) != OPEN_STATUS:
            continue
        if str(rec.get("id")) in decisions:
            continue
        if _severity_rank(order, str(rec.get("severity") or "minor")) < min_rank:
            continue
        open_items.append(
            {
                "kind": "feedback",
                "id": str(rec.get("id")),
                "from_agent": str(rec.get("from_agent") or ""),
                "feedback_kind": str(rec.get("kind") or ""),
                "severity": str(rec.get("severity") or ""),
                "task_ref": str(rec.get("task_ref") or ""),
                "message": str(rec.get("message") or ""),
                "related_paths": rec.get("related_paths") or [],
                "recurring": is_recurring(rec),
            }
        )

    open_items.sort(
        key=lambda c: (-_severity_rank(order, c["severity"]), c["task_ref"], c["id"])
    )
    return {"feedback": open_items[: int(surface.get("max_open", 10))]}


def write_candidates(root: Path, policy: dict[str, Any], candidates: dict[str, Any]) -> Path:
    path = root / policy["log"]["candidates"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def format_surface(candidates: dict[str, Any]) -> str:
    items = candidates.get("feedback", [])
    if not items:
        return ""
    lines: list[str] = []
    for cand in items:
        tag = " [recurring]" if cand.get("recurring") else ""
        lines.append(
            f"- [feedback] ({cand['severity']}/{cand['feedback_kind']}) from "
            f"{cand['from_agent']} on '{cand['task_ref']}': {cand['message']}{tag}"
        )
    header = (
        "Inbound feedback is open. Process each item, then run "
        "`.claude/hooks/detect_feedback.py resolve --id <id> --decision resolved` to clear it:\n"
        "- after acting, record the work with `task_ledger.py record-task --signature <task_ref>` "
        "(recurrence promotes it to a skill/agent).\n"
        "- a [recurring] pattern -> `detect_derivations.py record-signal --kind preference "
        "--key <slug>` to derive a preference.\n"
        "- not worth acting on -> resolve with `--decision decline --reason ...`.\n"
    )
    return header + "\n".join(lines)


# Events whose hookSpecificOutput supports additionalContext (Claude Code hooks).
CONTEXT_EVENTS = {"PostToolUse", "PreToolUse", "SessionStart", "UserPromptSubmit", "Stop"}


def emit_hook_context(message: str, event_name: str = "PostToolUse") -> None:
    if not message:
        return
    # hookSpecificOutput.hookEventName must exactly match the firing event.
    if event_name not in CONTEXT_EVENTS:
        event_name = "PostToolUse"
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": message,
        }
    }
    print(json.dumps(payload, ensure_ascii=False))


def run_hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    root = project_dir(payload)
    policy = load_policy(root)
    candidates = evaluate(root, policy)
    write_candidates(root, policy, candidates)
    event_name = str(payload.get("hook_event_name") or "PostToolUse")
    emit_hook_context(format_surface(candidates), event_name)
    return 0


def run_record_feedback(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_feedback.py record-feedback")
    parser.add_argument("--task-ref", required=True, help="Peer task signature or output path")
    parser.add_argument("--kind", required=True, help="Feedback kind (see policy 'kinds')")
    parser.add_argument("--severity", default="minor", help="Severity (see policy 'severity_order')")
    parser.add_argument("--message", required=True, help="Evidence-grounded one-line feedback")
    parser.add_argument("--related-paths", action="append", help="Paths (comma-separated or repeated)")
    parser.add_argument("--session", default="", help="Session id for recurrence counting")
    parser.add_argument("--to", default="", help="Override target agent name")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)

    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    policy = load_policy(root)
    agent = policy["agent"]

    kinds = policy.get("kinds", [])
    if kinds and args.kind not in kinds:
        print(f"error: --kind must be one of {kinds}", file=sys.stderr)
        return 2
    order = policy.get("severity_order", [])
    if order and args.severity not in order:
        print(f"error: --severity must be one of {order}", file=sys.stderr)
        return 2

    peer_inbox = str(agent.get("peer_inbox") or "").strip()
    if not peer_inbox:
        print("error: policy agent.peer_inbox is not set", file=sys.stderr)
        return 2

    record = {
        "from_agent": str(agent.get("self") or "").strip(),
        "to_agent": (args.to.strip() or str(agent.get("peer") or "").strip()),
        "task_ref": args.task_ref.strip(),
        "kind": args.kind,
        "severity": args.severity,
        "message": args.message.strip(),
        "related_paths": split_list(args.related_paths),
        "session": args.session.strip(),
        "status": OPEN_STATUS,
        "ts": int(time.time()),
    }
    record["id"] = make_id(record)

    append_jsonl(Path(peer_inbox).expanduser(), record)
    append_jsonl(root / policy["log"]["outbox"], record)
    print(f"sent feedback '{record['id']}' to {record['to_agent']} -> {peer_inbox}")
    return 0


def run_resolve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_feedback.py resolve")
    parser.add_argument("--id", required=True, help="Feedback id (fb-...)")
    parser.add_argument("--decision", required=True, choices=["ack", "resolved", "decline"])
    parser.add_argument("--reason", default="")
    parser.add_argument("--session", default="", help="Session id for the status line")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)

    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    policy = load_policy(root)
    path = root / policy["log"]["decisions"]
    decisions = load_decisions(path)
    decisions["feedback"][args.id] = {"decision": args.decision, "reason": args.reason.strip()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(decisions, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Append a status line so the inbox fold reflects the closure, keeping it append-only.
    status = "open" if args.decision == "ack" else args.decision
    if args.decision != "ack":
        append_jsonl(
            root / policy["log"]["inbox"],
            {"id": args.id, "status": status, "ts": int(time.time()), "session": args.session.strip()},
        )

    # Refresh candidates so the resolved one stops surfacing immediately.
    write_candidates(root, policy, evaluate(root, policy))
    print(f"resolved feedback '{args.id}' as {args.decision}")
    return 0


def run_evaluate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="detect_feedback.py evaluate")
    parser.add_argument("--project-root", default=None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when any open feedback exists (for CI)",
    )
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve() if args.project_root else project_dir({})
    policy = load_policy(root)
    candidates = evaluate(root, policy)
    path = write_candidates(root, policy, candidates)
    total = len(candidates["feedback"])
    if args.check and total:
        print(f"{total} open feedback item(s) pending", file=sys.stderr)
        return 1
    print(f"{total} open feedback item(s) -> {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "record-feedback":
        return run_record_feedback(argv[1:])
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
