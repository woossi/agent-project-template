# 작업

team-umc 팀의 현재 작업 패킷입니다. 가장 작은 작업 단위이며, 에이전트가 자동으로 기록·갱신합니다(사용자가 큐레이션하지 않음). 작업 패킷은 현재 상태만 담고, 진행 로그와 handoff는 `.context/`에 둡니다.
작성과 갱신은 `.claude/skills/write-task/SKILL.md`를 따릅니다.

## 현재 작업

상태: 진행 중 (orchestrator — 학위논문(B판) 전환 추적)

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
