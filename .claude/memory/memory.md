# Memory

Durable project-level context. Not a task log or scratchpad.

## Input Contract

Read when a task depends on prior decisions, a component contract is changing, or the user asks for consistency with previous work.

Write only when the information is confirmed, stable, project-scoped, and useful later. Use the Memory Entry format in `AGENTS.md`.

## Durable Facts

## 2026-06-24 - Enforced Tasks→Skills→Agents promotion loop

Fact: The Tasks→Skills→Agents chain is enforced by two PostToolUse hooks plus a policy. `.claude/hooks/task_ledger.py` auto-records executed actions and skill-usage (a `SKILL.md` read) to `.context/task-log/`, and accepts `record-task` for semantic task signatures. `.claude/hooks/detect_promotions.py` evaluates the ledger against `.claude/policies/promotion.json` (skill: signature recurs ≥`min_recurrence` across ≥`min_distinct_sessions`; agent: skills package co-used ≥`min_cousage` across ≥`min_distinct_sessions`) and re-surfaces candidates via `additionalContext` until closed with `detect_promotions.py resolve`. Authoring stays a judgment step (`write-skill`/`write-subagent`); only the trigger is deterministic. Ledger output lives under git-ignored `.context/`.
Source: Implementation in this session (hooks, tests, policy, doc declaration in AGENTS.md *Enforced Promotion Loop*, propagation in `init_agent_clone.py`).
Use Later When: Tuning promotion thresholds, debugging why a candidate did or did not surface, or extending the clone generator.

## 2026-06-24 - Enforced Memory→preference/term derivation loop + 3x promotion frequency

Fact: Added a memory-derivation loop mirroring the promotion loop. `.claude/hooks/detect_derivations.py` (PostToolUse + SessionStart, also `record-signal`/`evaluate`/`resolve` subcommands) surfaces `preference` and `term` candidates from two deterministic sources: optional `Derive: preference` / `Derive: term: <word>` markers in `memory.md` entries (surface immediately) and `record-signal` observations in `.context/memory-log/signals.jsonl` (surface on recurrence). Thresholds live in `.claude/policies/derivation.json` (preference/term: `min_recurrence` 2, `min_distinct_sessions` 1); candidates already in `user_preferences.md`/`word.json` are skipped; authoring stays judgment (`user_preferences.md` write or `register-term`). Separately, `promotion.json` count gates were lowered ~3x for higher auto-update frequency: skill `min_recurrence` 3→1 and `min_distinct_sessions` 2→1; agent `min_cousage` 3→1 and `min_distinct_sessions` 2→1 (`min_package_size` stays 2). Diagnosis recorded: root `.mcp.json` is an empty (`{"mcpServers": {}}`) runtime no-op but kept as the documented project-neutral MCP seam referenced by `.claude/mcp/README.md`.
Source: Implementation in this session (detect_derivations.py + test_detect_derivations.py (21 tests), derivation.json, settings.json wiring, promotion.json + policies/README.md, AGENTS.md *Enforced Derivation Loop* + Memory Entry `Derive:` field, .claude/CLAUDE.md, init_agent_clone.py parity).
Use Later When: Tuning derivation/promotion thresholds, debugging why a preference/term candidate did or did not surface, or deciding whether to keep the empty `.mcp.json`.

## 2026-06-25 - Model Y 다중 에이전트 팀 (터미널, 미리알림 연동)

Fact: 이 폴더를 동일 구조 peer 에이전트 "팀"으로 확장했다. 채택 모델은 **Model Y** — Conductor 없이 **터미널 Claude**로 운영하며, 공유 `.claude/` 1벌(동일성 자동 보장) + 정체성 N개(`CLAUDE_AGENT_NAME` env, guard `guard_agent_workspace.py:64`가 최우선 해석). 미리알림 매핑은 **목록=Team / 할일=Task / 노트(body)=진행상태 채널**이며 그룹은 API 미노출이라 쓰지 않는다(목록의 container는 account). 두 채널: (1) `reminders-team-bridge` 스킬 — JXA(`osascript -l JavaScript`)로 미리알림 읽기/쓰기(list-teams·pull·add·complete·annotate·create-list·delete-list), TCC 권한 필요(샌드박스 해제). (2) `team-inbox` 스킬 — 공유 store `.team/inbox/<수신자>/<msgid>.json`에 메시지당 불변 파일 + `os.replace` atomic write, 정렬 가능 msgid, broadcast=로스터-자기, 멱등 ack. 공유 store는 `.team/`(in-tree; `.claude/policies/team.json`의 `shared_store_root`), 인스턴스 로스터·바인딩·예산은 `.team/team.json`. 작업 격리는 `agent-workspace.json` per-agent deny(형제 `agents/<other>/**` 차단; allow/deny는 read·write 공용). 받은 편지함은 Bash CLI로 접근 — path guard는 Read/Edit/Write/MultiEdit만 게이팅하므로 차단되지 않음. 정합성 감사로 확인된 단일 작성자 가정 3대 블로커(정체성 `"main"` 붕괴, 공유 store 부재, 무잠금 쓰기)를 각각 env 정체성·`.team`·atomic rename으로 해소.

Source: 이 세션 구현 — `.claude/skills/reminders-team-bridge/`(JXA+CLI+테스트15), `.claude/skills/team-inbox/`(CLI+테스트16), `.team/`(team.json·README·inbox), `agents/orchestrator|worker-1/`, `.claude/policies/team.json`·`agent-workspace.json` 배선, `.gitignore`(런타임 inbox·context 무시). 전체 91 테스트 통과, 미리알림 읽기/쓰기 라이브 검증(샌드박스 왕복).

Use Later When: 팀 예산(P1)·메모리 연합 스마트뷰(P2)·공유 작업공간 GUI를 이어 만들 때, 미리알림 연동 디버깅 시, 또는 새 peer 에이전트를 로스터에 추가할 때(team.json members + agent-workspace.json deny 갱신).

## 2026-06-25 - 목표 중심 명령 구조 + 팀스킬 2종 + P0(per-agent 격리) 검증

Fact: 사용자→팀 명령은 두 진입점 — (A) 목표(Goal) 설정 → Tasks 자동분해, (B) 미리알림 Tasks 직접등록 — 으로 수렴하며 둘 다 "Tasks→에이전트 할당"으로 귀착. 할당은 `agent-workspace.json` 작업 경계로 명시화되고 `.context→.claude`로 지속 승격(§9.4 계획). **예산 배분은 철회**(team.json budget 제거, priority는 할당 우선순위 입력으로만 잔존). 두 신규 팀스킬: (1) `set-team-goal`(`team_goal.py`) — 목표를 계약요소(objective·deliverable·success_criteria·verification 필수)와 함께 `.team/goals/<id>.json`(canonical 1파일/목표, os.replace)에 기록; success_criteria/verification은 자율 작업의 정지조건. (2) `create-team-agent`(`team_agent.py`) — Model Y peer 스캐폴딩: 개별(`.claude/memory`,`tasks`,`.context`)은 실파일 seed, 공유(`.claude/{hooks,policies,skills,settings.json,CLAUDE.md}`+`AGENTS.md`)는 root로 symlink, `.team/team.json` members 원자 등록, 멱등(`--force`는 seed 보존). `agent-clone-setup` 참조하되 역할 rewrite는 안 함(동질성). 정체성은 `CLAUDE_AGENT_NAME` env(launch 시 export). **P0 라이브 검증됨**: 심볼릭 hook이 `CLAUDE_PROJECT_DIR=agents/<name>/`에서 실행되어 기록이 `agents/<name>/.context/`에 격리(orchestrator 무오염), 심볼릭 정책도 guard가 정상 로드(exit 0). 메모리 역할 확정: 개별(`agents/<name>/.claude/memory/`)=사적 작업사실, 팀(`.team/memory/`+`.team/goals/`)=합의 결정+목표.

Source: 이 세션 — `.claude/skills/set-team-goal/`(team_goal.py+테스트12), `.claude/skills/create-team-agent/`(team_agent.py+테스트9), `.team/team.json`(budget 제거·goals_dir 추가), 실제 orchestrator/worker-1 스캐폴딩, `.context/team-tier-promotion-plan.md` §9. 전체 112 테스트 통과.

Use Later When: 미검증 1칸(인터랙티브 `claude`가 `agents/<name>/`를 프로젝트 루트로 잡고 심볼릭 settings.json hook 등록하는지) 확인 후 P1(팀 승격 코어) 진행 시, 또는 목표→Tasks 분해/팀 자율 업무(받은 편지함 피드백 루프) 설계 시.

## 2026-06-25 - P1 팀 승격 코어 구현 + 적대적 리뷰 (결함 2건 수정)

Fact: 팀 계층 승격을 개별 루프 무수정 위에 additive로 구현. `detect_team_promotions.py`(개별 `detect_promotions.py`의 sibling) — `agents/*/.context/` 원장을 읽기전용 fan-in, **distinct-AGENT 축**(`min_distinct_agents`, 폴더명=ground truth)으로 team_skill/team_agent 후보; `_team_occurrences`는 session이 아닌 **agent로 버킷팅**(verbatim 복사 시 distinct=1 붕괴 회피); 후보는 per-runner shard, 결정은 (kind,key)당 불변 파일 + atomic os.replace; `find_team_root`는 agent 하위에서 walk-up. `.team/policies/team-promotion.json`(min_distinct_agents=2, governance=orchestrator-authors). `task_ledger.py`에 조건부 `agent` stamp(env CLAUDE_AGENT_NAME, additive·후방호환). settings.json SessionStart 등록. `.team/promotions/` 런타임 gitignore. **적대적 리뷰(7에이전트)로 확정 결함 2건 수정**: (1) HIGH — 결정 파일명 `_safe(key)`가 many-to-one slug이라 `a+b+c`/`a_b+c` 충돌→덮어쓰기→영구 재노출; 파일명에 `sha1(key)[:8]` 추가로 해결. (2) MED — `.team` 부재 시 find_team_root가 start 폴백+무조건 write로 가짜 `.team/promotions/` 골격 생성+자가오염(SessionStart 무조건 등록이라 비-팀 클론 첫 세션 발생); 미발견 시 None 반환+가드 early-return으로 해결. 전체 134 테스트 통과(라이브: 2에이전트 같은 signature→표면화, 1에이전트 반복→미표면화, no-team→골격 무생성).

Source: 이 세션 — detect_team_promotions.py + test(22), task_ledger.py 편집, team-promotion.json, settings.json, review-team-tier-impl 워크플로우(13발견 중 2확정).

Use Later When: P1.5(symlink skill-use recorder), P2(팀 파생 term/preference/memory), 목표→Tasks 분해, 팀 자율 업무(inbox 피드백 루프+목표 정지조건) 설계 시. 결정 파일명/no-team 가드 디버깅 시.

## 2026-06-25 - P2 팀 파생 구현 + 적대적 리뷰 (결함 1건 수정)

Fact: 팀 파생을 P1과 동형으로 구현. `detect_team_derivations.py` — kind = term/preference/**memory**(memory는 팀 전용). 신호 3원천을 `agents/*` 가로질러 읽기전용 수집: (1) 개별 루프용 `signals.jsonl` **재사용**(term/preference, 에이전트 추가행동 0), (2) `team-signals.jsonl`(`record-team-signal`, explicit), (3) 개별 memory.md의 `Share:` 마커(explicit 즉시 qualify). distinct-AGENT 게이트(min_distinct_agents=2) + explicit 단축회로. present-check는 팀 store(`.team/word.json`·`.team/user_preferences.md`·`.team/memory/`). P1 수정 패턴(find_team_root None 가드·결정 파일명 sha1 해시·per-runner shard·atomic) 상속. `.team/policies/team-derivation.json`, settings.json SessionStart 배선, `.team/derivations/` 런타임 gitignore. **적대적 리뷰(5에이전트)로 확정 결함 1건 수정**: `_group_signals` 버킷 키가 대소문자 구분(`.strip()`)인데 존재검사는 `.lower()` → cross-agent에서 `LISA`/`lisa`가 단일-에이전트 그룹 2개로 쪼개져 게이트 미달·조용히 누락; 버킷을 `key.lower()`로 정규화(표시는 first-seen raw 보존)하고 `decided`/resolve도 정규화해 mis-cased resolve도 닫히게 수정. cheap fix 3건도 반영(record-team-signal이 DEFAULTS 대신 policy 경로 사용 / 재사용 `signals.jsonl`의 `explicit` 필드 ingest 시 차단 / surface 라벨 "explicit team signal"). 전체 151 테스트 통과(라이브: LISA/lisa 2에이전트→단일 team_term, 1에이전트→미표면화).

Source: 이 세션 — detect_team_derivations.py + test(17), team-derivation.json, settings.json, review-team-derivation 워크플로우(8발견 중 1확정).

Use Later When: P1.5(symlink skill-use recorder), 팀 파생 **저작**(term→`.team/word.json` owner 직렬화 / memory→`.team/memory/` 불변 record), 목표→Tasks 분해, 팀 자율 업무 설계 시. 팀 신호 대소문자/explicit 거동 디버깅 시.

## 2026-06-25 - 미리알림 통합 검증 + #1·#2·#3 빌드 (저작/skill-use/목표분해)

Fact: **미리알림+팀 통합 라이브 검증**(샌드박스): orchestrator가 미리알림 백로그 읽기→`team-inbox`로 worker-1 위임→worker-1이 미리알림 `body`에 진행상태 기록+완료 체크→완료 통지. 실 umc(5건)도 정상 읽힘. 두 채널(미리알림·받은 편지함)이 한 작업 위에서 협업 확인. 이어 3개 빌드: **#3 목표→Tasks 분해** — `set-team-goal`에 `decompose`(success_criterion 매핑 + `--assign`으로 `.team/tasks/`에 배정), `tasks`/`task-status`/`progress`(criteria가 done task로 덮였는지 = 목표 정지조건) 추가. **#1 팀 파생 저작** — 새 스킬 `team-derive-author`(`team_derive.py`): `register-term`은 **owner 직렬화**(`governance.authoring_owner`만 `.team/word.json` 쓰기, 비-owner 거부→inbox 제안; 단일 작성자라 무잠금 register_term 충돌 회피, 그래도 atomic+4필드+중복차단), `record-memory`는 `.team/memory/<ns>__<agent>__<slug>.json` 불변 + `render-memory`로 `.team/memory.md` 키별 last-wins fold. **#2 P1.5** — `task_ledger.py record-skill-use`(심볼릭 공유 skill의 Read가 path-매칭 안 될 때 SkillUse 이벤트 명시 stamp, additive). 전체 169 테스트 통과(이전 151 + 분해6 + 저작10 + skill-use2). `.team/goals`·`.team/tasks`·`.team/memory`·`.team/word.json`은 durable(gitignore 아님).

Source: 이 세션 — team_goal.py(decompose 등)+test, team-derive-author/(team_derive.py+test10+SKILL.md), task_ledger.py(record-skill-use)+test, set-team-goal SKILL.md 갱신, 통합 라이브 데모.

Use Later When: 팀 자율 업무(받은 편지함 피드백 루프 + 목표 progress 정지조건) 설계 시 — 4번은 사용자가 "나중에"로 보류. 목표→Tasks→미리알림 미러링이 필요할 때(현재 분해 task는 .team/tasks 내부, 미리알림과 별도).
