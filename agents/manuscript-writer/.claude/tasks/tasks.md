# 작업

## 상태
진행 중. B판 §2 이론(3대단락)·§3 방법(2대단락) 집필 완료.
- §2 이론적 고찰: 2.1 비판적 실재론·2.2 베이지안-에이전트·2.3 디지털 활용능력 지역적 구조화. 신규4키(lim2025 등) §2.3 통합. fig:cr-strata 그림본체 data-curator 위임 대기.
- §3 분석 방법: 장제목 통합모형→분석방법, 3.1 통합 모형·3.2 분석적 구조 2대단락 재편. §2 위계사슬 정합 재작성(깨진 도입부 정비, eastwood2019 등). 라벨 전부 보존(sec:model·subsec:integrated·subsec:bayesian_method). subsubsec 개명(분석구조→게시글 코딩과 추론 파이프라인).
- 빌드 PASS·undefined0·44쪽. 부록 댕글링참조(subsubsec:ethics) 기수정.
- 기존: ②§4 결과 완료 / ⑤논의 미착수. ★보류: §1 가교6경로 인용삽입·국문초록규격·저자실명·T1.

## 완료 — §2.2 재작성 (선행연구 근거 보강) [2026-06-26]
사용자 지시로 §2.2를 선행연구 근거 논증으로 재작성 완료. paper-scout 신규5키(gill2005·perkins1987·vangrootel2017·tong2024·shi2025) Crossref verbatim 검증 후 refs.bib 등록(87엔트리)+§2.2 통합.
- 축A(베이지안 이질증거 통합): perkins1987·gill2005·vangrootel2017(질양 직접사례, vangrootel=CR직결) + spiegelhalter2003·ades2006(일반명제 한정·보건경제 명시) + raudenbush2002(부분풀링).
- 축B(정보차단 에이전트): tong2024·shi2025 위치짓기(1:1 동일시 금지·신규성 명시). du2023·liang2023 미인용(게재본 DOI 미확보).
- 빌드 PASS·undefined0·45쪽. perkins <> DOI 빌드 무해 확인. du/liang 본문 0건.
- ★재작성 후 qr 재검수 필요(R8 CLOSE는 재작성 전 기준). orchestrator에 qr·steward 라우팅 회신.

## (이전) §2.2 재작성 착수 메모
사용자 지적: 현 §2.2(베이지안-에이전트 추론 방법론)가 선행연구로 쌓은 논증 아님(인용 bhaskar1975·yeung2024 2개뿐, 핵심 두 명제=베이지안 증거통합/정보차단 에이전트 추론에 근거 0).
- paper-scout에 인용 탐색 요청 발신(msgid 01782462696359868000). 2갈래: (A) 베이지안이 양적·질적 이질근거 혼합통합에 쓰인 근거(혼합방법 Bayesian, precision-weighted pooling), (B) 에이전트·LLM 추론·가설생성·멀티에이전트 토론·정보차단 편향완화.
- ★scout 검증 회신 대기 → 회신 즉시 한번에 §2.2 재작성(사용자 확정).
- 재작성 시 동반 교정: steward 발견1 '잠재 기제'(띄움)→'잠재기제'(붙임) §2.2 영역분(ch2:27·29·31). R8/steward가 확인한 과대인용 가드·정직표기·미완성0은 유지.
- 재작성 후 qr 재검수 필요(현 R8 CLOSE는 재작성 전 기준).
- 활용가능 기존키: spiegelhalter2003·ades2006(베이지안 증거통합, 단 보건경제 맥락=단독 과대인용 주의), schurz2008·ritz2020(추론 형식).

## 목표
orchestrator가 '논문 파트별 재작성'을 5섹션으로 분해해 위임. 착수순서(사용자 확정)=방법(①§3 body_model)·결과(②§4 body_results) 먼저. 각 섹션을 section-writer 서브에이전트(academic-writing 스킬)로 한 건씩 방법론 기여 중심 재작성하고, quality-reviewer 독립검수(Q1·정합성·SSCR요건) 통과 + xelatex 다중패스 빌드 수렴(exit0·undefined0)으로 검증한다.

## 배경
전 섹션 초고는 이미 완결도 '상'(diagnosis-parts-status.md). 따라서 백지 재작성이 아니라 정합성 정비·기여 강화·검수 반려 반영 수준. 방법론 기여 두 축(A EB수축 비교 / B 정보차단 멀티에이전트 역행추론)은 §3.3↔§1.4↔§5.3에 이미 정합. ②body_results에는 quality-reviewer 반려(R1-F1 MAJOR: line77 '구로 제외' 자기모순 — 제외사유 데이터로 명시 필요, 도봉 누락사유 추가)를 반드시 반영. §3.4(=4.3) 단계E 지지전용 수치(772→지지126 등)는 출처부재로 [불확실] 유지·임의 수치 기입금지(EA5132EC).

## 입력
- /Users/ujunbin/research/UMC/umc_paper.tex (마스터)
- /Users/ujunbin/research/UMC/parts/{body_front_intro,body_ch2,body_model,body_results,body_ch4}.tex (5개 본문)
- /Users/ujunbin/research/UMC/parts/{figure_index,table_index,citekey_map,_newrefs_map}.md
- /Users/ujunbin/research/UMC/refs.bib, figures/
- .team/inbox 수신 메시지 2건(ack 완료), .team/tasks/ 배정 작업 JSON

## 기대 산출물
- 섹션별 골격·기여 매핑·정합성 검수 노트(.context/handoff/)
- (막힘 해제 후) 섹션별 재작성 계획과 실제 재작성

## 사용할 스킬
- team-inbox: peer 메시지 수신/ack
- set-team-goal(team_goal.py): 작업 상태 갱신(task-status), --store는 서브커맨드 앞 또는 root에서

## 사용할 서브에이전트
- section-writer: 단일 섹션 재작성(격리 컨텍스트, academic-writing 스킬). 한 건씩 위임. 착수순서 ①body_model §3 → ②body_results §4. handoff는 .context/handoff/section-rewrite-*.md

## 필요한 결정
- SSCR 체크리스트 확정 시점·내용(paper-scout 의존) — 미확정
- 결과 4.x 절 번호 표기 정합: 서론은 4.1~4.3로 RQ 대응 안내, 본문 결과 장은 \ref 라벨 사용 — 인쇄 번호 일치 확인 필요(검수 항목)

## 위험
- 체크리스트 미확정 상태에서 재작성을 선행하면 양식 재작업 위험 → 골격·검수까지만 선행
- 근거 없는 내용 생성 금지, 검증 안 된 주장은 불확실 표시(계약 제약)

## 검증
- xelatex 컴파일 통과(그림·표·참조 해소) — 막힘 해제 후
- 전 섹션 초고 완결성·기여 명확성 점검 통과

## 완료 기준
- 5개 섹션 골격·기여 매핑·정합성 검수 노트가 .context/handoff/에 기록되고 위험·결정이 orchestrator에 회신됨
- (Task 2 본체) SSCR 체크리스트 확정 후 섹션별 재작성 완료

<!-- component-contract:start -->
## 계약 연계

- 작업은 에이전트가 실행하는 가장 작은 작업 단위이며, 에이전트가 자동으로 기록하고 갱신한다.
- 작업 패킷은 현재 상태(목표, 입력, 검증, 완료 기준)만 담고, 진행 로그와 handoff는 `.context/`에 둔다.
- `사용할 스킬`에는 필요한 능력과 절차를 참조로 적는다. 절차를 복사하지 않는다.
- `사용할 서브에이전트`에는 역할, 담당 범위, handoff 위치를 적는다.
- 결과는 작업의 검증과 완료 기준으로 되돌아온다.
<!-- component-contract:end -->
