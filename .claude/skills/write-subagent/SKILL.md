---
name: write-subagent
description: Use when creating or updating a reusable Claude subagent definition under .claude/agents.
---

# 스킬: write-subagent

## 사용 시점

반복해서 맡길 역할을 `.claude/agents/<name>.md` 서브에이전트 정의로 만들어야 할 때 사용한다.

## 목적

서브에이전트의 역할, 입력, 출력, 도구, 작업 경계를 재사용 가능한 정의로 고정한다.

## 계약

- 서브에이전트는 반복 역할을 정의한다.
- 현재 목표와 완료 기준은 `.claude/tasks/tasks.md`에 둔다.
- 반복 절차는 `.claude/skills/`에 둔다.
- 일회성 클론 초기화는 `agent-clone-setup`을 쓴다.
- 경로 또는 Bash 제한이 있으면 `.claude/policies/agent-workspace.json`의 이름과 맞춘다.

## 입력

- 영어 kebab-case 에이전트 이름
- 역할과 사용 시점
- 허용 도구
- 읽을 입력
- 기대 출력
- 경로·Bash 제한 여부
- handoff 위치

## 절차

1. 반복 역할인지 확인한다. 일회성이면 `agent-clone-setup`을 쓴다.
2. `templates/AGENT.md`를 `.claude/agents/<name>.md`로 복사해 채운다.
3. YAML `name`은 파일명과 같은 안정 이름으로 둔다.
4. `description`은 `Use when...` 형태의 사용 조건만 적는다.
5. 역할에는 현재 작업 진행상황을 넣지 않는다.
6. 서브에이전트가 사용할 작업 입력은 `.claude/tasks/tasks.md`에서 받고, 필요한 능력은 `.claude/skills/`의 스킬로 참조한다.
7. 경계가 필요하면 `.claude/policies/agent-workspace.json`에 같은 이름으로 등록한다.
8. `.claude/agents/agents.md`에 파일과 역할을 반영한다.
9. 계약 연계 섹션은 `.claude/hooks/sync_component_contracts.py`가 관리하게 둔다.

## 출력 형식

- `.claude/agents/<name>.md`
- 선택 갱신: `.claude/policies/agent-workspace.json`
- 갱신: `.claude/agents/agents.md`

## 내부 자원

- `templates/` — 서브에이전트 템플릿 폴더
- `templates/AGENT.md` — Claude subagent 정의 템플릿

## 품질 점검

- 파일 하나가 에이전트 하나만 정의해야 한다.
- YAML `name`과 policy agent 이름이 일치해야 한다.
- 서브에이전트가 tasks 입력과 skills 능력을 어떻게 쓰는지 계약 연계가 보여야 한다.
- 작업 handoff는 `.context/agents/<agent-name>/`에 두어야 한다.
- 반복 절차를 에이전트 본문에 복사하지 않아야 한다.

## 자주 발생하는 실패 사례

- 일회성 작업자를 에이전트로 등록함 → `agent-clone-setup`을 사용한다.
- policy 이름과 YAML 이름이 다름 → 같은 이름으로 맞춘다.
- 작업 진행상황을 에이전트에 씀 → `.claude/tasks/`나 `.context/`로 옮긴다.
