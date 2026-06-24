---
name: write-task
description: Use when creating or updating the current task packet under .claude/tasks.
---

# 스킬: write-task

## 사용 시점

에이전트가 실행 중인 현재 작업을 `.claude/tasks/tasks.md`에 현재 상태로 자동 기록·갱신해 유지해야 할 때 사용한다. 작업은 가장 작은 작업 단위이며, 다른 에이전트가 이어받을 수 있도록 현재 명세를 정리한다.

## 목적

작업 목표, 입력, 산출물, 위험, 검증, 완료 기준을 짧은 작업 패킷으로 고정한다.

## 계약

- 작업은 에이전트가 실행하는 가장 작은 작업 단위이며, 에이전트가 자동으로 기록하고 갱신한다(사용자가 큐레이션하지 않는다).
- 작업 패킷은 현재 상태만 담는다. 진행 로그와 handoff는 `.context/`에 두고, 지속 메모리는 `.claude/memory/`에 둔다.
- 반복되는 작업 묶음이 하나의 포괄 이름으로 묶이면 `.claude/skills/`의 스킬로 승격한다.
- 특정 스킬 패키지를 독립 컨텍스트에서 다뤄야 하면 `.claude/agents/`의 서브에이전트로 분리하고, 작업 패킷에 담당 범위와 handoff 위치를 적는다.

## 입력

- 사용자 요청
- 작업 배경
- 입력 파일 또는 출처
- 기대 산출물
- 필요한 결정
- 위험과 검증 기준

## 절차

1. 작업이 기록할 만큼 명확한지 확인한다.
2. `templates/task.md` 형식으로 `.claude/tasks/tasks.md`를 갱신한다.
3. 상태는 `대기`, `진행 중`, `막힘`, `완료` 중 하나로 적는다.
4. 모르는 내용은 추측하지 말고 `필요한 결정`이나 `위험`에 둔다.
5. 사용할 스킬과 서브에이전트가 있으면 이름과 입력 경계를 적는다.
6. 작업 단위를 끝내면 `python3 .claude/hooks/task_ledger.py record-task --signature <작업 종류 슬러그> --objective <한 줄 목표> --skills <쓴 스킬> --paths <주요 경로>`로 시그니처를 원장에 남긴다. 원시 실행은 훅이 자동 기록하지만, 반복 작업 묶음을 스킬로 승격하려면 시그니처가 필요하다.
7. `detect_promotions.py`가 승격 후보를 띄우면 `write-skill`/`write-subagent`로 저작하고 `detect_promotions.py resolve`로 닫는다.
8. 계약 연계 섹션은 `.claude/hooks/sync_component_contracts.py`가 관리하게 둔다.
9. 완료 기준이 검증 가능한지 확인한다.

## 출력 형식

- 갱신: `.claude/tasks/tasks.md`

## 내부 자원

- `templates/` — 작업 패킷 템플릿 폴더
- `templates/task.md` — 현재 작업 패킷 템플릿

## 품질 점검

- 현재 작업만 담겨야 한다.
- 완료 기준이 관찰 가능해야 한다.
- 서브에이전트 입력과 스킬 능력 참조가 필요한 경우 작업 패킷에 분리되어야 한다.
- 스킬 절차나 에이전트 역할 본문을 작업에 복사하지 않아야 한다.
- 장기 메모리로 보존할 내용은 작업이 아니라 `.claude/memory/` 후보로 분리해야 한다.

## 자주 발생하는 실패 사례

- 진행 로그를 계속 누적함 → 작업 패킷에는 현재 상태만 남기고, 진행 로그와 handoff는 `.context/`에 둔다.
- 완료 기준이 모호함 → 실행할 검증 명령이나 확인 조건으로 바꾼다.
- 에이전트 역할을 작업에 씀 → `write-subagent`로 역할 정의를 만든다.
