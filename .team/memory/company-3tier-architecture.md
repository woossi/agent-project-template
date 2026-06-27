# UMC 회사 3계층 아키텍처 (회사 → 팀 → 워커)

> 상태: **구현 완료.** 2026-06-27 orchestrator·사용자 합의 후 `feat/company-3tier-architecture` 브랜치에서 Phase 0–5 구현.
> 이 문서는 회사(프로젝트) 레벨 결정의 단일 출처다. 4팀 워커가 참조한다.

## 1. 토폴로지: 회사 → 팀 → 워커 (구현됨)

UMC를 **회사(프로젝트)**로 두고, 그 아래 **4개 하위 팀**, 각 팀 아래 **워커(peer)**를 둔다.
**물리적 디렉토리 계층**으로 구현됨: `teams/<팀>/<워커>/`. 팀도 워커처럼 `.claude/{skills,memory,tasks}`+`.context`로 자기 자산을 관리하고, `.team-folder` 마커로 워커와 구분된다.
격리는 N² deny(`agent-workspace.json`)를 유지하되 경로가 `teams/<팀>/<워커>/**`로 재생성됨 — 같은 팀 형제도 격리(엄격). 워커 발견·symlink 깊이는 `os.path.relpath`로 토폴로지 비의존.

| 하위 팀 | 워커 | 미리알림 목록 | 팀 orchestrator |
| --- | --- | --- | --- |
| **데이터** | data-engineer · data-curator · inference-runner | `umc-data` | data-curator |
| **문서** | manuscript-writer · manuscript-steward | `umc-write` | manuscript-steward |
| **선행연구** | paper-scout | `umc-scout` | paper-scout (1인) |
| **검증** | stats-validator · quality-reviewer | `umc-review` | quality-reviewer |

- 회사 전체 대시보드·팀 간 조정 채널은 기존 `umc` 목록 유지.
- **검증 팀을 별도로 둔 이유**: stats-validator·quality-reviewer의 역할 핵심은 "생산자와 분리된 독립 검증"이다(team.json 명시). 데이터/문서 팀에 흡수하면 검증 독립성이 깨진다.

### 범위 분할 규칙 (계층별, 엄격 유지 — 사용자 명시)

분할은 계층마다 한 단계 아래를 격리·분할하며, **지금처럼 엄격히 관리**한다.

| 분할 주체 | 분할 대상 | 분할 종류 |
| --- | --- | --- |
| **프로젝트** | 각 **팀**의 역할 | 역할 격리 & 분할 |
| **팀** | 각 **워커**의 역할 | 역할 격리 & 분할 |
| **워커** | 자기 작업 | **물리적**(폴더, `agent-workspace.json` N² deny) **+ 문서적**(역할 비중복) 둘 다 |

- 물리적 분할 = 기존 `agent-workspace.json`의 형제 폴더 deny(이미 작동).
- 문서적 분할 = team.json 역할 설명의 "경계 분할"(이미 촘촘). 워커 간 역할이 겹치지 않게 유지한다.
- 이 엄격성은 검증 독립성(생산자≠검증자)과 수치정본 단일출처(steward)를 지키는 토대다.

## 2. 스킬 3계층 — 승격이 *서로 다른 시스템*

세 계층은 같은 "스킬"이라는 이름을 쓰지만 **승격 시스템이 다르다.** 워커 스킬만 기존 구조를 유지하고, 팀·프로젝트 스킬은 별도 승격기를 띄운다.

| 계층 | 의미 | 승격 시스템 | 저장 위치 |
| --- | --- | --- | --- |
| **워커 스킬** | 단일 워커 전용 반복 절차 | **기존 승격 구조 유지**(`detect_promotions.py`, 1명 반복) | `agents/<이름>/.claude/skills/` |
| **팀 스킬** | 자주 발생하는 **워커 간 워크플로우를 고정** | **별도 시스템.** 트리거 = *워커 간 작업 전달 구조*(누가 누구에게 산출물을 넘기는 반복). 같은 하위 팀 내 ≥2 워커 협업 | `.team/teams/<팀>/skills/` (제안) |
| **프로젝트 스킬** | **팀 간 자료 전달** 구조를 고정 | **별도 시스템.** 트리거 = *팀 간 전달* 반복. 서로 다른 팀 ≥2 | `.team/skills/` (회사 레벨, 제안) |

### 팀·프로젝트 스킬의 설계 목적 (사용자 명시, 2026-06-27)

- **오케스트레이터 단일 진입.** 스킬 제작의 목적은 *오케스트레이터가 스킬 하나만 호출하면 산출물이 나오게* 하는 것이다. 워커 간/팀 간 워크플로우를 스킬로 고정해, 오케스트레이터가 개별 워커를 일일이 조율하지 않고 스킬을 통해 산출물을 얻는다.
- **팀 스킬 = 워커 간 워크플로우 고정.** 트리거는 단일 워커의 반복이 아니라 *워커 사이의 작업 전달 구조*다. 어떤 산출물 핸드오프가 자주 반복되면 그 워크플로우를 팀 스킬로 굳힌다.
- **프로젝트 스킬 = 팀 간 자료 전달 고정.** 예 — 데이터→문서(레지스트리·수치정본 핸드오프·그림 전달 규약), 선행→문서, 생산→검증.

- 현재 승격 훅(`detect_team_promotions.py`)은 distinct-agent를 *회사 전체*에서 센다. 팀·프로젝트 스킬 승격기는 카운트를 **계층 경계 안에서** 따로 세고(팀=팀 안 ≥2, 프로젝트=팀 ≥2 걸쳐), 트리거를 "반복"이 아니라 **"작업 전달 구조의 반복"**으로 바꿔야 한다. 워커 스킬 승격기(`detect_promotions.py`)는 손대지 않는다.

## 2-1. 서브에이전트 — 워커 스킬에 종속 (사용자 명시)

- **서브에이전트는 워커 종속을 우선한다.** 워커가 작업 수행 시 *병렬화해서 빠르고 간편하게* 처리해야 할 때만 만든다.
- **무조건 워커의 스킬에 종속된다.** 서브에이전트는 독립 컴포넌트가 아니라 특정 워커 스킬의 병렬 실행 수단이다. 팀·프로젝트 레벨 서브에이전트는 두지 않는다(그 레벨의 반복은 *스킬*로 고정한다).
- 기존 `.claude/agents/`의 `write-subagent` 경로를 유지하되, 새 서브에이전트는 반드시 모(母) 워커 스킬을 참조해야 한다.

## 3. 메모리 3계층 (대칭, 구획화)

사용자 요구: **프로젝트 자원 ≠ 팀 자원, 별도 시스템으로 구획화.**

| 계층 | 내용 | 저장 위치 |
| --- | --- | --- |
| **워커 메모리** | 개인 작업 사실 | `agents/<이름>/.claude/memory/` (기존) |
| **팀 메모리** | 하위 팀 합의·맥락 | `.team/teams/<팀>/memory/` (신규, 제안) |
| **프로젝트 메모리** | 회사 전체 결정·목표·**팀 간 자료 전달 계약** | `.team/memory/` (기존을 회사 레벨로 승격) |

## 4. 메모리 자동 정리 = 자체 hook + 스킬 (MCP 아님)

조사 결론: 평문·git추적·구획화·자동정리를 **동시에** 만족하는 MCP는 없다. 자동정리 내장 MCP(ai-memory)는 메모리를 단일 SQLite에 가둬 git diff·guard 격리·3계층 구획을 깬다. 따라서 **기존 `detect_*` 패턴(결정적 hook이 띄우고 + 판단적 스킬이 저작)과 대칭으로 자체 구현**한다.

- **트리거(hook)**: `cleanup_memory.py` — 결정적·멱등·비대화형.
- **저작(스킬)**: `curate-memory` — 판단으로 병합·요약·아카이브.
- **3 메커니즘**:
  - **A. Compaction(압축)**: 계층 메모리가 N항목/N바이트 초과 또는 M세션 경과 시 → 중복·만료 병합·요약.
  - **B. Staleness(모순/만료)**: 같은 키의 새 결정 유입 시 옛 항목에 `superseded_by` 플래그 → 아카이브 판정.
  - **C. Eviction(적층 정리)**: append-only `.team/memory/*.json`이 K개 초과 시 오래된·소비분을 `.team/memory/.archive/`로 이동(LRU).
- **MCP 역할**: (선택) Basic Memory를 별도 vault의 **읽기 전용 시맨틱 검색 보조**로만. 저장소는 건드리지 않는다. ai-memory·mem0은 구획화·격리·git추적을 깨므로 부적합.

## 5. 미리알림

- `umc-data` · `umc-write` · `umc-scout` · `umc-review` 4개 신규 목록 생성.
- 기존 `umc`(35항목, 7 open)는 **회사 전체 마일스톤·팀 간 조정 대시보드**로 유지.
- **그룹(폴더) API는 불가**(검증됨): JXA에서 list의 container는 account(iCloud)뿐, 그룹 클래스 미노출. 그래서 "목록 = 팀"으로 1:1 매핑한다. tmux 윈도우 = 팀 = 목록 = 정렬.

## 6. 런처 스크립트 (정체성 유실 방지)

tmux 윈도우가 늘수록 `CLAUDE_AGENT_NAME` export를 깜빡해 전부 `main`으로 붕괴할 위험이 비례해 커진다.
→ `.team/launch/<agent>.sh`에 `CLAUDE_AGENT_NAME`을 박아 윈도우별 런처를 둔다(제안).

## 구현 순서 (제안)

브랜치: `feat/company-3tier-architecture` (워커 산출물은 main에 별도 커밋 완료).

1. `team-setup.json`에 `subteams` 필드 추가 + `team_init.py`에 패스스루(모르는 필드는 현재 무시되므로 보존 한 줄 추가).
2. 미리알림 4목록 생성(`umc-data/write/scout/review`).
3. 런처 스크립트(`.team/launch/<agent>.sh`).
4. 메모리 3계층 디렉토리 + 자동정리 hook(`cleanup_memory.py`)/스킬(`curate-memory`).
5. 팀·프로젝트 스킬 승격기를 *별도 시스템*으로 신설(워커 스킬 승격기는 불변). 트리거 = 작업 전달 구조의 반복, distinct 축 = 계층 경계.

## 확정된 결정 (2026-06-27)

- **범위 분할**: 프로젝트→팀 역할 격리, 팀→워커 역할 격리, 워커=물리적(폴더)+문서적(역할) 둘 다, 엄격 유지. (§1 범위 분할 규칙)
- **스킬 승격 3계층 = 서로 다른 시스템**: 워커=기존 유지, 팀·프로젝트=별도 승격기. 목적=오케스트레이터 단일 진입. (§2)
- **서브에이전트**: 워커 종속 우선, 무조건 워커 스킬에 종속, 병렬화 목적에 한정. (§2-1)
- **메모리 자동정리**: 자체 hook+스킬, MCP는 검색 보조만. (§4)

## 구현 완료 상태 (Phase 0–5)

- **Phase 0**: team_agent.py·team_init.py·hooks를 토폴로지 비의존으로 일반화(`os.path.relpath` 깊이계산, subteams 유도, 거버넌스 allowlist, worker_dirs). 평면 fallback으로 전체 220 테스트 그린.
- **Phase 1**: 4 팀 폴더 골격 + `.team-folder` 마커로 팀/워커 구분 가드(워커 식별 필터 3곳).
- **Phase 2**: 8 워커 `git mv` → `teams/<팀>/<워커>/`, `sync --all --force`로 재배선, 거버넌스 5개를 7명에게서 회수. symlink 무결성 0 broken.
- **Phase 3**: 워커 전용 스킬 3개(stat-claim-verification→stats-validator, paper-review→quality-reviewer, academic-writing→manuscript-writer)를 root→워커로 이동(거꾸로 교정).
- **Phase 4**: agent-workspace.json 재생성(teams 경로 N²), .gitignore, 비워커(orchestrator·section-writer) 삭제(handoff는 `.team/memory/handoff/`로 보존).
- **Phase 5**: 실제 토폴로지 hook smoke test 통과, AGENTS.md·설계문서 갱신.

## 남은 후속 작업 (이번 범위 밖)

- **팀·프로젝트 스킬 승격기 신설**: 작업 전달 구조 반복을 탐지(1차 신호 = inbox 핸드오프 `from→to`). 계층 경계 distinct 축. 워커 스킬 승격기는 불변. (§2)
- `create-team-agent`의 AGENT.md 템플릿 "Shared … skills" 문구를 거버넌스 구획화 반영해 정정.
- 프로젝트 스킬 디렉토리(`.team/skills`) 실제 도입은 첫 팀 간 전달 스킬이 승격될 때.
