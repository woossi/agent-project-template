# AGENTS.md

## 목적

이 프로젝트는 `team-umc` 팀(Model Y 멀티 에이전트)을 실행한다. 같은 트리를 공유하는 peer 에이전트들이 `CLAUDE_AGENT_NAME` 정체성으로 구분되어 함께 일한다.

- 역할: UMC 논문화를 수행하는 Model Y 멀티 에이전트 연구 팀의 공유 진입 계약 — orchestrator가 백로그를 분해·할당하고 worker가 실행·기록하며, 미리알림(umc 목록)과 받은 편지함으로 조정한다
- 목표: UMC 연구 프로젝트의 분석 결과를 투고 가능한 논문으로 완성한다
- 기본 응답 언어는 한국어다. 요청 산출물이 다른 언어를 요구할 때만 바꾼다.

## 권한 순서

충돌이 있으면 아래 순서로 따른다.

1. 현재 사용자 요청
2. 상위 시스템, 워크스페이스, 도구 지시
3. `AGENTS.md`
4. `.claude/CLAUDE.md`
5. `.claude/policies/`
6. `.claude/memory/`
7. `.claude/tasks/`
8. `.claude/agents/`
9. `.claude/skills/`

## 작업 경계

허용 작업 경로:
- .
- /Users/ujunbin/project/umc (UMC 분석 프로젝트)
- /Users/ujunbin/research/UMC (UMC 논문화 작업)
- /Users/ujunbin/article (원문 PDF 라이브러리 · 읽기 전용 참고)

명시 차단 경로:
- (none)

사용자 요청이 다른 경로를 명시하지 않으면 위 경계 밖을 탐색하지 않는다.
외부 경로는 필요한 최소 파일만 읽고, 변경 전에는 목적과 산출물을 분명히 한다.

## 입력

- UMC 분석 프로젝트(`/Users/ujunbin/project/umc`)와 논문화 작업(`/Users/ujunbin/research/UMC`)의 데이터·산출물
- 미리알림 umc 목록의 작업 백로그
- 팀 목표(.project/goals/)와 받은 편지함(.project/inbox/) 메시지
- 사용자 요청

## 산출물

- 투고 가능한 논문 초고(전 섹션)
- 방법론 기여를 명확히 한 원고
- 진행상태 기록과 완료 통지

## 실행 규칙

- 목표를 Tasks로 분해해 에이전트에 할당하고 완료를 추적한다
- 미리알림과 받은 편지함 두 채널로 조정한다
- 필요한 최소 맥락만 읽는다

## 도구

- Read
- Edit
- Write
- Grep
- Glob
- Bash

## 검증

- 전 섹션 초고 완성
- 방법론 기여 명확화
- 지도교수 리뷰 통과

## 제약

- umc 목록 작업에 한정한다
- 근거 없이 내용을 만들지 않는다
- 검증하지 않은 주장은 불확실로 표시한다

## 컴포넌트 계층 관계 (Tasks → Skills → Agents)

작업, 스킬, 에이전트는 상향식 생성 사슬을 이룬다(이 사슬은 위 권한 순서와 다른 축이다).

- 작업(`.claude/tasks/`)은 가장 작은 작업 단위다. 에이전트가 실행 작업을 자동으로 기록·갱신하며(사용자가 큐레이션하지 않음), 작업 패킷은 현재 상태만 담는다. 실행 로그와 handoff는 `.context/`에 둔다.
- 스킬(`.claude/skills/`)은 반복되는 작업 묶음이 하나의 포괄 이름으로 묶일 수 있을 때 그 묶음을 승격해 만든 재사용 절차다.
- 에이전트(`.claude/agents/`)는 특정 스킬 패키지를 독립 컨텍스트에서 관리해야 할 때 만드는 서브에이전트다.

이 사슬의 트리거는 훅으로 강제된다. `.claude/hooks/task_ledger.py`가 실행 작업과 스킬 사용을 `.context/task-log/`에 자동 기록하고, `.claude/hooks/detect_promotions.py`가 `.claude/policies/promotion.json`의 조건으로 평가해 승격 후보를 매 턴과 세션 시작마다 다시 띄운다. 스킬 후보는 `write-skill`, 에이전트 후보는 `write-subagent`로 저작하고 `detect_promotions.py resolve`로 닫는다.

같은 방식으로 메모리 파생도 강제된다. `.claude/memory/memory.md`의 넓은 장기 사실 중 안정적 선호나 반복 용어는 `.claude/hooks/detect_derivations.py`가 `.claude/policies/derivation.json` 조건으로 평가해 후보로 띄운다. 메모리 항목의 선택적 `Derive: preference` / `Derive: term: <단어>` 표시나 `record-signal`로 기록된 신호가 입력이며, 선호 후보는 `user_preferences.md`에 적고 용어 후보는 `register-term` 스킬로 등록한 뒤 `detect_derivations.py resolve`로 닫는다.

## 파일 계약

| 파일 | 역할 |
| --- | --- |
| `AGENTS.md` | 에이전트 공유 계약과 작업 경계 |
| `.claude/CLAUDE.md` | Claude 실행 어댑터 |
| `.claude/settings.json` | Claude Code 설정과 hook 등록 |
| `.claude/hooks/` | settings.json이 호출하는 결정적 가드·검증 스크립트 |
| `.claude/policies/` | hook이 읽는 기계 판독 정책(JSON): 작업 경계와 승격 조건(`promotion.json`) |
| `.claude/memory/` | 장기 맥락과 확정된 결정 |
| `.claude/tasks/` | 에이전트가 자동 기록·갱신하는 가장 작은 작업 단위(현재 상태) |
| `.claude/skills/` | 반복 작업 묶음을 포괄 이름으로 승격한 재사용 절차 |
| `.claude/agents/` | 특정 스킬 패키지를 독립 컨텍스트에서 관리하는 서브에이전트 |
| `.context/` | 에이전트 실행 로그, 임시 handoff, 검증 산출물 |
| `.project/` | Model Y 팀 공유 store: 로스터(`team.json`)·목표(`goals/`)·받은 편지함(`inbox/`)·팀 정책·팀 승격/파생·회사 메모리(`memory/`) |
| `teams/<팀>/` | 하위 팀 폴더(회사→팀→워커 3계층). 팀 자산 `.claude/{skills,memory,tasks}`(워커 간 협력 스킬·팀 메모리)+`.context`, 마커 `.team-folder` |
| `teams/<팀>/<워커>/` | peer 워커별 작업·메모리·`.context`(정체성으로 격리, 공유 자산은 root로 symlink) |

## 메모리 규칙 (3계층 구획화)

- 개별 워커 작업 사실은 teams/<팀>/<워커>/.claude/memory/에 둔다
- 팀 합의·맥락은 teams/<팀>/.claude/memory/에 둔다
- 회사(프로젝트) 전체 결정·목표는 .project/memory/와 .project/goals/에 둔다

`.claude/memory/`에는 확정된 장기 맥락만 짧게 남긴다.
현재 작업 상태는 `.claude/tasks/`에 두고, 실행 로그·진행상황·handoff·대량 산출물은 `.context/`에 둔다.

## 팀 구조 (Model Y)

이 프로젝트는 단일 에이전트가 아니라 **공유 1벌 + 정체성 N개**(Model Y)로 운영하는 팀이다. Conductor 없이 터미널 Claude로 각 peer를 실행하며, 같은 파일시스템의 `.project/` 공유 store로 조정한다.

- **정체성**: 각 터미널에서 `export CLAUDE_AGENT_NAME=<이름>` 후 실행한다. 미설정 시 `main`으로 떨어져 정체성이 붕괴하므로 반드시 export한다. guard와 받은 편지함이 이 값을 읽는다.
- **로스터·하위 팀**: `.project/team.json`(멤버·역할·미리알림 바인딩·`subteams`). 8 워커가 4 하위 팀으로 묶인다 — **데이터**(data-engineer·data-curator·inference-runner, `umc-data`), **문서**(manuscript-writer·manuscript-steward, `umc-write`), **선행연구**(paper-scout, `umc-scout`), **검증**(stats-validator·quality-reviewer, `umc-review`). 각 워커는 정확히 한 팀. 로스터·하위 팀·격리 정책은 `team-setup.json` 하나로 `team-init`이 재생성하고, 팀 증분 추가는 `team-init add-subteam`을 쓴다(손으로 멤버를 고치지 않는다). 회사 전체 대시보드는 `umc` 목록.
- **격리(물리적+문서적, 3계층)**: `.claude/policies/agent-workspace.json`이 각 워커를 자기 폴더로 한정하고 다른 모든 워커 폴더(`teams/<팀>/<워커>/**`)를 차단한다(N² 엄격 격리 — 같은 팀 형제도 차단). 자기 팀 공용 자원(`teams/<팀>/.claude`)은 읽기 가능. 공유 자산(`.claude/{hooks,policies,settings.json,CLAUDE.md}`, `AGENTS.md`)은 root로 symlink되어 동일성이 자동 보장된다.
- **스킬 3계층 구획화**: 워커 스킬은 워커 폴더의 real dir, 팀 스킬은 `teams/<팀>/.claude/skills`(워커 간 워크플로우 고정), 프로젝트 스킬은 `.project/skills`(팀 간 자료 전달, 예정). 공유 root 스킬 중 **거버넌스**(`team-init·create-team-agent·agent-clone-setup·set-team-goal·team-derive-author`)는 governance owner(data-curator)에게만 symlink되고, 나머지 공용 스킬은 전원에게 symlink된다.
- **두 채널**: 미리알림(목록 `umc`, 사람도 보는 백로그·진행상태 — `reminders-team-bridge`)과 받은 편지함(`.project/inbox/`, 에이전트끼리 구조화 메시지 — `team-inbox`).
- **목표·작업**: 팀 목표는 `set-team-goal`로 `.project/goals/`에 기록하고 Tasks로 분해해 할당한다. 팀 합의 결정·용어·선호는 `.project/memory/`·`.project/word.json`·`.project/user_preferences.md`로 파생한다(`team-derive-author`). 팀 계층 승격/파생은 `.project/policies/team-promotion.json`·`team-derivation.json` 조건으로 distinct-agent 축에서 평가된다.
- **팀 정의 갱신**: 로스터·정책은 `team-init`이 `team-setup.json` 하나로 재생성한다.
