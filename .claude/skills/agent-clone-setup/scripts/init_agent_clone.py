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
            "5. `.claude/policies/`",
            "6. `.claude/memory/`",
            "7. `.claude/tasks/`",
            "8. `.claude/agents/`",
            "9. `.claude/skills/`",
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
            "## 컴포넌트 계층 관계 (Tasks → Skills → Agents)",
            "",
            "작업, 스킬, 에이전트는 상향식 생성 사슬을 이룬다(이 사슬은 위 권한 순서와 다른 축이다).",
            "",
            "- 작업(`.claude/tasks/`)은 가장 작은 작업 단위다. 에이전트가 실행 작업을 자동으로 기록·갱신하며(사용자가 큐레이션하지 않음), 작업 패킷은 현재 상태만 담는다. 실행 로그와 handoff는 `.context/`에 둔다.",
            "- 스킬(`.claude/skills/`)은 반복되는 작업 묶음이 하나의 포괄 이름으로 묶일 수 있을 때 그 묶음을 승격해 만든 재사용 절차다.",
            "- 에이전트(`.claude/agents/`)는 특정 스킬 패키지를 독립 컨텍스트에서 관리해야 할 때 만드는 서브에이전트다.",
            "",
            "이 사슬의 트리거는 훅으로 강제된다. `.claude/hooks/task_ledger.py`가 실행 작업과 스킬 사용을 `.context/task-log/`에 자동 기록하고, `.claude/hooks/detect_promotions.py`가 `.claude/policies/promotion.json`의 조건으로 평가해 승격 후보를 매 턴과 세션 시작마다 다시 띄운다. 스킬 후보는 `write-skill`, 에이전트 후보는 `write-subagent`로 저작하고 `detect_promotions.py resolve`로 닫는다.",
            "",
            "## 파일 계약",
            "",
            "| 파일 | 역할 |",
            "| --- | --- |",
            "| `AGENTS.md` | 에이전트 공유 계약과 작업 경계 |",
            "| `.claude/CLAUDE.md` | Claude 실행 어댑터 |",
            "| `.claude/settings.json` | Claude Code 설정과 hook 등록 |",
            "| `.claude/hooks/` | settings.json이 호출하는 결정적 가드·검증 스크립트 |",
            "| `.claude/policies/` | hook이 읽는 기계 판독 정책(JSON): 작업 경계와 승격 조건(`promotion.json`) |",
            "| `.claude/memory/` | 장기 맥락과 확정된 결정 |",
            "| `.claude/tasks/` | 에이전트가 자동 기록·갱신하는 가장 작은 작업 단위(현재 상태) |",
            "| `.claude/skills/` | 반복 작업 묶음을 포괄 이름으로 승격한 재사용 절차 |",
            "| `.claude/agents/` | 특정 스킬 패키지를 독립 컨텍스트에서 관리하는 서브에이전트 |",
            "| `.context/` | 에이전트 실행 로그, 임시 handoff, 검증 산출물 |",
            "",
            "## 메모리 규칙",
            "",
            render_list(contract["memory_rules"]),
            "",
            "`.claude/memory/`에는 확정된 장기 맥락만 짧게 남긴다.",
            "현재 작업 상태는 `.claude/tasks/`에 두고, 실행 로그·진행상황·handoff·대량 산출물은 `.context/`에 둔다.",
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
            "## 운영 원칙",
            "",
            "- 재사용 가능하고 검증 가능한 산출물을 우선한다.",
            "- 확인하지 않은 사실을 확정처럼 쓰지 않는다.",
            "- 작업 경계와 `.claude/policies/agent-workspace.json`을 지킨다.",
            "",
            "## 실행 규칙",
            "",
            "- 먼저 `AGENTS.md`의 계약과 현재 사용자 요청을 따른다.",
            "- 작업 전 필요한 최소 맥락만 읽는다.",
            "- 장기 맥락은 `.claude/memory/`, 현재 작업은 `.claude/tasks/`, 임시 산출물은 `.context/`에 분리한다.",
            "- 외부 작업 경로는 `AGENTS.md`의 작업 경계와 `.claude/policies/agent-workspace.json`을 함께 확인한다.",
            "- 반복되는 작업 묶음을 포괄하는 스킬이 있으면 `.claude/skills/`에서 읽고 적용한다.",
            "- 특정 스킬 패키지를 독립 컨텍스트에서 다뤄야 할 때만 `.claude/agents/`의 서브에이전트를 사용한다.",
            "",
            "## 컴포넌트 관리",
            "",
            "- `.claude/tasks/tasks.md` — 에이전트가 자동 기록·갱신하는 현재 작업(사용자 큐레이션 금지). 진행 로그와 handoff는 `.context/`에 둔다. `task_ledger.py`가 실행 작업·스킬 사용을 자동 기록하고, 작업 단위를 끝내면 `record-task`로 시그니처를 남긴다.",
            "- `.claude/skills/` — 반복되는 작업 묶음을 하나의 포괄 이름으로 승격할 때만 스킬을 만든다. 절차만 담고 작업 로그는 담지 않는다. `detect_promotions.py`가 띄운 스킬 후보를 `write-skill`로 저작한다.",
            "- `.claude/agents/` — 특정 스킬 패키지를 독립 컨텍스트에서 관리해야 할 때만 서브에이전트를 만든다. 스킬을 참조하고 절차는 복사하지 않는다. `detect_promotions.py`가 띄운 에이전트 후보를 `write-subagent`로 저작한다.",
            "- `.claude/memory/` — 확정된 장기 맥락만 짧게 남긴다.",
            "- `.claude/policies/` — hook이 읽는 정책(JSON). 결정적으로 유지하고 비밀과 작업 진행은 넣지 않는다. `promotion.json`은 스킬/에이전트 승격 조건을 담는다.",
            "- `.claude/hooks/` — 결정적이고 멱등적인 비대화형 스크립트만 둔다.",
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


def serialize_project_input(contract: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in PROJECT_REQUIRED_STRINGS:
        payload[key] = contract[key]
    for key in PROJECT_REQUIRED_LISTS:
        payload[key] = contract[key]
    for key in PROJECT_OPTIONAL_LISTS:
        if contract.get(key):
            payload[key] = contract[key]
    bash = contract.get("bash", {})
    if bash.get("allow") or bash.get("deny"):
        payload["bash"] = bash
    return payload


def write_project_input(root: Path, contract: dict[str, Any], name: str) -> Path:
    input_path = project_relative_path(root, name)
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(
        json.dumps(serialize_project_input(contract), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return input_path


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
    parser.add_argument(
        "--save-input",
        default="agent-setup.json",
        help="Path to persist the normalized project-setup input JSON (project-setup only)",
    )
    parser.add_argument(
        "--no-save-input",
        action="store_true",
        help="Skip writing the normalized project-setup input JSON",
    )
    args = parser.parse_args(argv)

    try:
        root = Path(args.project_root).expanduser().resolve()
        data = load_json(args.input)
        if args.project_setup:
            contract = normalize_project_setup(data)
            written = []
            if not args.no_save_input and args.save_input:
                written.append(write_project_input(root, contract, args.save_input))
            written += write_project_setup(root, contract)
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
