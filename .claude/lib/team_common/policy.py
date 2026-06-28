"""Policy loading and governance helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import load_json_dict


def deep_merge(base: dict[str, Any], override: Any) -> dict[str, Any]:
    """Deep-merge ``override`` into a shallow copy of ``base``."""
    merged = dict(base)
    if isinstance(override, dict):
        for key, value in override.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
    return merged


def load_policy(path: Path, defaults: dict[str, Any]) -> dict[str, Any]:
    """Load a policy JSON object and overlay it on defaults."""
    return deep_merge(defaults, load_json_dict(path))


def governance_owner(policy: dict[str, Any], *keys: str, default: str) -> str:
    """Return the first non-empty governance owner field among ``keys``."""
    gov = policy.get("governance")
    if isinstance(gov, dict):
        for key in keys:
            owner = gov.get(key)
            if isinstance(owner, str) and owner.strip():
                return owner.strip()
    return default

