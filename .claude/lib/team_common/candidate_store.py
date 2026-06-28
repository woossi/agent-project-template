"""Shared candidate and decision store helpers."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from .io import atomic_write_json, load_json_dict


def safe_segment(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z가-힣._-]+", "_", text).strip("_")
    return (slug or "x")[:120]


def canonical_team_runner(_team_root: Path, _runner: str) -> str:
    """Team-tier global signals always fold into the shared ``team.json`` shard."""
    return "team"


def load_decisions(decisions_dir: Path, kinds: Iterable[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {kind: {} for kind in kinds}
    if not decisions_dir.is_dir():
        return out
    for path in sorted(decisions_dir.glob("*.json")):
        rec = load_json_dict(path)
        kind = rec.get("kind")
        key = rec.get("key")
        if kind in out and isinstance(key, str) and key:
            out[kind][key] = rec
    return out


def decision_record_path(decisions_dir: Path, kind: str, key: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return decisions_dir / f"{kind}__{safe_segment(key)}__{digest}.json"


def write_team_shard(team_root: Path, candidates_dir: str, candidates: dict[str, Any], runner: str) -> Path:
    runner = canonical_team_runner(team_root, runner)
    path = team_root / candidates_dir / f"{safe_segment(runner)}.json"
    atomic_write_json(path, candidates)
    return path

