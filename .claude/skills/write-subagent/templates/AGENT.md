---
name: agent-name
description: Use when this project needs a focused subagent for a repeatable responsibility.
tools: Read, Grep, Glob
---

# Role

이 서브에이전트가 반복해서 맡는 책임.

## Inputs

- 작업 패킷 또는 사용자 요청
- 읽어야 할 프로젝트 파일
- 필요한 스킬 이름

## Procedure

1. 입력과 경계를 확인한다.
2. 맡은 범위만 수행한다.
3. 결과와 검증 근거를 정리한다.

## Output

- 짧은 finding, patch, 또는 handoff summary

## Boundaries

- 허용 경로:
- 금지 경로:
- Bash 제한:

## Handoff

- `.context/agents/<agent-name>/`에 필요한 인수인계를 둔다.

<!-- component-contract:start -->
## 계약 연계

- 서브에이전트는 `.claude/tasks/tasks.md`의 작업 입력과 검증 기준을 받는다.
- 서브에이전트는 `.claude/skills/`의 스킬 능력을 필요한 경우 읽어 사용한다.
- 결과와 남은 위험은 작업 패킷 또는 `.context/agents/<agent-name>/`로 돌려준다.
- 반복 절차를 에이전트 본문에 복사하지 않는다.
<!-- component-contract:end -->
