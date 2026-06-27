# UMC 회사 3계층 아키텍처 (회사 → 팀 → 워커)

> 상태: **구현 완료.** 2026-06-27 orchestrator·사용자 합의 후 `feat/company-3tier-architecture` 브랜치에서 Phase 0–5 구현.
> 이 문서는 회사(프로젝트) 레벨 결정의 단일 출처다. 4팀 워커가 참조한다.

## 1. 토폴로지: 회사 → 팀 → 워커 (구현됨)

UMC를 **회사(프로젝트)**로 두고, 그 아래 **4개 하위 팀**, 각 팀 아래 **워커(peer)**를 둔다.
**물리적 디렉토리 계층**으로 구현됨: `teams/<팀>/<워커>/`. 팀도 워커처럼 `.claude/{skills,memory,tasks}`+`.context`로 자기 자산을 관리하고, `.team-folder` 마커로 워커와 구분된다.
격리는 N² deny(`agent-workspace.json`)를 유지하되 경로가 `teams/<팀>/<워커>/**`로 재생성됨 — 같은 팀 형제도 격리(엄격). 워커 발견·symlink 깊이는 `os.path.relpath`로 토폴로지 비의존.

| 하위 팀 | 워커(생산자) | 미리알림 목록 | 팀 orchestrator(조율 전담) |
| --- | --- | --- | --- |
| **데이터** | data-engineer · data-curator · inference-runner | `umc-data` | **data-lead** (+회사 owner 겸) |
| **문서** | manuscript-writer · manuscript-steward | `umc-write` | **write-lead** |
| **선행연구** | paper-scout | `umc-scout` | **scout-lead** |
| **검증** | stats-validator · quality-reviewer | `umc-review` | **review-lead** |
| **분석** | causal-analyst | `umc-analysis` | **analysis-lead** |

> **조율 전담 팀장 신설(2026-06-27).** 기존엔 팀원 1명이 orchestrator를 겸했으나, 사용자 결정으로 **각 팀에 조율만 하는 전담 팀장 워커**(`<팀>-lead`)를 신설했다. 팀장은 산출물을 직접 생산하지 않고 (가)할당+품질지표·(나)품질원장·(다)자기팀 거버넌스·조정만 소유한다(생산자≠조율자). 14 워커. 회사 owner(COMPANY 거버넌스 + cross-team)는 `data-curator`→`data-lead`로 이전. team-setup.json source-of-truth 갱신 → team-init 재생성 → create-team-agent로 5 폴더 생성 → sync. 거버넌스가 기존 겸임자에서 회수되고 전담 팀장으로 이동(실측 검증, broken 0).

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
| **워커 스킬** | 단일 워커 전용 반복 절차 | **기존 승격 구조 유지**(`detect_promotions.py`, 1명 반복) | `teams/<팀>/<워커>/.claude/skills/` (실구현) |
| **팀 스킬** | 자주 발생하는 **워커 간 워크플로우를 고정** | **별도 시스템**(`detect_team_promotions.py`, 구현됨). 트리거 = *팀 내(INTRA) inbox 핸드오프 구조의 반복*. 같은 하위 팀 내 ≥2 워커 협업 | `teams/<팀>/.claude/skills/` (실구현) |
| **프로젝트 스킬** | **팀 간 자료 전달** 구조를 고정 | **별도 시스템**(`detect_team_promotions.py`, kind=`project_skill`, 구현됨). 트리거 = *팀 간(INTER) inbox 핸드오프 반복*. 서로 다른 팀 ≥2 | `.project/skills/` (회사 레벨 — 현재 부재, 첫 `project_skill` 승격 시 생성. hook은 경로부재를 정상처리: 없으면 빈 set) |

### 팀·프로젝트 스킬의 설계 목적 (사용자 명시, 2026-06-27)

- **오케스트레이터 단일 진입.** 스킬 제작의 목적은 *오케스트레이터가 스킬 하나만 호출하면 산출물이 나오게* 하는 것이다. 워커 간/팀 간 워크플로우를 스킬로 고정해, 오케스트레이터가 개별 워커를 일일이 조율하지 않고 스킬을 통해 산출물을 얻는다.
- **팀 스킬 = 워커 간 워크플로우 고정.** 트리거는 단일 워커의 반복이 아니라 *워커 사이의 작업 전달 구조*다. 어떤 산출물 핸드오프가 자주 반복되면 그 워크플로우를 팀 스킬로 굳힌다.
- **프로젝트 스킬 = 팀 간 자료 전달 고정.** 예 — 데이터→문서(레지스트리·수치정본 핸드오프·그림 전달 규약), 선행→문서, 생산→검증.

- **구현 완료(2026-06-27, C 작업).** `detect_team_promotions.py`가 **계층 경계 축**으로 inbox 핸드오프(`from→to`, `.consumed` 포함) 구조를 읽어 5종 신호를 띄운다. 트리거는 단순 task signature 반복이 아니라 **"작업 전달 구조의 반복"**이다. 워커 스킬 승격기(`detect_promotions.py`)·워커 파생기(`detect_derivations.py`)·`promotion.json`은 **무수정**(R2 불변 git-diff 0으로 검증).
  - **분기①(정상)** `team_skill`: 같은 팀(INTRA) 핸드오프 ≥`min_intra_handoffs`·≥2 워커 → 팀 워크플로우 스킬 후보.
  - **`project_skill`**: 다른 팀(INTER) 핸드오프 ≥`min_inter_handoffs` → 팀 간 전달 스킬 후보.
  - **분기②** `new_worker`(신호 전용): 팀 INTRA가 희소(`< sparsity_threshold`)한데 특정 워커가 과부하(task-log 부하지표 `worker_load`) → "그 팀에 워커 추가 검토" 신호. 1인 팀(scout)은 INTRA 구조적 0이므로 부하 floor 단독 판정.
  - **분기③** `rebalance`(신호 전용): 팀 INTRA가 희소한데 한 워커 쌍만 핸드오프 집중(그 외 0) → "역할 경계 재조정 검토" 신호.
  - **자동화 수준**: 4종 모두 후보를 **띄우기만** 한다. `team_skill`·`project_skill`은 owner(data-curator)가 `write-skill`로 저작, `new_worker`·`rebalance`는 **신호 전용**(자동 저작 없음, `team-init add-subteam`/역할경계 수동 검토). 모든 임계값은 `team-promotion.json`에서 주입(코드 리터럴은 `.get` 기본값으로만).

## 2-1. 서브에이전트 — 워커 스킬에 종속 (사용자 명시)

- **서브에이전트는 워커 종속을 우선한다.** 워커가 작업 수행 시 *병렬화해서 빠르고 간편하게* 처리해야 할 때만 만든다.
- **무조건 워커의 스킬에 종속된다.** 서브에이전트는 독립 컴포넌트가 아니라 특정 워커 스킬의 병렬 실행 수단이다. 팀·프로젝트 레벨 서브에이전트는 두지 않는다(그 레벨의 반복은 *스킬*로 고정한다).
- 기존 `.claude/agents/`의 `write-subagent` 경로를 유지하되, 새 서브에이전트는 반드시 모(母) 워커 스킬을 참조해야 한다.

## 3. 메모리 3계층 (대칭, 구획화)

사용자 요구: **프로젝트 자원 ≠ 팀 자원, 별도 시스템으로 구획화.**

| 계층 | 내용 | 저장 위치 |
| --- | --- | --- |
| **워커 메모리** | 개인 작업 사실 | `agents/<이름>/.claude/memory/` (기존) |
| **팀 메모리** | 하위 팀 합의·맥락 | `teams/<팀>/.claude/memory/` (실구현) |
| **프로젝트 메모리** | 회사 전체 결정·목표·**팀 간 자료 전달 계약** | `.project/memory/` (기존을 회사 레벨로 승격) |

## 4. 메모리 자동 정리 = 자체 hook + 스킬 (MCP 아님)

조사 결론: 평문·git추적·구획화·자동정리를 **동시에** 만족하는 MCP는 없다. 자동정리 내장 MCP(ai-memory)는 메모리를 단일 SQLite에 가둬 git diff·guard 격리·3계층 구획을 깬다. 따라서 **기존 `detect_*` 패턴(결정적 hook이 띄우고 + 판단적 스킬이 저작)과 대칭으로 자체 구현**한다.

- **트리거(hook)**: `cleanup_memory.py` — 결정적·멱등·비대화형.
- **저작(스킬)**: `curate-memory` — 판단으로 병합·요약·아카이브.
- **3 메커니즘**:
  - **A. Compaction(압축)**: 계층 메모리가 N항목/N바이트 초과 또는 M세션 경과 시 → 중복·만료 병합·요약.
  - **B. Staleness(모순/만료)**: 같은 키의 새 결정 유입 시 옛 항목에 `superseded_by` 플래그 → 아카이브 판정.
  - **C. Eviction(적층 정리)**: append-only `.project/memory/*.json`이 K개 초과 시 오래된·소비분을 `.project/memory/.archive/`로 이동(LRU).
- **MCP 역할**: (선택) Basic Memory를 별도 vault의 **읽기 전용 시맨틱 검색 보조**로만. 저장소는 건드리지 않는다. ai-memory·mem0은 구획화·격리·git추적을 깨므로 부적합.

## 5. 미리알림

- `umc-data` · `umc-write` · `umc-scout` · `umc-review` 4개 신규 목록 생성.
- 기존 `umc`(35항목, 7 open)는 **회사 전체 마일스톤·팀 간 조정 대시보드**로 유지.
- **그룹(폴더) API는 불가**(검증됨): JXA에서 list의 container는 account(iCloud)뿐, 그룹 클래스 미노출. 그래서 "목록 = 팀"으로 1:1 매핑한다. tmux 윈도우 = 팀 = 목록 = 정렬.

## 6. 런처 스크립트 (정체성 유실 방지)

tmux 윈도우가 늘수록 `CLAUDE_AGENT_NAME` export를 깜빡해 전부 `main`으로 붕괴할 위험이 비례해 커진다.
→ `.project/launch/<agent>.sh`에 `CLAUDE_AGENT_NAME`을 박아 윈도우별 런처를 둔다(제안).

## 구현 순서 (제안)

브랜치: `feat/company-3tier-architecture` (워커 산출물은 main에 별도 커밋 완료).

1. `team-setup.json`에 `subteams` 필드 추가 + `team_init.py`에 패스스루(모르는 필드는 현재 무시되므로 보존 한 줄 추가).
2. 미리알림 4목록 생성(`umc-data/write/scout/review`).
3. 런처 스크립트(`.project/launch/<agent>.sh`).
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
- **Phase 4**: agent-workspace.json 재생성(teams 경로 N²), .gitignore, 비워커(orchestrator·section-writer) 삭제(handoff는 `.project/memory/handoff/`로 보존).
- **Phase 5**: 실제 토폴로지 hook smoke test 통과, AGENTS.md·설계문서 갱신.

## 완료된 후속 작업 (C 작업, 2026-06-27)

- ✅ **팀·프로젝트 스킬 승격기 신설**: `detect_team_promotions.py`가 inbox 핸드오프(`from→to`) 구조를 계층 경계 축으로 읽어 5종(`team_skill`·`project_skill`·`new_worker`·`rebalance`·`team_agent`[deprecated, 읽기전용]) 신호를 띄움. 워커 스킬 승격기·파생기·`promotion.json` 무수정(R2 검증). 정책 = `team-promotion.json` v2. (§2)
- ✅ **부수 정합성**: governance owner fallback `orchestrator→data-curator` 대칭 정정(promotions·derivations 두 hook + 두 정책 mode 라벨). 유령/오타 candidates shard 3종 삭제(`paper-socut`·`quaility-reviewer`·`danggeun-scraper`, 정보손실 0). `stat-claim-verification` decision 본문 "root 배치"→실배치(워커 dir) 정정.

## 7. 팀 자율운영 루프 — 3종 정책 (구현 완료, 2026-06-27)

P0+P1+P2(팀 메일박스+claim) 위에 팀장 자율운영 3종을 얹었다. 한 닫힌 루프다: **팀 메일박스 도착 → (가) 팀장 자율 할당+품질지표 → 워커 실행 → 검증팀 판정 → (나) 2연속 실패 신호 → (다) 권한으로 팀장이 전문화 워커 생성.** 사양 단일출처: `.context/3policy-integration-spec.md`.

- ✅ **(다) 거버넌스 팀장 분산.** 거버넌스 5종을 2계층으로 분할(사용자 결정 Q1, 2026-06-27): **COMPANY**(`team-init`·`agent-clone-setup`)는 회사 owner(data-curator) 단독, **TEAM**(`create-team-agent`·`set-team-goal`·`team-derive-author`)은 각 subteam orchestrator(팀장)에게 분산. `team-init`은 분산 제외(사용자 명시). 자기팀 한정은 2겹 — 스킬 보유 게이트(symlink) + `_require_own_team` 대상팀 검사(호출자=대상팀 orchestrator인가; 회사 owner는 cross-team 허용, 미식별 정체성 fail-closed). `team_agent.py`: `_company_owner`/`_orchestrators`/`_orchestrator_of`/`_require_own_team`, `create_agent(subteam, requester)`, `_register_in_roster(subteam)`, `agent_dir_for(subteam_hint)`. 정책 `team-promotion.json` governance=`tiered`(company_owner+authoring_owner 별칭 하위호환+company_skills/team_skills). `team_init._governance_block`이 재생성. 5팀장 배선 실측·broken 0.
- ✅ **(가) 팀장 자율 할당 + 품질평가.** 할당은 최근접 워커 + 품질지표(quality_gate) 부착, 품질 판정은 **검증팀 위임**(원고=quality-reviewer review-gate, 데이터/분석=stats-validator — 사용자 결정 Q3 종류별 분담). `team_inbox.post`에 옵셔널 `quality_gate`/`verdict`/`work_ref`(기본 None, promoter 엣지해석 불변, 기존 메시지 영향 0). CLI `--quality-gate`/`--verdict`/`--work-ref`(JSON 검증).
- ✅ **(나) 2연속 실패 → 전문화 워커.** 신규 스킬 `team-quality-ledger`(LEAD_ONLY, 거버넌스 아님). `quality_ledger.py`: verdict를 (worker, kind)별 팀장 폴더 원장(`teams/<팀>/<팀장>/.context/quality-ledger.jsonl`)에 기록, **PASS만 통과·리셋, PARTIAL/FAIL 둘 다 실패**(사용자 결정 Q2). 2연속 비-PASS면 `signal`이 `spawn_specialized_worker` 권고. `mark-spawned` 후 같은 키 재실패는 `rebalance`로 격하(무한생성 방지). 자율 수준 **L1**(사용자 결정 Q4: 신호 후 팀장 판단, 무인 아님). 신호 축 분리 — verdict 축(quality_ledger) ≠ inbox 핸드오프 축(detect_team_promotions). promoter에 specialize_worker kind 미추가(중복·혼선 방지).
- ✅ **부수: 테스트 부채 청산.** `detect_team_promotions.py` 테스트 6건이 C 작업의 옛 트리거(task signature)를 검증한 채 남아 실패(미수정 잔존)했던 것을, 새 inbox 핸드오프 트리거(roster/handoff 헬퍼, key=team)로 갱신. team_init baseline-allow 재설계 후 stale였던 workspace-policy 테스트 2건도 새 설계(defaults.allow=baseline 재생성)로 정정. R2 보호 파일 무수정 유지.
- **검증:** 164 테스트 통과(create-team-agent 28·team-init 27·team-inbox 30·quality-ledger 12·promotions 22·derivations·dashboard 25 등), R2 PASS, broken symlink 0, (가)+(나)+(다) E2E 1흐름 통과.

## 남은 후속 작업 (이번 범위 밖)

- 새 전문화 워커의 작업경로 권한: create 시점엔 baseline-only(미등록 fail-closed, 안전 측 과소권한). 정식 경로 권한은 다음 `team-init`(team-setup.json에 새 워커 반영) 때 부여.
- `set-team-goal`/`team-derive-author`도 자기팀 한정 가드(`_require_own_team` 류)를 붙일지 — 현재 create만 가드. 두 스킬은 공유 store에 쓰므로 guard 격리가 1차 방어이나, 명시 가드 추가는 후속.
- `create-team-agent`의 AGENT.md 템플릿 "Shared … skills" 문구를 거버넌스 구획화 반영해 정정.
- 프로젝트 스킬 디렉토리(`.project/skills`) 실제 도입은 첫 팀 간 전달 스킬이 승격될 때(hook은 부재를 정상처리).
- `orchestrator.json` candidates shard 재발: 비정본 정체성(`CLAUDE_AGENT_NAME=orchestrator`) launch 신호. 후보 산출 영향 0(worker_dirs 부재). 정체성 export 규율 점검 후 삭제.
- 임계값(`min_intra_handoffs=8`·`min_inter_handoffs=20`·`min_overload_load=6.0` 등)은 현 inbox/task-log 스냅샷 기준. 누적 증가 시 `team-promotion.json`에서 재튜닝(코드 변경 불요, R2 안전).
