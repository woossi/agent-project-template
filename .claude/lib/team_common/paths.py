"""Root discovery helpers for the team checkout."""
from __future__ import annotations

from pathlib import Path


def find_team_root(start: Path) -> Path | None:
    """Return the nearest ancestor containing ``.project/``, else ``None``."""
    cur = start.resolve()
    for _ in range(10):
        if (cur / ".project").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None

