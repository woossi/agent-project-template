# Memory

Durable project-level context. Not a task log or scratchpad.

## Input Contract

Read when a task depends on prior decisions, a component contract is changing, or the user asks for consistency with previous work.

Write only when the information is confirmed, stable, project-scoped, and useful later. Use the Memory Entry format in `AGENTS.md`.

## Durable Facts

## 2026-06-24~25 - 팀 인프라 빌드 이력 (압축 요약, 안정화·코드로 검증됨)

Fact: 이 폴더를 Model Y 다중 에이전트 팀으로 구축한 인프라 빌드 6단계를 압축 보존한다. 모두 코드·테스트로 검증·안정화됨. 상세 구현은 git 이력과 각 스크립트·테스트가 ground truth.
1. **Tasks→Skills→Agents 승격 루프**: `task_ledger.py`(PostToolUse, 실행 액션·skill-use 원장→`.context/task-log/`, `record-task`/`record-skill-use`) + `detect_promotions.py`(원장 vs `.claude/policies/promotion.json` 평가→`additionalContext` 후보, `resolve`로 닫음). 저작=judgment(`write-skill`/`write-subagent`), 트리거만 결정적. promotion.json 게이트 ~3x 하향(skill min_recurrence 1·min_distinct_sessions 1; agent min_cousage 1·min_package_size 2).
2. **Memory→preference/term 파생 루프**: `detect_derivations.py`(PostToolUse+SessionStart) — `memory.md`의 `Derive: preference`/`Derive: term:<word>` 마커(즉시) + `record-signal` 신호(재발 시) → 후보. 임계 `.claude/policies/derivation.json`(min_recurrence 2·min_distinct_sessions 1). 저작=`user_preferences.md` write 또는 `register-term`.
3. **두 조정 채널**: `reminders-team-bridge`(JXA `osascript`로 미리알림 읽기/쓰기, TCC 권한 필요·목록=Team/할일=Task/노트=진행상태) + `team-inbox`(공유 store `.project/inbox/<수신자>/<msgid>.json` 메시지당 불변파일·os.replace atomic·정렬 msgid·broadcast=로스터-자기·멱등 ack, Bash CLI 경유라 path guard 비대상). 정체성=`CLAUDE_AGENT_NAME` env(guard 최우선 해석). 단일작성자 3대 블로커(정체성 main 붕괴·공유store 부재·무잠금쓰기)를 env·`.project`·atomic rename으로 해소.
4. **목표 중심 명령 + peer 스캐폴딩 + P0 격리**: `set-team-goal`(`team_goal.py`: goal→`.project/goals/<id>.json`, `decompose`로 success_criterion→`.project/tasks/` 배정, `progress`=정지조건) + `create-team-agent`(`team_agent.py`: 개별 .claude/{memory,tasks,.context} 실파일 seed·공유 {hooks,policies,skills,settings.json,CLAUDE.md}+AGENTS.md는 root symlink·team.json members 원자등록·멱등). budget 철회(priority만 잔존). P0 라이브 검증: 심볼릭 hook이 `CLAUDE_PROJECT_DIR=agents/<name>/`에서 실행→기록 격리. 메모리 역할: 개별 `agents/<name>/.claude/memory/`=사적 사실, 팀 `.project/memory/`+`.project/goals/`=합의·목표.
5. **P1 팀 승격 + P2 팀 파생** (개별 루프 위 additive·동형): `detect_team_promotions.py`/`detect_team_derivations.py` — `agents/*/.context/` 읽기전용 fan-in, **distinct-AGENT 축**(폴더명=ground truth, min_distinct_agents=2, agent로 버킷팅해 verbatim 복사 시 distinct=1 붕괴 회피), per-runner shard·결정 (kind,key)당 불변파일+atomic. 파생 kind=term/preference/memory(memory는 팀 전용), 신호 3원천(`signals.jsonl` 재사용·`team-signals.jsonl`·memory.md `Share:` 마커). 정책 `.project/policies/team-promotion.json`·`team-derivation.json`(governance authoring_owner=orchestrator). 적대적 리뷰로 확정 결함 수정: 결정 파일명에 `sha1(key)[:8]`(slug 충돌), `find_team_root` 미발견 시 None+가드(가짜 .project 골격 자가오염), 버킷 키 `lower()` 정규화(대소문자 분리 누락).
6. **저작/skill-use/목표분해 빌드 + 통합 검증**: `team-derive-author`(`team_derive.py`: `register-term`=owner 직렬화 `.project/word.json`, `record-memory`=`.project/memory/<ns>__<agent>__<slug>.json` 불변 + `render-memory`로 `.project/memory.md` 키별 last-wins fold) + `task_ledger.py record-skill-use`(심볼릭 skill Read가 path 미매칭 시 명시 stamp). 미리알림+inbox 두 채널 라이브 협업 검증됨. `.project/{goals,tasks,memory,word.json}`은 durable(gitignore 아님), `.project/{inbox,promotions,derivations}`·`.context/`는 런타임 gitignore.
Source: 2026-06-24~25 구현 세션들. 각 스크립트(`.claude/hooks/`·`.claude/skills/`)·테스트(누적 169 통과)·`.claude/policies/`·`.project/policies/`·AGENTS.md 계약 섹션이 상세.
Use Later When: 승격/파생 임계 튜닝·후보 표면화 디버깅, 새 peer를 로스터에 추가(create-team-agent + team.json members + agent-workspace.json deny), 미리알림/inbox 연동 디버깅, 결정 파일명·no-team 가드·대소문자 거동 디버깅, 미검증 1칸(인터랙티브 `claude`가 `agents/<name>/`를 루트로 잡고 심볼릭 settings.json hook 등록하는지) 확인 시.

## 2026-06-25 - team-umc 정체성 셋업 (진입 파일·팀 정의 전환)

Fact: 중립 템플릿이던 이 프로젝트를 UMC 논문화 팀(`team-umc`) 정체성으로 전환. 사용자 확인: 이름=`team-umc`, UMC=연구 프로젝트/과제명, 범위="진입 파일 전환 + 팀 정의 재점검". (1) `agent-clone-setup --project-setup`으로 `agent-setup.json`(agent_name=team-umc, 목표=UMC 분석결과→투고 논문, 검증=전 섹션 초고·방법론 기여·지도교수 리뷰 통과)·`AGENTS.md`·`.claude/CLAUDE.md` 재작성 + `--update-policy`로 `agent-workspace.json` defaults 갱신. **핵심**: project-setup의 `update_project_policy`는 defaults만 덮고 `agents`는 setdefault라 orchestrator/worker-1 deny 경계 보존됨. project-setup 템플릿이 단일 에이전트 관점이라 AGENTS.md에 "팀 구조 (Model Y)" 섹션·파일계약 `.project/`·`agents/` 행 보강, CLAUDE.md 역할 문장의 "~한다이며/~한다이다" 어색함을 팀 관점 문장으로 수정. (2) `team-init`으로 팀 이름 research-umc→team-umc 통일(team.json·team-setup.json·team-promotion/derivation.json 재생성). 미리알림 목록(`umc`)·멤버(orchestrator/worker-1)·역할·governance(authoring_owner=orchestrator, min_distinct_agents=2)·목표(`umc-논문화`)는 보존 — `reminders_list`를 입력에서 빼면 None으로 덮이므로 명시 재지정. 검증: JSON 6개 유효, 회귀 테스트 22 passed, peer symlink가 새 진입 파일 자동 참조, guard 격리 스모크 정상. (후속) 사용자가 지정한 외부 입력 경로 2개를 작업 경계에 등록: `/Users/ujunbin/project/umc`(분석 프로젝트: analysis·config·docs)·`/Users/ujunbin/research/UMC`(논문화 작업: refs.bib·figures·parts·report_restructured·ITU UMC Data Hackathon). agent-setup.json workspace_paths·AGENTS.md 작업경계·입력에 반영, agent-workspace.json `defaults.allow`에는 guard glob 규칙상 `/**` 부착(폴더만 적으면 하위 미매칭). guard 재검증: 두 경로 하위 허용(exit 0), 미등록 외부경로·peer 폴더 차단(exit 2).

Source: 이 세션 — init_agent_clone.py --project-setup, AGENTS.md/CLAUDE.md Edit 보강, team_init.py init.

Use Later When: team-umc로 논문화 작업을 시작할 때, 새 peer를 로스터에 추가할 때(create-team-agent + team.json members + agent-workspace.json deny), 또는 "UMC" 용어를 `word.json`에 등록할 때(현재 정의 미확정 — 4필드를 사용자와 확인 후 register-term).

## 2026-06-27 - 작업 우선순위: 석사 학위논문 우선 / SSCI는 방향만 확정

Fact: 사용자가 두 active 목표의 우선순위를 명시했다 — **현재 우선순위는 `umc-학위논문`(B판 기반 석사 학위논문, 2026 가을 ~12월 심사)**. `umc-논문화`(SSCI Q1 투고)는 보류가 아니라 **방향성만 확정**된 상태로 후순위다. SSCI 2차 편집부 결정(Reject & Resubmit)에 대한 사용자 전략 방향은 확정됨 — (1) 타깃=둘 다(SSCR 방법론기여 + 도시계획 JAPA·Urban Studies·Cities) 이중 포지셔닝, (2) 전 트랙 병행, (3) 제목 간결화. 단 이는 *방향성*이며 즉시 착수 지시가 아니다. R&R 대응의 미해결 게이트(A-1 멀티에이전트 검증 착수 GO·재구조화 강도/우선순위·IRB 해당여부 PI확인·inference-runner/data-engineer 기동)는 **PDF(원고) 재작성 과정에서 재논의**한다 — 사용자가 분석 전면 수정 계획을 갖고 있어, 지금 트랙별 위임을 풀지 않는다(A-1 등 큰 재실행은 GO 대기 유지). data-engineer inbox에 쌓인 R&R 5대항목 트랙 위임은 학위논문 우선 동안 활성화하지 않는다.
Source: 사용자 직접 지시(이 세션). 근거 inbox: 2차 R&R 결정 메시지(.project/inbox/data-engineer/...__orchestrator__), 진단 agents/orchestrator/.context/handoff/reject-resubmit-decision-2026-06-26.md §사용자 결정 필요.
Use Later When: 작업 할당·peer 위임 우선순위를 정할 때(학위논문 트랙 먼저), SSCI R&R 재개 시점을 판단할 때(원고 전면 재작성 + 분석 수정과 함께 묶어 재논의), A-1/IRB/기동 게이트를 다시 띄울 때.
