#!/usr/bin/env python3
"""Shared helpers for the project hooks.

Several hooks resolved the project root, walked up to the team repo root, found a
worker folder, and deep-merged a policy dict with byte-identical copies of the
same code. This module is the single source of truth for those primitives so the
copies cannot drift. Each helper is verified (AST-identical) against every former
inline copy before extraction.

Two ``project_dir`` flavours exist on purpose and are kept distinct:

- ``project_dir_simple`` — ``CLAUDE_PROJECT_DIR`` / payload cwd / cwd. Used by the
  detectors and guards that operate on the shared repo root.
- ``project_dir_per_agent`` — anchors to the repo root, then descends into the
  registered ``CLAUDE_AGENT_NAME`` worker folder so each peer's ledger/promotion
  state stays isolated. Used by ``task_ledger`` and ``detect_promotions``.

``guard_word_json`` keeps its own ``project_dir`` (different payload precedence)
and is intentionally not routed through here.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def project_dir_simple(payload: dict[str, Any]) -> Path:
    """Resolve the shared repo root from env, then payload cwd, then cwd."""
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(str(raw)).expanduser().resolve()


def find_repo_root(start: Path) -> Path:
    """Walk up from ``start`` to the team repo root.

    The root anchors the shared store: it contains ``.project/team.json``
    (canonical) or, as a fallback, ``AGENTS.md``. If nothing matches, keep
    ``start``.
    """
    for base in (start, *start.parents):
        if (base / ".project" / "team.json").is_file():
            return base
    for base in (start, *start.parents):
        if (base / "AGENTS.md").is_file():
            return base
    return start


def agent_root(root: Path, agent: str) -> Path | None:
    """The worker's folder under ``root``, supporting both topologies.

    Prefers the 2-tier location ``teams/<team>/<agent>/`` (any team), falls back
    to the flat ``agents/<agent>/``. Returns None if neither exists.
    """
    teams_dir = root / "teams"
    if teams_dir.is_dir():
        for team in teams_dir.iterdir():
            cand = team / agent
            if cand.is_dir():
                return cand
    flat = root / "agents" / agent
    return flat if flat.is_dir() else None


def project_dir_per_agent(payload: dict[str, Any]) -> Path:
    """Resolve the per-agent ledger/promotion anchor.

    Anchor to the repo root, then descend into the registered
    ``CLAUDE_AGENT_NAME`` worker folder when an identity is set, so every peer's
    state stays separated regardless of where the hook fires.
    ``CLAUDE_PROJECT_DIR`` supplies the shared repo root, not the per-agent
    destination. The ledger writer (``task_ledger``) and the promotion reader
    (``detect_promotions``) must agree on this exact directory.
    """
    explicit = os.environ.get("CLAUDE_PROJECT_DIR")
    start = Path(str(payload.get("cwd") or os.getcwd())).expanduser().resolve()
    root = Path(explicit).expanduser().resolve() if explicit else find_repo_root(start)
    agent = os.environ.get("CLAUDE_AGENT_NAME") or ""
    if agent:
        resolved = agent_root(root, agent)
        if resolved is not None:
            return resolved
    return root


def merge(base: dict[str, Any], override: Any) -> dict[str, Any]:
    """Deep-merge ``override`` into a shallow copy of ``base`` (dicts recurse)."""
    merged = dict(base)
    if isinstance(override, dict):
        for key, value in override.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = merge(merged[key], value)
            else:
                merged[key] = value
    return merged
