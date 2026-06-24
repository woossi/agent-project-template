#!/usr/bin/env python3
"""Initialize a local agent project or a cloned-agent bootstrap packet."""
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
PROJECT_REQUIRED_STRINGS = ("agent_name", "agent_purpose", "role")
PROJECT_REQUIRED_LISTS = ("workspace_paths", "inputs", "outputs", "verification", "constraints")
PROJECT_OPTIONAL_LISTS = ("operating_rules", "memory_rules", "initial_notes", "tools", "denied_paths")
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


def unique_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def normalize_project_setup(data: dict[str, Any]) -> dict[str, Any]:
    contract: dict[str, Any] = {key: require_string(data, key) for key in PROJECT_REQUIRED_STRINGS}
    for key in PROJECT_REQUIRED_LISTS:
        contract[key] = require_string_list(data, key)
    for key in PROJECT_OPTIONAL_LISTS:
        contract[key] = optional_string_list(data, key)
    contract["bash"] = normalize_bash(data)

    if not NAME_RE.fullmatch(contract["agent_name"]):
        raise ContractError("agent_name must use letters, numbers, dashes, or underscores")
    contract["workspace_paths"] = unique_strings(["."] + contract["workspace_paths"])
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


def render_agents_md(contract: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AGENTS.md",
            "",
            "## 목적",
            "",
            f"이 프로젝트는 `{contract['agent_name']}` 로컬 에이전트를 실행한다.",
            "",
            f"- 역할: {contract['role']}",
            f"- 목표: {contract['agent_purpose']}",
            "- 기본 응답 언어는 한국어다. 요청 산출물이 다른 언어를 요구할 때만 바꾼다.",
            "",
            "## 권한 순서",
            "",
            "충돌이 있으면 아래 순서로 따른다.",
            "",
            "1. 현재 사용자 요청",
            "2. 상위 시스템, 워크스페이스, 도구 지시",
            "3. `AGENTS.md`",
            "4. `.claude/CLAUDE.md`",
            "5. `.claude/memory/`",
            "6. `.claude/tasks/`",
            "7. `.claude/skills/`",
            "",
            "## 작업 경계",
            "",
            "허용 작업 경로:",
            render_list(contract["workspace_paths"]),
            "",
            "명시 차단 경로:",
            render_list(contract["denied_paths"]),
            "",
            "사용자 요청이 다른 경로를 명시하지 않으면 위 경계 밖을 탐색하지 않는다.",
            "외부 경로는 필요한 최소 파일만 읽고, 변경 전에는 목적과 산출물을 분명히 한다.",
            "",
            "## 입력",
            "",
            render_list(contract["inputs"]),
            "",
            "## 산출물",
            "",
            render_list(contract["outputs"]),
            "",
            "## 실행 규칙",
            "",
            render_list(contract["operating_rules"]),
            "",
            "## 도구",
            "",
            render_list(contract["tools"]),
            "",
            "## 검증",
            "",
            render_list(contract["verification"]),
            "",
            "## 제약",
            "",
            render_list(contract["constraints"]),
            "",
            "## 파일 계약",
            "",
            "| 파일 | 역할 |",
            "| --- | --- |",
            "| `AGENTS.md` | 에이전트 공유 계약과 작업 경계 |",
            "| `.claude/CLAUDE.md` | Claude 실행 어댑터 |",
            "| `.claude/settings.json` | Claude Code 설정과 hook 등록 |",
            "| `.claude/memory/` | 장기 맥락과 확정된 결정 |",
            "| `.claude/tasks/` | 현재 작업 단위 |",
            "| `.claude/skills/` | 반복 절차와 능력 |",
            "| `.claude/agents/` | 반복 역할 정의 |",
            "| `.context/` | 임시 handoff와 검증 산출물 |",
            "",
            "## 메모리 규칙",
            "",
            render_list(contract["memory_rules"]),
            "",
            "`.claude/memory/`에는 확정된 장기 맥락만 짧게 남긴다.",
            "임시 진행상황, 대량 산출물, handoff는 `.claude/tasks/` 또는 `.context/`에 둔다.",
            "",
        ]
    )


def render_claude_md(contract: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# .claude/CLAUDE.md",
            "",
            "@../AGENTS.md",
            "",
            "## 역할",
            "",
            f"Claude 런타임은 `{contract['agent_name']}`의 실행 어댑터다.",
            f"역할은 {contract['role']}이며, 목표는 {contract['agent_purpose']}이다.",
            "",
            "## 실행 규칙",
            "",
            "- 먼저 `AGENTS.md`의 계약과 현재 사용자 요청을 따른다.",
            "- 작업 전 필요한 최소 맥락만 읽는다.",
            "- 장기 맥락은 `.claude/memory/`, 현재 작업은 `.claude/tasks/`, 임시 산출물은 `.context/`에 분리한다.",
            "- 외부 작업 경로는 `AGENTS.md`의 작업 경계와 `.claude/policies/agent-workspace.json`을 함께 확인한다.",
            "- 반복 절차가 있으면 `.claude/skills/`에서 맞는 스킬을 읽고 적용한다.",
            "- 반복 역할이 필요할 때만 `.claude/agents/`를 사용한다.",
            "",
            "## 응답 규칙",
            "",
            "- 결과, 검증, 남은 위험을 짧게 보고한다.",
            "- 파일을 바꿨으면 핵심 경로를 명시한다.",
            "- 확인하지 않은 사실은 확정처럼 쓰지 않는다.",
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


def write_project_setup(root: Path, contract: dict[str, Any]) -> list[Path]:
    agents_path = root / "AGENTS.md"
    claude_path = root / ".claude/CLAUDE.md"
    claude_path.parent.mkdir(parents=True, exist_ok=True)
    agents_path.write_text(render_agents_md(contract), encoding="utf-8")
    claude_path.write_text(render_claude_md(contract), encoding="utf-8")
    return [agents_path, claude_path]


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


def update_project_policy(root: Path, contract: dict[str, Any]) -> Path:
    policy_path = root / ".claude/policies/agent-workspace.json"
    if policy_path.exists():
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContractError(f"invalid policy JSON: {policy_path}: {exc}") from exc
    else:
        policy = {"version": 1, "defaults": {}, "agents": {}}

    if not isinstance(policy, dict):
        raise ContractError("agent workspace policy must be a JSON object")

    defaults = policy.setdefault("defaults", {})
    if not isinstance(defaults, dict):
        raise ContractError("agent workspace policy defaults field must be an object")
    defaults["allow"] = contract["workspace_paths"]
    defaults["deny"] = contract["denied_paths"]
    defaults["bash"] = contract["bash"]

    agents = policy.setdefault("agents", {})
    if not isinstance(agents, dict):
        raise ContractError("agent workspace policy agents field must be an object")

    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return policy_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize a local agent project or clone bootstrap packet")
    parser.add_argument("--input", default="-", help="Input JSON path, or '-' for stdin")
    parser.add_argument("--project-root", default=".", help="Project root")
    parser.add_argument("--project-setup", action="store_true", help="Rewrite AGENTS.md and .claude/CLAUDE.md")
    parser.add_argument("--update-policy", action="store_true", help="Update .claude/policies/agent-workspace.json")
    args = parser.parse_args(argv)

    try:
        root = Path(args.project_root).expanduser().resolve()
        data = load_json(args.input)
        if args.project_setup:
            contract = normalize_project_setup(data)
            written = write_project_setup(root, contract)
            if args.update_policy:
                written.append(update_project_policy(root, contract))
        else:
            contract = normalize_contract(data)
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
