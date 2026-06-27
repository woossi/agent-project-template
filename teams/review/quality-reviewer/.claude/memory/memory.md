# Memory — agent: quality-reviewer

Private working memory (facts this agent learns while working).
Team-wide decisions and goals live in the team store (.team/memory, .team/goals).

## Durable Facts

## 정체성과 역할 경계
독립 품질검수 주체. 집필자(manuscript-writer/section-writer)와 분리된 게이트 운영자다.
검수의견·체크리스트·재작업지시만 산출하고 **원고를 직접 집필·수정하지 않는다**(수정안 예시만 제시, 적용은 집필자).
inbox "적용·보존 완료" 보고는 PASS 근거가 아니라 **검증해야 할 가설**이다 — 산출물(파일·라인·표 셀값)에서 직접 대조해야 PASS.
집필자 핸드오프 로그는 형제폴더 guard로 차단됨(정상). 검증은 작업 경계 내 원고로 한다.
Derive: preference

## 검수 게이트 5축 (manuscript-review-gate 운영 기준)
원고 산출물을 다음 5축으로 PASS/PARTIAL/FAIL/N/A 판정한다(체크리스트 v1, `.context/review-checklist.md`).
- **A 저널 투고요건**(SSCR/SAGE, SSCI Q1): A1 영어·A2 본문 ≤10,000단어·A3 초록 150–200단어·A4 APA7·A5 double-anonymized·A6 AI공개·A7 키워드 3–6·A8 그림표 규격·A9 구조. ★A1(영어)·A3(초록길이)는 **하드 게이트** — 미통과 시 다른 항목 무관하게 자동 FAIL.
- **B 정합성·완결성**: RQ–결과 대응·방법결과 분리·용어/수치 일관·상호참조 무결성·자산 존재·한계 정직성·초록본문 정합·결론의 기여 환원("디지털 결핍 발견"이 아니라 "재현가능한 측정-추론 절차"로 환원).
- **C 방법론 기여 Q1 정렬**: 기여 2축=(가)행정 사전값 대 플랫폼 관측의 EB 수축 비교(측정-기제 이행 조작화) / (나)정보차단형 멀티에이전트 역행추론(확증편향 차단). 심사축=신규성·재현가능성·방법주장정합·강건성·검증가능성·이전가능성·타당도위협대응·SSCR 스코프적합.
- **D 통계·수치**: stats-validator 연계 교차확인. 수치 결함은 **임의 보정 금지** — 실측 확정(stats-validator) 연계 후 집필자 적용.
- **E 관통논리(서술의 지위)**: `.team/memory.md` `manuscript-status-of-claims` 기준. D축(hedge 대상 정합)과 짝.
Derive: term: 검수 게이트 5축

## 핵심 검수 원칙: 단위 전체 수치 무결성 검산
지적·변경된 항목만 보지 말고, 그 항목이 속한 **절·표의 모든 합산 가능 수치를 한 번에 검산**한다(grep 추출 → python3 부분합=총계, 표↔본문↔초록↔그림캡션 일치).
부분합이 총계와 어긋나면 본문이 그 부분합의 정의를 주는지 확인하고, 없으면 결함 기록.
★교훈(R1→R2): R1에서 line77만 보다 R2에서야 53 vs 126 불일치를 발견 — 집필자가 못 본 결함 발견이 검수자의 1차 가치.
Derive: preference

## 관통논리 E축 판정 규칙 (한정·단서의 세 종류)
모든 한정·단서·해명은 세 종류뿐이며 종류마다 올바른 동작이 결정된다(근거: `.team/memory.md` manuscript-status-of-claims).
- **(1) 설계요구**(min-max 상대척도·자치구 단위·정보차단 멀티에이전트·예측오차 우선탐색) → **긍정 선언**이어야 PASS. "X는 차선/대용 아님"식 **부정 경유는 (3) 위장 = 위반**.
- **(2) 데이터 한계**(진짜 한계) → §5에 사실로 **1회** 적시. 삭제·단정화는 **과소=위반(한계 은폐)**.
- **(3) 선제사과 항변**(존재론 동일성 부인·"발견법으로만"·"등가 아님" 반복·"탐색적 윤곽으로만" 반복) → **삭제**돼야 PASS. 같은 항변 2회+ 잔존이면 `R<n>-F` 기록.
★진짜 한계 6종(§5 1회 보존 필수, 사라지면 은폐 FAIL): ①선택편향 비식별성(당근 이용자=디지털 접근가능층) ②단일 통신사(SKT) 대리지표 ③낮은 ICC(0.49%) 2수준 검정력 제약 ④동일출처 오염회피 위한 차원제외 대가 ⑤플랫폼 비대표성(하한값·선택적 증거) ⑥min-max 절대충분성 비판단.
53계열 특례: (3)메타해명("경계 불확실")은 걷되, "53이 불확실하다는 사실"은 (2)이므로 [불확실] 표기 유지(임의 보정 금지). 표 tab:stage_e 126계열 불변이 조건.
Derive: term: 한정의 세 종류

## 라운드 운영과 F-id 체계
재판정은 R<n> 라운드로 누적(현재 R1~R10 완료, `.context/review-checklist.md`). 각 라운드: 직전 F-id close 판정 먼저 → 단위 수치 검산 → 축별 판정 → 새 결함 F-id 부여.
결함 식별자 `R<n>-F<k>`, 등급 MAJOR(재작업 반려)/MINOR(정리 권고). 모든 F-id에 파일·라인·요구사항·수정안 예시.
라우팅: 미리알림 annotate 1줄 + 집필자·orchestrator(수치결함이면 stats-validator) inbox `--reply-to` + 처리 메시지 ack.
주요 결함 이력: R1-F1(line77), R2-F1(§4.3 수치 정합성 공백, 53 vs 126 불일치 — close), R7-F1(A2 단어수 ~2배 초과 투고차단), R7-F2(A3 초록 길이 하드게이트), R9-F1(빌드 PASS여도 PDF 출력오염 — 검수자 직접 발견).
Derive: term: F-id

## 출력 오염 점검 (빌드 PASS ≠ 출력 무결성)
★R9-F1 교훈: LaTeX 빌드가 PASS(undefined 0)여도 PDF 출력물에 마크업 잔존(`</content>` 등)이 살아남을 수 있다.
빌드 통과만으로 출력 무결성을 판정하지 말고, **pdftotext로 실제 출력물을 실측**해 비-LaTeX 마크업·오염 토큰 잔존을 확인한다.
Derive: preference

## 글품질 rubric 4차원 (writing-quality-rubric.md)
문체·수사 품질을 0–2 채점으로 측정(스킬 references/, econ-writing-skill 50+ 가이드 내재화).
- A 구조·수사(주장-우선 문단·기여 위치·문헌 공정성·결론 절제) / B 구체성·정량성(크기 명시·통계 vs 실질유의 구분·능동태·표 자족성) / C AI·상투 문체 탐지(금지어 delve/crucial/robust(통계외)/leverage 등·문장 리듬·구체 제도 디테일) / D 불확실성·정직성.
★D 핵심: **미검증분 hedge 의무(D1, 부재 시 FAIL)** 와 **방어적 과잉 hedge 억제(D2)** 는 충돌이 아니라 **짝**이다 — hedge의 유무가 아니라 **대상의 정합성**을 본다(검증된 사실은 단정, 미검증분은 반드시 hedge). 팀 정책 조정(외부 출처는 hedge 부재를 AI문체로 보지만 본 팀은 미검증분 hedge를 의무로 둠).
Derive: term: 미검증분 hedge 의무

## 외부 동료평가 교차확인 (paper-review 패널, 2026-06-26)
orchestrator가 paper-review로 외부 독립 패널 3인(통계방법론·주장증거정합·alignment-forum) 운영 → **만장일치 Major revision**(`.context/peer-review/`).
내 게이트와 교차된 쟁점(외부 독립 포착으로 타당성 강화): C4 223건 재현불가(=내 R2-F1과 동일 뿌리)·C1 ICC 0.49% 우회논리(평균효과 한계→괴리분석 전환을 '방법론적 회피'로 읽음)·C3 노원구 과대표현(반박108 vs 지지7인데 정책명제 병렬, E축 직결).
★신규 결함(아직 미반영): alfa의 다중비교 보정 전면 부재(HLM·EB·에이전트 단계 Bonferroni/FDR 없음)·C2 LLM 분류 방향성 편향(안전·연결품질 과배정이 핵심 산출 차원과 겹침=분류 아티팩트 가능성).
→ 다음 §1·§4·§5 전수평가 체크리스트에 C1·C2·C3·C4·다중비교보정 항목화(본문이 보류·사용자결정 연동이라 '체크리스트 준비'까지, 실검수는 orchestrator 타이밍 지시).

## 작업 경계와 협업
원고 경로: `/Users/ujunbin/research/UMC/parts/*.tex`·`umc_paper.tex`·`tables_main.tex`·refs.bib. B판=`parts_ko_B/`(석사 학위논문 1단 38쪽).
공유 store(.team/inbox·.team/memory)는 CLI(Bash)로만 접근. 검산은 세션 Bash(grep/python3).
B판 QA 5축 심사(6단계배치·사슬일관성·한계정직성·측정≠기제경계·인용충실성) 1차 = 5축 모두 PASS — `.team/memory.md` `bpan-thesis-qa-gate-1차평가`에 팀 기록 완료.
