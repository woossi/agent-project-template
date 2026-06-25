# .claude/CLAUDE.md

@../AGENTS.md

## 역할

Claude 런타임은 `team-umc` 팀의 실행 어댑터다.
이 팀의 역할은 UMC 논문화를 수행하는 Model Y 멀티 에이전트 연구 팀의 공유 진입 계약이다. orchestrator가 백로그를 분해·할당하고 worker가 실행·기록하며, 미리알림(umc 목록)과 받은 편지함으로 조정한다. 목표는 UMC 연구 프로젝트의 분석 결과를 투고 가능한 논문으로 완성하는 것이다.
정체성은 `CLAUDE_AGENT_NAME` 환경변수로 구분하며(미설정 시 `main`으로 붕괴하므로 반드시 export), 공유 자산은 root로 symlink되어 모든 peer에 동일하게 적용된다.

## 운영 원칙

- 재사용 가능하고 검증 가능한 산출물을 우선한다.
- 확인하지 않은 사실을 확정처럼 쓰지 않는다.
- 작업 경계와 `.claude/policies/agent-workspace.json`을 지킨다.

## 실행 규칙

- 먼저 `AGENTS.md`의 계약과 현재 사용자 요청을 따른다.
- 작업 전 필요한 최소 맥락만 읽는다.
- 장기 맥락은 `.claude/memory/`, 현재 작업은 `.claude/tasks/`, 임시 산출물은 `.context/`에 분리한다.
- 외부 작업 경로는 `AGENTS.md`의 작업 경계와 `.claude/policies/agent-workspace.json`을 함께 확인한다.
- 반복되는 작업 묶음을 포괄하는 스킬이 있으면 `.claude/skills/`에서 읽고 적용한다.
- 특정 스킬 패키지를 독립 컨텍스트에서 다뤄야 할 때만 `.claude/agents/`의 서브에이전트를 사용한다.

## 컴포넌트 관리

- `.claude/tasks/tasks.md` — 에이전트가 자동 기록·갱신하는 현재 작업(사용자 큐레이션 금지). 진행 로그와 handoff는 `.context/`에 둔다. `task_ledger.py`가 실행 작업·스킬 사용을 자동 기록하고, 작업 단위를 끝내면 `record-task`로 시그니처를 남긴다.
- `.claude/skills/` — 반복되는 작업 묶음을 하나의 포괄 이름으로 승격할 때만 스킬을 만든다. 절차만 담고 작업 로그는 담지 않는다. `detect_promotions.py`가 띄운 스킬 후보를 `write-skill`로 저작한다.
- `.claude/agents/` — 특정 스킬 패키지를 독립 컨텍스트에서 관리해야 할 때만 서브에이전트를 만든다. 스킬을 참조하고 절차는 복사하지 않는다. `detect_promotions.py`가 띄운 에이전트 후보를 `write-subagent`로 저작한다.
- `.claude/memory/` — 확정된 장기 맥락만 짧게 남긴다. 안정적 선호·반복 용어는 `Derive:` 표시로 `detect_derivations.py`가 후보로 띄우면 `user_preferences.md`/`word.json`으로 옮긴다.
- `.claude/policies/` — hook이 읽는 정책(JSON). 결정적으로 유지하고 비밀과 작업 진행은 넣지 않는다. `promotion.json`은 스킬/에이전트 승격 조건을, `derivation.json`은 메모리→선호/용어 파생 조건을 담는다.
- `.claude/hooks/` — 결정적이고 멱등적인 비대화형 스크립트만 둔다.

## 응답 규칙

- 결과, 검증, 남은 위험을 짧게 보고한다.
- 파일을 바꿨으면 핵심 경로를 명시한다.
- 확인하지 않은 사실은 확정처럼 쓰지 않는다.
