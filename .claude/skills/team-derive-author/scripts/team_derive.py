#!/usr/bin/env python3
"""Author team-derived assets into the shared team store (the AUTHORING side).

``detect_team_derivations.py`` surfaces team_term / team_preference / team_memory
candidates; this CLI is how the governance OWNER acts on them and closes the loop.

Conflict-safety = OWNER SERIALIZATION. The most dangerous shared writer is the
non-atomic ``register_term`` full-file rewrite, so the team dictionary
(``.project/word.json``) and the shared preferences doc are written by exactly ONE
agent — the ``governance.authoring_owner`` from ``.project/policies/team-derivation.json``.
A non-owner is refused and told to propose via the inbox. With a single writer
there is no concurrency, and the write is still done atomically (tmp + os.replace).

Team memory is append-of-immutable: each fact is one file
``.project/memory/<ns>__<agent>__<slug>.json`` (never edited), folded into a derived
``.project/memory.md`` view, so even multiple authors never corrupt a shared file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from team_common.identity import identity_from_cwd  # noqa: E402
from team_common.io import atomic_write_text  # noqa: E402
from team_common.roster import TeamIndex  # noqa: E402

TERM_FIELDS = ("term", "ko", "definition", "use_when")


class DeriveAuthorError(RuntimeError):
    """Raised on a non-owner write, a missing field, a duplicate term, or bad input."""


def resolve_store(explicit: str | None) -> Path:
    return Path(explicit or os.environ.get("CLAUDE_PROJECT_STORE") or ".project").expanduser()


def _repo_root_for_store(store: Path) -> Path | None:
    resolved = store.expanduser().resolve()
    if resolved.name == ".project" and (resolved / "team.json").is_file():
        return resolved.parent
    for base in (resolved, *resolved.parents):
        if (base / ".project" / "team.json").is_file():
            return base
    return None


def _load_subteams(root: Path) -> dict[str, list[str]]:
    return TeamIndex.load(root).subteams


CWD_FAILCLOSED = "__cwd_failclosed__"


def _worker_at(root: Path, candidate: Path) -> str | None:
    return TeamIndex.load(root).worker_at(candidate)


def _identity_from_cwd(root: Path) -> str | None:
    return identity_from_cwd(root, failclosed=CWD_FAILCLOSED)


def resolve_identity(explicit: str | None, root: Path | None = None) -> str:
    if root is not None:
        cwd_id = _identity_from_cwd(root)
        if cwd_id is not None:
            return cwd_id
    return explicit or os.environ.get("CLAUDE_AGENT_NAME") or "user"


def slugify(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "-", text.strip()).strip("-").lower() or "x"


def load_owner(store: Path) -> str:
    policy = store / "policies/team-derivation.json"
    try:
        data = json.loads(policy.read_text(encoding="utf-8"))
        owner = data.get("governance", {}).get("authoring_owner")
        if isinstance(owner, str) and owner:
            return owner
    except (OSError, json.JSONDecodeError):
        pass
    return "orchestrator"


def _require_owner(store: Path, by: str) -> None:
    owner = load_owner(store)
    if by != owner:
        raise DeriveAuthorError(
            f"only the team owner '{owner}' may write the shared store (you are '{by}'); "
            "propose via the inbox instead (team_inbox.py post --to " + owner + ")"
        )


def _atomic_write(path: Path, text: str) -> None:
    atomic_write_text(path, text)


def _load_word(store: Path) -> dict[str, Any]:
    path = store / "word.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("terms"), list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "schema_version": "1.0",
        "description": "Team-shared terminology. Written only by the team owner (owner-serialized).",
        "terms": [],
    }


def register_term(store: Path, *, term: str, ko: str, definition: str, use_when: str, by: str) -> dict[str, Any]:
    _require_owner(store, by)
    fields = {"term": term.strip(), "ko": ko.strip(), "definition": definition.strip(), "use_when": use_when.strip()}
    missing = [name for name in TERM_FIELDS if not fields[name]]
    if missing:
        raise DeriveAuthorError("missing required term fields: " + ", ".join(missing) + " (never invent a definition)")
    data = _load_word(store)
    lowered = {str(e.get("term", "")).strip().lower() for e in data["terms"] if isinstance(e, dict)}
    if fields["term"].lower() in lowered:
        raise DeriveAuthorError(f"term already in team dictionary: {fields['term']}")
    data["terms"].append(fields)
    _atomic_write(store / "word.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return fields


def _is_shared_memory(store: Path) -> bool:
    """기록 대상 메모리가 공유 메모리인지 판정한다.

    공유: .project/memory · teams/<팀>/.claude/memory.
    비공유(통과): teams/<팀>/<워커>/.claude/memory 등 워커 개인 메모리.
    """
    mdir = (store / "memory").resolve()
    parts = mdir.parts
    # .project/memory
    for i, seg in enumerate(parts[:-1]):
        if seg == ".project" and parts[i + 1] == "memory":
            return True
    # teams/<팀>/.claude/memory  (teams/<팀>/<워커>/.claude/memory 는 비공유)
    if "teams" in parts:
        ti = parts.index("teams")
        # 팀 공유: teams / <팀> / .claude / memory  → 'teams' 뒤로 정확히 3 세그먼트
        tail = parts[ti + 1:]
        if len(tail) == 3 and tail[1] == ".claude" and tail[2] == "memory":
            return True
    return False


def record_memory(store: Path, *, key: str, fact: str, source: str = "", by: str = "user", clock=time.time_ns) -> dict[str, Any]:
    # 공유 메모리(.project/memory · teams/<팀>/.claude/memory) 기록은 owner 게이트.
    # 워커 개인 메모리(teams/<팀>/<워커>/.claude/memory)는 통과(계층별 게이트).
    if _is_shared_memory(store):
        _require_owner(store, by)
    key = key.strip()
    fact = fact.strip()
    if not key or not fact:
        raise DeriveAuthorError("team memory needs a non-empty --key and --fact")
    ts = clock()
    record = {"key": key, "fact": fact, "source": source.strip(), "by": by, "ts_ns": ts}
    path = store / "memory" / f"{ts:020d}__{slugify(by)}__{slugify(key)}.json"
    _atomic_write(path, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


def render_memory(store: Path) -> Path:
    """Fold immutable memory records into a human-readable .project/memory.md (idempotent)."""
    mdir = store / "memory"
    records: list[dict[str, Any]] = []
    if mdir.is_dir():
        for p in sorted(mdir.glob("*.json")):
            try:
                records.append(json.loads(p.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    # de-dup by key: last (highest ts) wins
    by_key: dict[str, dict[str, Any]] = {}
    for rec in sorted(records, key=lambda r: r.get("ts_ns", 0)):
        k = str(rec.get("key", "")).strip()
        if k:
            by_key[k] = rec
    lines = ["# Team Memory", "", "Accepted team decisions + facts (derived view of .project/memory/*.json).", ""]
    for k in sorted(by_key):
        rec = by_key[k]
        lines.append(f"## {k}")
        lines.append("")
        lines.append(rec.get("fact", ""))
        meta = f"By: {rec.get('by', '')}" + (f" · Source: {rec['source']}" if rec.get("source") else "")
        lines.append("")
        lines.append(meta)
        lines.append("")
    path = store / "memory.md"
    _atomic_write(path, "\n".join(lines).rstrip() + "\n")
    return path


# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team_derive.py", description="Author team-derived assets (owner-serialized).")
    parser.add_argument("--store", default=None)
    parser.add_argument("--by", default=None, help="Author identity (default: $CLAUDE_AGENT_NAME).")
    sub = parser.add_subparsers(dest="op", required=True)

    p_term = sub.add_parser("register-term", help="Register a term into .project/word.json (owner only).")
    p_term.add_argument("--term", required=True)
    p_term.add_argument("--ko", required=True)
    p_term.add_argument("--definition", required=True)
    p_term.add_argument("--use-when", required=True)

    p_mem = sub.add_parser("record-memory", help="Append an immutable team-memory record.")
    p_mem.add_argument("--key", required=True)
    p_mem.add_argument("--fact", required=True)
    p_mem.add_argument("--source", default="")

    sub.add_parser("render-memory", help="Regenerate .project/memory.md from the immutable records.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = resolve_store(args.store)
    by = resolve_identity(args.by, _repo_root_for_store(store))
    try:
        if args.op == "register-term":
            result = register_term(store, term=args.term, ko=args.ko, definition=args.definition, use_when=args.use_when, by=by)
        elif args.op == "record-memory":
            result = record_memory(store, key=args.key, fact=args.fact, source=args.source, by=by)
            render_memory(store)
        elif args.op == "render-memory":
            result = {"rendered": str(render_memory(store))}
        else:  # pragma: no cover
            raise DeriveAuthorError(f"unhandled op: {args.op}")
    except DeriveAuthorError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    json.dump({"ok": True, "op": args.op, "result": result}, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
