"""Small, deterministic file I/O helpers."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any


def load_json_dict(path: Path) -> dict[str, Any]:
    """Read a JSON object, returning ``{}`` when missing, invalid, or not an object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def atomic_write_json(
    path: Path,
    payload: Any,
    *,
    indent: int | None = 2,
    sort_keys: bool = True,
    trailing_newline: bool = True,
) -> None:
    """Atomically publish JSON via tmp-file + ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    text = json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=sort_keys)
    if trailing_newline:
        text += "\n"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically publish text via tmp-file + ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
