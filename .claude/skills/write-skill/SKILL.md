---
name: write-skill
description: Use when creating or updating a reusable project skill under .claude/skills.
---

# 스킬: write-skill

## 사용 시점

반복되는 작업 묶음이 하나의 포괄 이름으로 묶일 수 있을 때, 그 묶음을 `.claude/skills/<name>/` 스킬로 승격하거나 기존 스킬을 갱신해야 할 때 사용한다. `detect_promotions.py`가 스킬 승격 후보를 띄웠을 때도 이 스킬로 저작한다.

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
2. `detect_promotions.py`가 띄운 후보에서 시작하면 `.context/promotions/candidates.json`의 시그니처·반복 횟수·목표를 근거로 삼는다.
3. **공개 스킬 참조(선택)**: 승격 대상이 *에이전트 전용 도메인 스킬*(통계 검증·데이터 변환·공간통계·학술 글쓰기 등 외부에 표준 대응물이 있는 절차)이면, 저작 전에 **GitHub MCP로 공개 스킬을 검색해** 출발점·레퍼런스로 참고할 수 있다. `mcp__github__search_code`(예: `path:SKILL.md <도메인 키워드>`)나 `mcp__github__search_repositories`로 후보를 찾고, `mcp__github__get_file_contents`로 해당 `SKILL.md`를 읽는다(`anthropics/skills` 등 신뢰 가능한 저장소 우선). *팀 계약 스킬*(`team-*`, `reminders-team-bridge`, `set-team-goal`, `register-term`, `write-*` 등 이 팀 고유 조정 계약)이면 외부 대응물이 없으므로 생략한다. 참고는 입력일 뿐이며 채택·내부화는 항상 이 스킬로 닫는다 — 외부 스킬을 그대로 의존하지 않고 절차를 로컬 `SKILL.md`로 옮겨 적는다. 외부 스킬 검색 전용 MCP(skills-search/skills-mcp 등)는 별도 등록하지 않는다(이미 연결된 GitHub MCP로 충분).
4. `templates/SKILL.md`를 `.claude/skills/<name>/SKILL.md`로 복사해 채운다.
5. 필요한 보조 파일은 새 스킬 폴더 안에만 둔다.
6. 작업 패킷이나 서브에이전트 정의를 스킬 안에 저장하지 않는다.
7. 계약 연계 섹션은 `.claude/hooks/sync_component_contracts.py`가 관리하게 둔다.
8. 색인은 ConfigChange/PostToolUse 훅이 `.claude/hooks/update_skill_index.py`로 자동 갱신한다. 직접 확인하려면 같은 스크립트를 실행한다.
9. `python .claude/hooks/update_skill_index.py --check`로 색인이 최신인지 확인한다.
10. 후보에서 승격했다면 `python3 .claude/hooks/detect_promotions.py resolve --kind skill --key <시그니처> --decision promote`로 후보를 닫는다.

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
- 공개 스킬을 참조했어도 절차는 로컬 `SKILL.md`에 직접 적혀 있어야 하며, 외부 스킬·검색 도구에 런타임 의존하지 않아야 한다.
- 작업·서브에이전트와의 연계는 `계약 연계` 섹션에 남아 있어야 한다.
- `python .claude/hooks/update_skill_index.py --check`가 통과해야 한다.

## 자주 발생하는 실패 사례

- 일회성 작업을 스킬로 만듦 → `write-task`로 작업 패킷을 작성한다.
- 역할 정의를 스킬에 넣음 → `write-subagent`로 에이전트 정의를 작성한다.
- 색인을 손으로 수정함 → ConfigChange 훅이 `.claude/hooks/update_skill_index.py`로 자동 갱신한다.
