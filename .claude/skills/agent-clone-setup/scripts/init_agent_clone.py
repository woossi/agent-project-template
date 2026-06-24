#!/usr/bin/env python3
"""Initialize a cloned-agent bootstrap packet from a JSON input contract."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_STRINGS = (
    "agent_name",
    "source_agent",
    "clone_purpose",
    "role",
    "task_objective",
    "handoff_path",
)
REQUIRED_LISTS = (
    "inputs",
    "allowed_paths",
    "tools",
    "outputs",
    "verification",
    "constraints",
)
OPTIONAL_LISTS = ("denied_paths", "initial_notes")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class ContractError(ValueError):
    pass


def load_json(path: str | None) -> dict[str, Any]:
    try:
        raw = sys.stdin.read() if path in (None, "-") else Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError as exc:
        raise ContractError(f"cannot read input: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON input: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError("input must be a JSON object")
    return data


def require_string(data: dict[str, Any], key: str) -> str:
    if key not in data:
        raise ContractError(f"missing required field: {key}")
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"field must be a non-empty string: {key}")
    return value.strip()


def require_string_list(data: dict[str, Any], key: str) -> list[str]:
    if key not in data:
        raise ContractError(f"missing required field: {key}")
    value = data[key]
    if not isinstance(value, list) or not value:
        raise ContractError(f"field must be a non-empty string list: {key}")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ContractError(f"field must contain only non-empty strings: {key}")
    return [item.strip() for item in value]


def optional_string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ContractError(f"field must be a string list: {key}")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ContractError(f"field must contain only non-empty strings: {key}")
    return [item.strip() for item in value]


def normalize_bash(data: dict[str, Any]) -> dict[str, list[str]]:
    value = data.get("bash", {})
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ContractError("field must be an object: bash")
    normalized: dict[str, list[str]] = {}
    for key in ("allow", "deny"):
        raw = value.get(key, [])
        if not isinstance(raw, list):
            raise ContractError(f"bash.{key} must be a string list")
        if not all(isinstance(item, str) and item.strip() for item in raw):
            raise ContractError(f"bash.{key} must contain only non-empty strings")
        normalized[key] = [item.strip() for item in raw]
    return normalized


def normalize_contract(data: dict[str, Any]) -> dict[str, Any]:
    contract: dict[str, Any] = {key: require_string(data, key) for key in REQUIRED_STRINGS}
    for key in REQUIRED_LISTS:
        contract[key] = require_string_list(data, key)
    for key in OPTIONAL_LISTS:
        contract[key] = optional_string_list(data, key)
    contract["bash"] = normalize_bash(data)

    if not NAME_RE.fullmatch(contract["agent_name"]):
        raise ContractError("agent_name must use letters, numbers, dashes, or underscores")
    return contract


def project_relative_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"path escapes project root: {raw_path}") from exc
    return resolved


def render_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (none)"


def render_bootstrap(contract: dict[str, Any]) -> str:
    bash = contract["bash"]
    return "\n".join(
        [
            f"# Agent Clone Bootstrap: {contract['agent_name']}",
            "",
            "## Required Brief",
            f"- Agent: {contract['agent_name']}",
            f"- Source agent: {contract['source_agent']}",
            f"- Clone purpose: {contract['clone_purpose']}",
            "",
            "## Role",
            contract["role"],
            "",
            "## Objective",
            contract["task_objective"],
            "",
            "## Inputs",
            render_list(contract["inputs"]),
            "",
            "## Workspace Boundary",
            "Allowed paths:",
            render_list(contract["allowed_paths"]),
            "",
            "Denied paths:",
            render_list(contract["denied_paths"]),
            "",
            "## Tools",
            render_list(contract["tools"]),
            "",
            "## Bash Policy",
            "Allowed commands:",
            render_list(bash["allow"]),
            "",
            "Denied commands:",
            render_list(bash["deny"]),
            "",
            "## Expected Output",
            render_list(contract["outputs"]),
            "",
            "## Verification",
            render_list(contract["verification"]),
            "",
            "## Constraints",
            render_list(contract["constraints"]),
            "",
            "## Initial Notes",
            render_list(contract["initial_notes"]),
            "",
        ]
    )


def write_bootstrap(root: Path, contract: dict[str, Any]) -> list[Path]:
    handoff_dir = project_relative_path(root, contract["handoff_path"])
    handoff_dir.mkdir(parents=True, exist_ok=True)

    bootstrap = handoff_dir / "bootstrap.md"
    canonical = handoff_dir / "clone-input.json"
    bootstrap.write_text(render_bootstrap(contract), encoding="utf-8")
    canonical.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return [bootstrap, canonical]


def update_policy(root: Path, contract: dict[str, Any]) -> Path:
    policy_path = root / ".claude/policies/agent-workspace.json"
    if policy_path.exists():
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContractError(f"invalid policy JSON: {policy_path}: {exc}") from exc
    else:
        policy = {
            "version": 1,
            "defaults": {"allow": ["."], "deny": [], "bash": {"allow": [], "deny": []}},
            "agents": {},
        }

    if not isinstance(policy, dict):
        raise ContractError("agent workspace policy must be a JSON object")
    agents = policy.setdefault("agents", {})
    if not isinstance(agents, dict):
        raise ContractError("agent workspace policy agents field must be an object")

    agents[contract["agent_name"]] = {
        "allow": contract["allowed_paths"],
        "deny": contract["denied_paths"],
        "bash": contract["bash"],
    }
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return policy_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize a cloned-agent bootstrap packet")
    parser.add_argument("--input", default="-", help="Input JSON path, or '-' for stdin")
    parser.add_argument("--project-root", default=".", help="Project root")
    parser.add_argument("--update-policy", action="store_true", help="Update .claude/policies/agent-workspace.json")
    args = parser.parse_args(argv)

    try:
        root = Path(args.project_root).expanduser().resolve()
        contract = normalize_contract(load_json(args.input))
        written = write_bootstrap(root, contract)
        if args.update_policy:
            written.append(update_policy(root, contract))
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
