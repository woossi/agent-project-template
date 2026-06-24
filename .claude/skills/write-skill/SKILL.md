---
name: write-skill
description: Use when creating or updating a reusable project skill under .claude/skills.
---

# 스킬: write-skill

## 사용 시점

반복되는 작업 묶음이 하나의 포괄 이름으로 묶일 수 있을 때, 그 묶음을 `.claude/skills/<name>/` 스킬로 승격하거나 기존 스킬을 갱신해야 할 때 사용한다.

## 목적

반복되는 작업 묶음을 하나의 포괄 이름으로 승격해 재사용 가능한 절차로 작성하고, 작업·서브에이전트와의 경계를 분리한다.

## 계약

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차를 정의한다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조하며, 절차를 복사하지 않는다.
- 작업 목표와 진행상황은 `.claude/tasks/tasks.md`에 둔다.
- 특정 스킬 패키지를 독립 컨텍스트에서 다루는 역할은 `.claude/agents/`에 둔다.
- 스킬이 다른 파일을 포함하면 `SKILL.md`의 `내부 자원`에 모두 적는다.

## 입력

- 영어 kebab-case 스킬 이름
- 사용 시점
- 입력, 절차, 출력 형식
- 품질 점검
- 자주 발생하는 실패 사례

## 절차

1. 반복되는 작업 묶음을 하나의 포괄 이름으로 묶을 수 있는지 확인한다. 일회성 작업이면 `write-task`를 쓴다.
2. `templates/SKILL.md`를 `.claude/skills/<name>/SKILL.md`로 복사해 채운다.
3. 필요한 보조 파일은 새 스킬 폴더 안에만 둔다.
4. 작업 패킷이나 서브에이전트 정의를 스킬 안에 저장하지 않는다.
5. 계약 연계 섹션은 `.claude/hooks/sync_component_contracts.py`가 관리하게 둔다.
6. `.claude/skills/update-skill-index/scripts/update_index.py`를 실행해 색인을 갱신한다.
7. 점검 모드로 색인이 최신인지 확인한다.

## 출력 형식

- `.claude/skills/<name>/SKILL.md`
- 선택: `.claude/skills/<name>/references/`, `scripts/`, `templates/`
- 갱신: `.claude/skills/skills.md`

## 내부 자원

- `templates/` — 새 스킬을 만들 때 쓰는 템플릿 폴더
- `templates/SKILL.md` — 기본 스킬 문서 템플릿
- `templates/references/notes.md` — 참조 파일 템플릿
- `templates/scripts/run.py` — 실행 스크립트 템플릿

## 품질 점검

- 스킬 폴더명은 영어 kebab-case여야 한다.
- `SKILL.md`가 있어야 한다.
- `내부 자원`에 실제 포함 파일과 폴더가 모두 적혀야 한다.
- 작업 진행상황이나 도메인 사실을 스킬에 넣지 않아야 한다.
- 작업·서브에이전트와의 연계는 `계약 연계` 섹션에 남아 있어야 한다.
- `python .claude/hooks/update_skill_index.py --check`가 통과해야 한다.

## 자주 발생하는 실패 사례

- 일회성 작업을 스킬로 만듦 → `write-task`로 작업 패킷을 작성한다.
- 역할 정의를 스킬에 넣음 → `write-subagent`로 에이전트 정의를 작성한다.
- 색인을 손으로 수정함 → ConfigChange 훅이 `.claude/hooks/update_skill_index.py`로 자동 갱신한다.
