# 작업

team-umc 팀의 현재 작업 패킷입니다. 가장 작은 작업 단위이며, 에이전트가 자동으로 기록·갱신합니다(사용자가 큐레이션하지 않음). 작업 패킷은 현재 상태만 담고, 진행 로그와 handoff는 `.context/`에 둡니다.
작성과 갱신은 `.claude/skills/write-task/SKILL.md`를 따릅니다.

## 현재 작업

상태: 진행 중 (orchestrator — 학위논문(B판) 전환 추적)

★★ 3종 정책 통합설계 — 팀 자율운영 루프 구현 완료 (2026-06-27, P0+P1+P2 위에 얹음)
- ★사용자 요청: "3종 통합설계 진행". 사양 단일출처 `.context/3policy-integration-spec.md`. 한 닫힌 루프 — 팀 메일박스 도착→(가)팀장 자율할당+품질지표→워커 실행→검증팀 판정→(나)2연속 실패 신호→(다)권한으로 팀장이 전문화 워커 생성.
- ★사용자 결정 4종: Q1 거버넌스=전역2(team-init·agent-clone-setup→data-curator)/팀장3(create-team-agent·set-team-goal·team-derive-author→각 orchestrator). Q2 PARTIAL=실패(PASS만 통과·리셋). Q3 비원고게이트=종류별분담(원고=quality-reviewer·데이터/분석=stats-validator). Q4 자율=L1(신호 후 팀장 판단, 무인 아님).
- ★(다) 거버넌스 팀장 분산: team_agent.py GOVERNANCE_COMPANY/TEAM 분할+LEAD_ONLY(team-quality-ledger). _company_owner·_orchestrators·_require_own_team(자기팀 한정 2겹: 스킬 게이트+대상팀 검사, 회사owner cross-team 허용·미식별 fail-closed)·create_agent(subteam,requester)·_register_in_roster(subteam)·agent_dir_for(subteam_hint). team-promotion.json governance=tiered(company_owner+authoring_owner별칭+company/team_skills). team_init._governance_block 재생성. 5팀장 배선 실측·broken0.
- ★(가) 팀장 자율할당+품질평가: 품질판정=검증팀 위임(원고 review-gate·데이터/분석 stats-validator). team_inbox.post 옵셔널 quality_gate/verdict/work_ref(기본 None, promoter 엣지해석 불변, 기존 메시지 영향0)+CLI --quality-gate/--verdict/--work-ref(JSON검증).
- ★(나) 2연속 실패→전문화 워커: 신규 스킬 team-quality-ledger(LEAD_ONLY). quality_ledger.py record/signal/mark-spawned, 팀장 폴더 원장(teams/<팀>/<팀장>/.context/quality-ledger.jsonl), PASS만 리셋·PARTIAL/FAIL 실패, 2연속 비-PASS→spawn 권고, mark후 재실패→rebalance(무한생성 방지). 신호 축 분리(verdict축≠inbox핸드오프축, promoter에 specialize 미추가).
- ★대시보드 adapters.py: inbox_post quality필드 + quality_record/signal/mark_spawned + agent_create(own-team).
- ★부수: detect_team_promotions 테스트 6건이 C작업 옛 트리거(task signature) 검증한 채 실패 잔존하던 것을 새 inbox 핸드오프 트리거(roster/handoff 헬퍼·key=team)로 갱신. team_init baseline-allow 재설계 후 stale였던 workspace-policy 테스트 2건도 새 설계(defaults.allow=baseline 재생성)로 정정. R2 무수정.
- ★검증: 263 테스트 통과(회귀0)·R2 PASS(4 보호파일 git-hash 무변)·broken symlink0·(가)+(나)+(다) E2E 1흐름(할당→verdict 2연속FAIL→signal→팀장 자기팀 워커생성→가드 일반워커 거부→anti-thrash rebalance) 통과.
- 남은(범위밖): 새 전문화워커 작업경로 권한은 다음 team-init까지 baseline-only(fail-closed 과소권한). set-team-goal/team-derive-author 자기팀 가드 명시추가(현재 create만). create-team-agent AGENT.md 템플릿 문구 정정.

★ 팀 메일박스 + claim 모델 전환 (P0+P1+P2 완료, 2026-06-27)
- ★사용자 요청: 워커→개별워커 inbox를 팀 메일박스+claim으로. 발신=팀소속, 팀 inbox에 쌓임, 각 워커가 자기팀 inbox 확인→자기할당이면 claim. + 팀 오케스트레이터가 보고 할당.
- ★P0(발행버그 수정): adapters.inbox_post가 post에 --as(read/ack 전용)를 넘겨 발행이 깨져 있던 것을 --from으로 교정. 실측 재현 확인(unrecognized arguments: --as).
- ★P1(team_inbox.py 팀메일박스+claim): load_subteams·team_of·is_team / post --to-team(팀당 1부, sender_team·to_team·claimed_by 필드) / claim(os.replace 원자성, 경합 시 1명만 성공) / read --team(unclaimed/claimed/consumed 상태구분) / ack --team(claimed→consumed). 개인 inbox 병행 유지(무이동 마이그레이션). CLI: post --to-team, read/ack --team, 신규 claim 서브커맨드.
- ★P2(승격기 동시패치 — 신호 붕괴 방지): inbox_edges가 팀 메시지를 워커 엣지로 정확 해석 — claim 전엔 팀멤버 fan-out, claim 후엔 claimed_by 단일. 팀명(to_team)이 엣지 오염 안 되게 is_team_name으로 skip. classify_edge INTER/INTRA 정확 보존. detect_team_promotions.py만 수정(워커 승격기 R2 불변).
- ★검증: claim 경합 3명→1명만(원자성)·전체 사이클(post→read→claim→ack) 동작·팀메시지 워커엣지 정확(팀명 오염0)·라이브 신호 3/4/1 유지·team-inbox 24 pass·대시보드 24 pass(P0 회귀테스트 포함)·R2 PASS.
- ★정형 액션 버튼(이미 modals.py 커밋됨, 사용자 추가): [inbox 확인·처리][리마인더 확인] — 팀 채운 프리셋을 headless 워커에 전송. 이제 P1 CLI(--to-team·claim)가 들어와 inbox 프리셋이 의미대로 동작 가능.
- ✅ 다음 통합설계(3종)=완료(위 ★★ 항목 참조). 자율 L1 구현(L3 4가드는 범위밖). 남은 대시보드 P3(claim 컬럼·팀 배지)·P4(action_instruct_team)는 미구현(별도).

★ 대시보드 UI 점검·개선 (2026-06-27, tools/umc-dashboard Textual TUI)
- ★점검(워크플로우 코드실측): 사용자 제안 (1)inbox→칸반 승격 (2)자원 게이지 스트립 + "실제 한도자원이 뭐냐" 질문.
- ★핵심 발견: 진짜 한도 자원 거의 없음 — session_pool 동시성 한도 0(무한)·tmux 한도 0·토큰예산 추적 0. inbox '/200'은 store.load_inbox 표시 cap이지 저장한도 아님(실제 522건). 사용자 추정(동시슬롯8·tmux0/4·inbox/200)이 코드와 불일치. 진짜 부하신호=워커별 미소비 inbox 깊이(이미 agent_grid 배지 구현됨).
- ★칸반 실현가능성=불가(휴리스틱): inbox subject 100% [태그]시작이나 태그 246종(172종 1회)·발화행위이지 상태아님. 4열 분류 시 45% 미분류+과거사실 '완료' 오판. task-id 없음·reply_to 43%만. → 사용자 결정='칸반 안 만듦'.
- ★사용자 결정: 자원=팀부하 현재량(한도게이지 아님) / 칸반 제외 / 범위=3열 레이아웃+콘솔보존+배지강화+하단 스트립.
- ★구현(4파일): widgets/resource_strip.py 신설(하단 풀폭 팀부하 현재량: 미소비inbox·active세션·미완백로그, '현재량' 라벨로 거짓한도 오해 방지) / app.py 3열 재배치(좌 워커·중앙 백로그+inbox전이·우[후보/WorkerConsole]·하단 스트립, WorkerConsole 보존=headless 지시 유일 출력면) / agent_grid.py 큐깊이 배지 색농도 강화(≤2 노랑/≤5 주황/>5 빨강)+stale정합(8→9워커·analysis 팀라벨 추가) / widgets/__init__.py.
- ★검증: 구문·import OK / Textual run_test headless mount 무오류(전 위젯 쿼리 성공·CSS·refresh_data 통과) / 기존 테스트 22 pass(회귀0) / 실데이터 스트립·배지 결정적 산출(9워커·미소비17·워커별 큐깊이). hook/정책 무관(R2 영향0).
- 미완(범위밖): 칸반 4열은 메시지 스키마에 task_id+transition 신설 전제(team-inbox 변경 큰작업). 2열(미완/완료) 칸반은 Reminders completed로 결정적 가능하나 이번 보류.

★★ analysis 팀 신설 + 팀별 권한 화이트리스트 + guard 보안수정 완료 (2026-06-27, 팀 내부 구조 재설계)
- ★사용자 지시: 각 워커에 접근폴더 권한 지정. scout=article+knowledge / write=research/UMC / data=project/umc+iCloud(umc-compressed-db) / analysis(신설)=project/umc. + review=research/UMC+project/umc(orchestrator 결정).
- ★analysis 팀 신설: causal-analyst(인과추론 전문 에이전트, 1인 팀) 신규 생성. 정보차단 역행추론·ablation의 인과 설계·식별·해석 담당. 경계분할: 재실행·생산=inference-runner(data팀) / 인과설계·해석=causal-analyst / 독립검증=stats-validator. 추후 bayesian/text-analyst 확장 여지.
- ★팀별 권한 화이트리스트(신기능): team-setup.json subteam에 allow_paths 필드 추가 → team_init.py가 BASELINE_ALLOW(루트·스크래치패드·워크플로우산출)+팀 allow_paths를 워커별 agents[name].allow로 전개. guard merged_config가 allow=대체 의미론이라 baseline을 워커마다 박음. defaults.allow=baseline-only(미등록 fail-safe).
- ★guard 보안수정(사용자 결정): #2 fail-closed(미등록/오타/미설정 정체성 → agents 전체 deny 합성 → 워커폴더 차단) + #1 Bash 경로-deny(check_bash_policy에 bash_path_tokens shlex+re.split[=:,]+메타문자strip 경로추출 → deny 대조). #3 대소문자는 범위밖(알려진 잔여, macOS case-insensitive FS).
- ★비대칭 해소(검증 발견 후 보강): 초기엔 '팀 외부경로 path도구만 allow강제'였으나, 검증관이 Bash로 타팀 외부경로 누출(scout가 cat project/umc rc0) 1차증거 재현. 사용자 결정='Bash에서도 강제'. ★allow-side 검사(과차단:/tmp까지 막음)를 폐기하고 **타팀 외부경로를 각 워커 deny에 전개**(team_init _other_team_allow_paths)로 전환 → Read/Edit/Write·Bash 모든 채널 대칭 차단, /tmp 등 무관경로 과차단 0. bash_path_tokens가 ';' 등 메타문자 미분리하던 버그도 수정.
- ★변경: team-setup.json(5팀+allow_paths)·team_init.py(BASELINE_ALLOW·_team_allow_paths·normalize_subteams·build_agent_workspace_policy·add_subteam·build_team_json)·guard_agent_workspace.py(fail-closed+Bash경로)·AGENTS.md. 재생성 산출: team.json(9워커5팀)·agent-workspace.json. 신규: teams/analysis/causal-analyst/.
- ★검증 전수 PASS: 권한격리 23케이스(5팀 외부경로 화이트리스트·iCloud 공백/틸드 매칭·N²격리·baseline)+보안 4벡터 차단(Bash cat/grep/cp peer·미설정/오타/미등록 fail-closed)+정상작업 통과. R2 불변(워커승격기·정책·파생기 git-diff0). 동기화 out_of_sync=[]. 실증: orchestrator(미등록) 세션의 검증 Bash명령이 fail-closed로 차단된 것 자체가 #1/#2 라이브 증명.
- 미완(범위밖): 1.3GB project/umc/data → iCloud umc-compressed-db 데이터 이동(data-engineer 위임, 코드 참조경로 조사 후). #3 대소문자 우회(casefold 수정 보류). 미리알림 umc-analysis 목록 실제 생성(reminders-team-bridge). 거버넌스 승격후보(create-team-agent+team-init+team-inbox) 정리.

★★ C 작업 — 프로젝트-팀 승격 구조 구현 완료 (2026-06-27, 팀 내부 구조 재설계 中)
- 범위: 3계층 설계(company-3tier-architecture.md §2)의 "팀·프로젝트 스킬 승격기 신설" = 마지막 미완 후속작업. 워커 승격기는 불변(R2).
- ★사용자 결정: (1)팀 스킬 트리거='신호만 띄움'(자동저작 없음) (2)부하지표=task-log 레저 (3)범위='세 분기 전체 + 프로젝트 승격기'. + 팀 스킬 정의 보강: "inbox로 연결된 다수 워커 워크플로우 자동승격; inbox 희소 시 ①과부하→신규에이전트 신호 ②쌍집중→경계재조정 신호"로 3분기.
- ★구현(detect_team_promotions.py 확장): 트리거를 task signature→**inbox 핸드오프(from→to, .consumed 포함, recipients fan-out, orchestrator 제외)** 구조로 전환. 계층경계 축(team.json subteams). 5종 신호:
  · team_skill(INTRA ≥2워커 핸드오프) / project_skill(INTER 팀쌍) / new_worker(희소팀+과부하워커, 신호) / rebalance(희소팀+쌍집중, 신호) / team_agent(deprecated 읽기전용).
  · 부하지표 worker_load = tasks건수 + skill이벤트 + signature수(정책 가중). 1인팀(scout)은 floor 단독.
- ★실측 발화(evaluate): team_skill 3(data23/write16/review11) · project_skill 4(review+write78/data+write43/scout+write42/data+review30) · new_worker 1(scout:paper-scout load30, solo-overload) · rebalance 0(무손실 대기). 사용자 정의대로 scout(1인 inbox희소)이 정확히 new_worker로 발화.
- ★변경 5파일: .claude/hooks/detect_team_promotions.py(확장)·detect_team_derivations.py(governance fallback 대칭정정)·.project/policies/team-promotion.json(v2)·team-derivation.json(mode라벨)·.project/memory/company-3tier-architecture.md(경로표기 실구현 정정·승격기 구현완료 기록).
- ★부수정합성: governance owner orchestrator(유령)→data-curator 정정 / 유령·오타 shard 3종 삭제(paper-socut·quaility-reviewer·danggeun-scraper, 정보손실0) / stat-claim decision 본문 'root배치'→실배치(워커dir) 정정 / 기존 decision 3건 by=data-curator 보존.
- ★검증(적대적 3검증관 PASS): R2 불변 git-diff 0(hash-object 바이트동일)·사양정합(임계값 정책주입·하드코딩0)·멱등결정성(비결정소스0, _fmt_pairs 2차 tie-breaker 추가로 FS-무관). resolve 멱등(동일 digest 덮어쓰기).
- 남은 후속(범위밖): .project/skills 첫승격시 도입 / orchestrator shard 재발(정체성 export 규율 점검) / create-team-agent 템플릿 문구 / 임계값 누적시 재튜닝.

★ 거버넌스 전면 점검 완료 (2026-06-26 ~22:00, 사용자 지시 '각 워커 내부 스킬·에이전트·메모리 전반 점검, tmux 활용')
- 방식: 8 peer tmux 윈도우(0:2~0:9) 시차 분배·자가점검 → inbox 회신 취합 → owner(data-curator) 실행.
- ★스킬 분배 불정합 8건 교정(역할정합화, orchestrator 직접 ls -la 최종검증·깨진symlink 0):
  · academic-writing → manuscript-writer 추가(집필주체)·steward 유지 / stats-validator·data-engineer·inference-runner 제외(역할교집합0, DE 사용흔적0건).
  · stat-claim-verification → stats-validator 추가(초안저자 복귀)·steward·inference-runner 제거(검증자 단독, 생산/검증 분리).
  · paper-review(신규 root) → quality-reviewer 추가(메타리뷰 독립운영). data-curator 자신은 미수령(QA귀속).
  · 최종: academic-writing={MW,steward} / stat-claim={stats-validator} / paper-review={QA}.
- ★메모리 파생: 스텁 4 peer(stats-validator·QA·data-engineer·inference-runner ~200B) → 전원 4~8KB 도메인지형 파생 완료. MW·steward도 보강. Derive 표시 다수(detect_derivations 후보화 예정).
- ★구조 검증: 공유 14종 거버넌스 스킬 전peer symlink 동일(정상)·peer 고유스킬(paper-scout 3·MW build-verify-latex·QA manuscript-review-gate) 정당·팀에이전트 2종(figure-designer·section-writer) 정상·gis-figure-designer는 사용자전역(범위밖).
- 파생 후보(data-curator owner 처리 위임, task#15): (가)scholarly-evidence-search 공유승격 후보(steward 재사용, 일반화 저작 전제·신호누적 대기) (나)DE parquet 인프라스킬 보류(distinct-agent 미충족) (다)team_agent 후보 재거절(동일패턴 기 decline).
- ⚠️ rate limit: QA(0:6) 일시 발생했으나 회복·메모리/용어등록 완료. 다수 peer 동시호출은 여전히 시차 권장.

★ B판 PDF 45쪽 (사용자 직접 작업) — tasks.md 기존 기록(38쪽)과 불일치 해소
- 실측: umc_paper_ko_B.pdf 45쪽, parts_ko_B/ part파일 19:03 갱신. 38쪽→45쪽 변화는 사용자 직접 작업분(맥락 미상, 추측 금지).
- 거버넌스 점검은 이 PDF 변경과 독립(원고 본문 미접촉). 본문 후속작업은 사용자 맥락 확인 후.

목표(2026-06-26 사용자 결정으로 분기):
- ★주 목표 = **umc-학위논문** (.project/goals/umc-학위논문.json): B판을 석사 학위논문으로. paper-scout 6가지 논증으로 CR 이론장 구축. 이번 학기말(2026 가을~12월) 심사.
- 부 목표 = umc-논문화(SSCI 투고): 별개 목표로 보존, 우선순위 후순위.
- B판 = parts_ko_B/, umc_paper_ko_B.tex (에이전트 역행추론·정책검증판). A판(parts_ko/)은 보류.

★ 현재 국면 — 6가지 논증 정의 대기 + B판 학위논문 재편 (2026-06-26)
- paper-scout에 'paper-scout의 6가지 논증 구조' 정의 조회함(inbox 3a61d318). 회신 오면 B판 이론장 배치로 분해.
  · 주의: .project/memory의 '(2)진짜 한계 6종'(선택편향·SKT대리·낮은ICC·동일출처제외·비대표성·min-max비판단)은 한계지 이론논증이 아님 → 별개. 추측 금지, 회신 확인 후 진행.
- umc-학위논문 목표 3 task 분해(.project/goals): ①6가지논증 이론장 배치(paper-scout, 정의 대기) ②학위논문 체재 전섹션 완성(manuscript-writer) ③지도교수 리뷰(manuscript-writer).

다음 단계(석사·학기말 기준 — 미리알림 umc 목록에 due 등록):
- 6/27: 사용자 두 PDF 검토(B 주력 확정)
- ~6/30: paper-scout 6가지 논증 회신 → B판 이론장 배치 분해
- 7월: B판 학위논문 체재 재편·전 섹션 + 측정이론 인용 보강
- 학기 중반~말: 지도교수 리뷰 반복 → 심사

[이력] CR 두 버전(A/B) 초안 완성·검증 (2026-06-26)
- A판(umc_paper_ko.pdf 26쪽): 에이전트=측정기, 역행추론=연구자, 방법론기여 종착.
- B판(umc_paper_ko_B.pdf 27쪽): 에이전트=역행추론자, Bayesian 다층증거 통합, 잠재기제 가설, 정책검증 종착(사용자 흐름도).
- 검증(orchestrator 직접): 양판 xelatex PASS·undefined 0·수치 보존·A/B 미혼합·active inference 0. 옛 정책판 잔재는 .context/_attic_old_policy_drafts/ 격리.
- 단일 기준: research/UMC/.context/cr-theory-building-remap-design.md
- 사용자 결정: 한국어판만 / 분석 재해석 허용 / 정책 서사 대부분 제거 / 분량 압축 보류 / 기존 영문판 폐기 / 두 버전 작성 → B 주력.

조직 변경 (2026-06-26 사용자 지시):
- ★로스터: danggeun-scraper 삭제(폴더·inbox는 .attic_removed_agents/로 격리, 산출물 보존) / manuscript-steward 신설. team-setup.json→team-init 재생성(작업경계 article 보존·형제격리 8개 정합).
- manuscript-steward 역할 = 논문 본문 글 일관성 자원: 개념어 용어사전·표기규약 / 본문 그림 추가·제거·배치 일관성(★data-curator에서 이관) / 구조·용어·작성방식 귀속. 집필=writer, 일관성=steward. 용어 대안탐색은 PS 요청.
- 지도교수 리뷰본 → QA(quality-reviewer)로 재배선 + QA 산하 '논문 평가 지표 구축' 분화.
- Task#2(체재 전섹션) 분해: (a)전체 글단위 논리구조 (b)개별 문장 빈도·표현 → MW. MW에 이전 컨텍스트(영문화 용어표·6병렬) 활용한 작성 워크플로우 체계화 요청(inbox 8290b775).
- steward 부트스트랩 발송(inbox d0175a38): 용어사전 초안 + 그림 일관성 현황.

umc-학위논문 task 현황(.project/tasks): 6가지논증 이론장배치(PS,정의대기) / 학위논문 체재 전섹션(MW) / 논리구조관리(MW) / 문장표현관리(MW) / 논문평가지표 구축(QA) / 지도교수리뷰 QA관리(QA).

★ 30분 자율 진행 결과 (2026-06-26 ~12:03):
- 4 peer tmux 기동(0:3 PS·0:4 MW·0:6 QA·0:9 steward[구 zsh 재사용]). 4라운드 폴링·조정.
- ★'6가지 논증 구조' = Research_Map 6단계(한계 6종과 별개) 확정. PS가 6단계×B판 섹션 배치표 .project/memory 파생(key=research-map-6-step-argument-x-bpan-sections, 파일:줄+인용+PASS/PARTIAL 판정). B판 사슬과 1:1 정합.
  · 6단계: 1연구문제→서론 / 2메타이론CR→2장 / 3HLM=actual→3장 / 4LLM에이전트=잠재구조 측정도구→3장 / 5질양증거 Bayesian통합→Methods / 6역행추론(retroduction)→Methods·종합.
- ★T1 용어 정본 잠정결정: '잠재기제' 정본, 2장 첫등장만 '생성기제(generative mechanism)' 병기. steward glossary 확정·15곳 교정위치 확보(사용자 최종확인 시 저비용 번복). 잠재상태(측정)≠잠재기제(역행추론) 경계 보존.
- ★P0 인용갭 해소: PS가 신규 ref 5건 Crossref검증 발굴 — bollen1991·flake2017(측정이론, 단계4 핵심)·spiegelhalter2003·ades2006(Bayesian통합 단계5)·danermark2019(메타이론 단계2). 전건 refs.bib 미중복. 단계6 전방향/순차 추론양식 정전=미확보 정직표기.
- MW: 거시 1회전 선행진단 완료(A판 오염 0·약한고리 2건). 현재 [GO] 통합 실행 중(ref5등록+거시본실행+T1교정+빌드).
- steward: glossary-B 정본·그림 일관성 현황(고아 figures_main.tex R1→data-curator 조율요청).
- QA: R7 영문판 검수→학위논문 기준 재정렬 지시함(SSCR 한도 폐기).

★ 2차 자율 진행(20분, ~12:28) 결과 — B판 학위논문 1사이클 완결:
- 사용자: 1단 확정, 나머지 orchestrator 판단 위임.
- ★학위논문 양식 확정·적용: (1)1단(\documentclass[11pt]{article}, A판 2단은 불변) (2)국문초록 별도페이지·분량자유 (3)저자/심사위원=placeholder(제출직전 보류) (4)natbib 유지 (5)잠재기제(generative mechanism) 원어병기 3곳.
- ★인용 갭 전건 해소: refs.bib 72→78엔트리(+6). 신규 6키 전건 .aux 인용·서지 Crossref검증: bollen1991·flake2017(측정이론 단계4)·spiegelhalter2003·ades2006(Bayesian통합 단계5)·danermark2019(메타이론 단계2, 2판)·collier2011(process tracing 단계6 순차양식). 단계6 전방향양식=미확보 정직표기(설계명명 서술).
- ★거시+미시+체재변환+인용보강 1사이클 완결. T1 생성기제0/잠재기제 통일. T3(서론 단계E 명시)·T5(정책잔재0). 거시보강(2장 도입연결).
- B판 최종: umc_paper_ko_B.tex 1단·xelatex PASS·undefined0·38쪽·수치 전건보존(0.279/0.695/ICC0.49/223/772).
- ack 메커니즘 교훈: ack --id는 파일명 전체(<ts>__<from>__<랜덤>) 사용해야 consumed 이동. 부분 id면 재출현.

★ 3차 추가 진행(~14:13) 결과:
- ★미시 1회전 완료(MW): '곧' 26→11회(의미별 분산, 기계치환 회피)·'바로' 강조 인플레 해소·'~데 있다' 인접만 변주(과교정 회피)·T1 잔여이슈A(ch2:9 병기중복 제거, 최종 원어병기 2곳). 수치·\ref·\citep·신규6키 전건 보존. 빌드 PASS 38쪽 undefined0.
- ★그림 정리 완료(data-curator): 고아 figures_main.tex + 구버전(image2/10)·미참조(image1/3/4/5/13) figures/_attic 격리(삭제 아님·MANIFEST+복원명령). 정본 10개 보존. image10 오격리 방지 확인. B판 38쪽 영향0.
- ⚠️ QA 1차 심사평가 미완: API rate limit + tool call 미완성 반복으로 QA 세션이 평가 완료 못 함($52대 정체). 평가지표 체크리스트·B판 평가는 다음 세션으로 이월.
- rate limit 교훈: 다수 peer 동시 LLM 호출 시 계정 rate limit 발생. 재개는 시차/순차로.

★ 4차 자동 진행(~14:42): QA 1차 게이트 통과.
- ★B판 QA 1차 심사평가 = 5축(6단계배치·사슬일관성·한계정직성·측정≠기제경계·인용충실성) 모두 PASS·차단 미흡 0건(학위논문 심사 가능 수준). 축4(측정/기제 경계)=PASS모범. .project/memory: bpan-thesis-qa-gate-1차평가(by QA, orchestrator 화면채록 보존 — QA inbox post가 tool오류 미전송).
- umc-학위논문 '논문 평가지표 구축' task=done.
- P1 권고 2건(차단아님): (a)에이전트 3추론양식 근거 1구절씩 보강 → MW 위임함(전방향=미확보 정직표기) (b)국문초록 기관규격=사용자 양식대기.
- ★기술이슈: QA(0:6) 세션이 tool call 미완성 반복(컨텍스트 47%, 응답 잘림). 평가는 화면채록으로 보존했으나, QA 세션은 재시작 권장. rate limit과 별개 문제.

★★ B판 학위논문 1차 안정화 도달 (2026-06-26 ~14:47):
- P1-a 보강 완료(MW): 단계B 3추론양식 근거 1구절씩(귀추=schurz2008+danermark2019·순차=collier2011·전방향=인용없이 설계명명 정직서술). danermark 2판 정합. 빌드 PASS 38쪽 undefined0. 전방향 인용0 확인.
- ▶현 B판 상태: 1단 38쪽·xelatex PASS·undefined0·refs 78엔트리(신규6키)·잠재기제 정본 통일·6단계 논증 배치·미시 다듬기·그림 정본화·QA 5축 PASS·P1 권고 반영. 본문 1차 안정화.

남은 작업(★대부분 사용자 결정 의존):
- ★사용자 결정 대기: (1)국문초록 기관규격 (2)저자 실명·심사위원 블록(제출직전) (3)T1 정본 최종확인('잠재기제' 잠정, 번복 저비용). → 체재변환 §5(국문초록)·제출판은 이것 확정 후.
- 지도교수 리뷰 도착 시 QA 2차 추적(task 잔존).
- QA(0:6) 세션 tool call 미완성 이슈 → 재시작 권장(평가 산출은 .project/memory 보존됨).
- 팀 word.json 미존재 — 용어 팀사전 이관 시 경로·소유 확인.
- 팀 word.json 미존재(.project symlink 없음) — 용어 팀사전 이관 시 경로·소유 확인(owner=data-curator).
- ★사용자 결정 대기: T1 정본 최종확인('잠재기제' 잠정, 번복 저비용)·저자 실명/심사위원 블록(제출직전).
- 이전 SSCI/영문 트랙: 폐기·후순위. 로그: agents/orchestrator/.context/handoff/tasks-pre-CR-transition-2026-06-26.md
