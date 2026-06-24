#!/usr/bin/env python3
"""Sync task, skill, and subagent contract scaffolding."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


BEGIN = "<!-- component-contract:start -->"
END = "<!-- component-contract:end -->"
RELEVANT_PREFIXES = (".claude/skills", ".claude/tasks", ".claude/agents")


MANAGED_SECTIONS = {
    Path(".claude/skills/write-skill/templates/SKILL.md"): """## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.""",
    Path(".claude/skills/write-task/templates/task.md"): """## 계약 연계

- 작업은 에이전트가 실행하는 가장 작은 작업 단위이며, 에이전트가 자동으로 기록하고 갱신한다.
- 작업 패킷은 현재 상태(목표, 입력, 검증, 완료 기준)만 담고, 진행 로그와 handoff는 `.context/`에 둔다.
- `사용할 스킬`에는 필요한 능력과 절차를 참조로 적는다. 절차를 복사하지 않는다.
- `사용할 서브에이전트`에는 역할, 담당 범위, handoff 위치를 적는다.
- 결과는 작업의 검증과 완료 기준으로 되돌아온다.""",
    Path(".claude/skills/write-subagent/templates/AGENT.md"): """## 계약 연계

- 서브에이전트는 특정 스킬 패키지를 독립 컨텍스트에서 관리하는 역할이다.
- 서브에이전트는 `.claude/tasks/tasks.md`의 작업 입력과 검증 기준을 받는다.
- 서브에이전트는 `.claude/skills/`의 스킬 능력을 참조하여 사용한다. 절차를 복사하지 않는다.
- 결과와 남은 위험은 작업 패킷 또는 `.context/agents/<agent-name>/`로 돌려준다.""",
}


def load_payload() -> dict[str, Any]:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def project_dir(raw: str | None) -> Path:
    value = raw or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Path(value).expanduser().resolve()


def normalize_rel(path_value: str, root: Path) -> str:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = root / path
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except ValueError:
        return path_value.replace("\\", "/")


def tool_paths(payload: dict[str, Any], root: Path) -> list[str]:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    paths: list[str] = []
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append(normalize_rel(value, root))
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for item in edits:
            if isinstance(item, dict):
                value = item.get("file_path") or item.get("path")
                if isinstance(value, str) and value:
                    paths.append(normalize_rel(value, root))
    return paths


def is_relevant_path(path: str) -> bool:
    normalized = path.lstrip("./")
    return normalized == "AGENTS.md" or normalized.startswith(RELEVANT_PREFIXES)


def should_run(payload: dict[str, Any], root: Path, force: bool) -> bool:
    if force or not payload:
        return True
    event = payload.get("hook_event_name")
    if event == "ConfigChange":
        matcher = payload.get("matcher")
        return matcher in (None, "skills", "agents", "tasks")
    if event != "PostToolUse":
        return False

    tool_name = payload.get("tool_name")
    if tool_name in {"Edit", "Write", "MultiEdit"}:
        return any(is_relevant_path(path) for path in tool_paths(payload, root))
    if tool_name == "Bash":
        tool_input = payload.get("tool_input")
        command = tool_input.get("command") if isinstance(tool_input, dict) else ""
        if not isinstance(command, str):
            return False
        return any(token in command for token in (".claude/skills", ".claude/tasks", ".claude/agents"))
    return False


def replace_managed_section(text: str, section: str) -> tuple[str, bool]:
    block = f"{BEGIN}\n{section.strip()}\n{END}"
    start = text.find(BEGIN)
    end = text.find(END)
    if start != -1 and end != -1:
        if end < start:
            raise ValueError("contract sync markers are out of order")
        end += len(END)
        new_text = text[:start].rstrip() + "\n\n" + block + "\n" + text[end:].lstrip("\n")
    elif start == -1 and end == -1:
        new_text = text.rstrip() + "\n\n" + block + "\n"
    else:
        raise ValueError("contract sync marker pair is incomplete")
    return new_text, new_text != text


def sync_template_sections(root: Path) -> list[Path]:
    changed: list[Path] = []
    for rel_path, section in MANAGED_SECTIONS.items():
        path = root / rel_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new_text, did_change = replace_managed_section(text, section)
        if did_change:
            path.write_text(new_text, encoding="utf-8")
            changed.append(path)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync skill, task, and subagent contract scaffolding")
    parser.add_argument("--project-root", default=None, help="Project root. Defaults to CLAUDE_PROJECT_DIR or cwd")
    parser.add_argument("--force", action="store_true", help="Run even if the hook payload is unrelated")
    args = parser.parse_args(argv)

    root = project_dir(args.project_root)
    payload = load_payload()
    if not should_run(payload, root, args.force):
        return 0

    try:
        changed = sync_template_sections(root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if changed:
        for path in changed:
            print(path)
    else:
        print("component contract structure is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
