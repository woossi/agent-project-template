#!/usr/bin/env python3
"""Claude Code hook guard for project-scoped agent workspace policy."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Any


PATH_TOOLS = {"Read", "Edit", "Write", "MultiEdit"}
DIRECT_PATH_KEYS = ("file_path", "path", "notebook_path")


def load_payload() -> dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def project_dir(payload: dict[str, Any]) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(str(raw)).expanduser().resolve()


def resolve_policy_path(raw_path: str | None, root: Path) -> Path | None:
    if not raw_path:
        raw_path = os.environ.get("CLAUDE_AGENT_WORKSPACE_POLICY")
    if not raw_path:
        default_path = root / ".claude/policies/agent-workspace.json"
        return default_path if default_path.exists() else None

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def load_policy(path: Path | None, explicit: bool) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.exists():
        if explicit:
            print(f"Agent workspace policy not found: {path}", file=sys.stderr)
            return {}
        return None
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid agent workspace policy JSON: {path}: {exc}", file=sys.stderr)
        return {}
    if not isinstance(policy, dict):
        print(f"Invalid agent workspace policy: root must be an object: {path}", file=sys.stderr)
        return {}
    return policy


def active_agent_name(payload: dict[str, Any]) -> str:
    for key in ("CLAUDE_AGENT_NAME", "CLAUDE_SUBAGENT_NAME"):
        value = os.environ.get(key)
        if value:
            return value

    for key in ("agent_name", "subagent_name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value

    agent = payload.get("agent")
    if isinstance(agent, str):
        return agent
    if isinstance(agent, dict):
        for key in ("name", "type"):
            value = agent.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def merged_config(policy: dict[str, Any], agent_name: str) -> dict[str, Any]:
    defaults = policy.get("defaults")
    if not isinstance(defaults, dict):
        defaults = {}

    agents = policy.get("agents")
    if not isinstance(agents, dict):
        agents = {}
    agent_config = agents.get(agent_name)
    if not isinstance(agent_config, dict):
        agent_config = {}

    allow = (
        as_string_list(agent_config.get("allow"))
        if "allow" in agent_config
        else as_string_list(defaults.get("allow")) or ["."]
    )
    deny = as_string_list(defaults.get("deny")) + as_string_list(agent_config.get("deny"))

    default_bash = defaults.get("bash")
    if not isinstance(default_bash, dict):
        default_bash = {}
    agent_bash = agent_config.get("bash")
    if not isinstance(agent_bash, dict):
        agent_bash = {}

    bash_allow = (
        as_string_list(agent_bash.get("allow"))
        if "allow" in agent_bash
        else as_string_list(default_bash.get("allow"))
    )
    bash_deny = as_string_list(default_bash.get("deny")) + as_string_list(agent_bash.get("deny"))
    bash_enabled = bool(agent_bash.get("enabled", default_bash.get("enabled", True)))

    return {
        "agent": agent_name or "main",
        "allow": allow,
        "deny": deny,
        "bash": {"allow": bash_allow, "deny": bash_deny, "enabled": bash_enabled},
    }


def iter_tool_paths(tool_input: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in DIRECT_PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    return paths


def relative_path(raw_path: str, root: Path) -> str | None:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        rel = candidate.resolve(strict=False).relative_to(root)
    except ValueError:
        return None
    return rel.as_posix() or "."


def normalize_pattern(pattern: str, root: Path) -> str:
    path = Path(pattern).expanduser()
    if path.is_absolute():
        try:
            return path.resolve(strict=False).relative_to(root).as_posix()
        except ValueError:
            return pattern
    normalized = pattern.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized or "."


def path_matches(pattern: str, rel_path: str, root: Path) -> bool:
    pattern = normalize_pattern(pattern, root)
    if pattern in {".", "**", "**/*"}:
        return True
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return rel_path == prefix or rel_path.startswith(prefix + "/")
    return rel_path == pattern or fnmatch.fnmatchcase(rel_path, pattern)


def command_matches(pattern: str, command: str) -> bool:
    return fnmatch.fnmatchcase(command, pattern)


def check_path_policy(paths: list[str], root: Path, config: dict[str, Any]) -> int:
    for raw_path in paths:
        rel = relative_path(raw_path, root)
        if rel is None:
            print(
                f"Blocked {raw_path}: outside project root for agent {config['agent']}.",
                file=sys.stderr,
            )
            return 2
        if any(path_matches(pattern, rel, root) for pattern in config["deny"]):
            print(
                f"Blocked {rel}: denied by workspace policy for agent {config['agent']}.",
                file=sys.stderr,
            )
            return 2
        if not any(path_matches(pattern, rel, root) for pattern in config["allow"]):
            print(
                f"Blocked {rel}: outside allowed workspace for agent {config['agent']}.",
                file=sys.stderr,
            )
            return 2
    return 0


def check_bash_policy(command: str, config: dict[str, Any]) -> int:
    bash = config["bash"]
    if not bash["enabled"]:
        print(f"Blocked Bash: disabled for agent {config['agent']}.", file=sys.stderr)
        return 2
    if any(command_matches(pattern, command) for pattern in bash["deny"]):
        print(
            f"Blocked Bash command: denied by workspace policy for agent {config['agent']}.",
            file=sys.stderr,
        )
        return 2
    if bash["allow"] and not any(command_matches(pattern, command) for pattern in bash["allow"]):
        print(
            f"Blocked Bash command: Bash command is not allowed for agent {config['agent']}.",
            file=sys.stderr,
        )
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", help="Path to agent workspace policy JSON")
    args = parser.parse_args(argv)

    payload = load_payload()
    root = project_dir(payload)
    explicit_policy = bool(args.policy or os.environ.get("CLAUDE_AGENT_WORKSPACE_POLICY"))
    policy_path = resolve_policy_path(args.policy, root)
    policy = load_policy(policy_path, explicit_policy)
    if policy is None:
        return 0
    if policy == {}:
        return 2

    if payload.get("hook_event_name") != "PreToolUse":
        return 0

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    config = merged_config(policy, active_agent_name(payload))

    if tool_name in PATH_TOOLS:
        return check_path_policy(iter_tool_paths(tool_input), root, config)

    if tool_name == "Bash":
        command = tool_input.get("command")
        if isinstance(command, str):
            return check_bash_policy(command, config)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
