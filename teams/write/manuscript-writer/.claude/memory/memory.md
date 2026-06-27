# Memory — agent: manuscript-writer

Private working memory. Team-wide decisions/goals live in the team store (.team/memory, .team/goals).

## Durable Facts

### G0. 정직성·무손상 가드 (전역 — 집필·수정·재작성에 우선)
근거 없는 생성 금지, 미검증 주장은 불확실 표시(계약). 헤지 감축이 정직성 훼손으로 가지 않게 균형.
- **무손상**: 수치·통계량은 **mc(manuscript-steward) 수치 정본이 단일 출처** — 창작·변형 금지, 의심 시 mc 조회. 정본 문서=`agents/manuscript-steward/.context/numeric-canon-B.md`. 본문 수치를 글 작업 중 임의로 바꾸지 않는다(값은 외우지 않고 정본 참조). 출처부재 수치는 `[불확실]`·임의 기입 금지. 수치 변경 필요 시 sv 검증값을 출처로 받아 mc가 정본화(보관=mc·검증=sv 분리). (team.json 정식 반영 완료, 2026-06-27 사용자 결정.)
- **수치 인용 가드 4건(mc 정본)**: ①댓글 37만/187만(ch4:47)=후속과제 추정치, 분석결과 인용 금지 ②106/13/7 분포=한 실행 결과(식별자 미보존), 확정통계 단정 금지 ③z\_shift는 차원 내 표준화→차원 간 비교 금지, |z|>1.5는 실무 선별기준(통계유의 아님) ④중랑 연결품질 z\_shift는 본문 +1.73(results:114) vs 1.69(results:125) 공존=미확정, 인용 전 mc 조회(sv 검증 중).
- **한계 보존**: 진짜 한계 6종은 §5에 사실로 1회씩 보존(삭제·단정화 금지). 미검증 추정은 hedge, 자료 뒷받침 발견은 단정형.
- **신규 인용**: Crossref verbatim 검증 후만 refs.bib 등록. 게재본 DOI 미확보 키는 본문 미인용(du2023·liang2023).

### W1. 본문 수정 분류 (rework 방지) — 2026-06-26 회고
- **즉시-가능분**(익명화·파일격리·placeholder 제거 등 정합 무관 양식) vs **정합 검토 필요분**(선정기준·표본흐름·수치·논증 구조). 후자는 한 줄짜리라도 그 로직이 걸친 관련 라인 전체를 함께 읽고 정합 확인 전까지 수정 금지.
- 근거: line77 desert를 dc 코드정합 권고만 보고 즉시 수정→qr R1-F1 MAJOR 반려(구로=강건셀 최상위 자기모순)→재수정. **peer "코드 정합" 권고 ≠ "본문 논리 정합"**(line114 동시 확인 시 1회로 종료).

### W2. 미시 다듬기 — 방어적 절제 → 적극적 설계 논리 (사용자 핵심)
`Derive: preference` 과잉 헤지·방어적 항변·메타해명을 적극적 설계 논리로 전환.
- **헤지 정리**: 탐색적/확증적 한정 대폭 감축(실측 26회→3회, 88%↓). 차원별 신뢰도(F1 값=mc 정본 참조)에 표현을 매핑: 고신뢰 차원(예: 안전)=확신 단정, 저신뢰 차원(예: 기기)="해석 제외" 1회. (구체 F1 값은 외우지 않고 mc 정본 조회.)
- **항변 제거**: "CR과 동일하지 않다/절차적 차용" 류 항변 0건·빈자리 미충전. 설계 요구는 **긍정 선언(active)**으로.
- **정의**: 긍정 정의 앞세우고 부정단서 최소 1회.

### S1. manuscript-steward 분업 경계 (독단 금지)
일관성의 *판단·기준*=steward, 글 *생산*=writer. 겹치면 핸드오프, writer 독단 금지.
- **steward(기준)**: 용어 일관성·T1 정본·그림 배치 판단·한국어 口癖 금지목록·학위논문 체재 표준·**수치 정본 보관**(2026-06-27 team.json 정식 반영. mc=보관·일관성, sv=독립 재현 검증으로 분리 확정).
- **writer(집필)**: 句長 분산·상투구 제거·표현 다양화·dash 위반 탐지·hedge 균형·섹션 집필/재작성. **dc**: 그림 생성·파일·공유스킬 governance authoring.
- **T1 대기**: 생성기제(generative mechanism)·잠재기제·잠재상태·잠재구조 구분. 2장=CR 원어 / 3~5장=B판 산출(잠재기제 가설). 의도된 구분 vs 통일 대상은 steward 정본 영역 → 정본 후 일괄. writer 임의 통일 금지.

### B1. B판 학위논문 정체성 — 에이전트 역행추론·정책 검증 종착
B판(`research/UMC/parts_ko_B/`, `umc_paper_ko_B.tex`)은 A판(SSCI 투고본)과 달리 **학위논문(thesis) 체재**. 단일기준=`research/UMC/.context/cr-theory-building-remap-design.md`.
- **위계 사슬(전 섹션 관통)**: CR(존재론)→미관측 잠재기제→행정관측(HLM)≠생활세계(LLM)=괴리→괴리=잠재기제 신호→다층증거 Bayesian 통합→Agent 역행추론→잠재기제 가설→정책 검증. 각 고리는 **앞이 다음을 필연 요구하는 위계**(병렬 나열 금지=사용자 메타지침). 장 매핑: 1=사슬예고+RQ, 2=CR→괴리=신호, 3=측정·통합·역행추론 형식화, 4=행정패턴→괴리→가설, 5=가설→정책검증·이전가능성.
- **주체 일관성(핵심)**: 역행추론 주체=**에이전트**(연구자 아님). "연구자가 역행추론"·"측정에서 멈춘다"(A판)는 오염→교정. A/B 교차오염은 grep 후 **정독 확정**(느슨한 grep 오탐 — body_ch4:6).
- **체재 차이**: 1단·분량한도 자유·국문초록 기관양식·실명/심사위원 블록·참고문헌 기관양식 = **정책 결정 사항**, orchestrator 확정 후 반영.

### B2. 영문화 glossary — BLK-1 단일 기준
`agents/manuscript-writer/.context/glossary-en.md`가 공통본문·frontmatter 영문화 단일기준. 모든 section-writer 위임이 준수.
- **절대보존 6규칙**: \label·\ref·인용키·수식·표 구조 보존(라벨키 변경 금지), 수치 무손상(G0), 산문 내 em/en dash 0(표 `---`·\cmidrule·수식 `--`는 유지), AI 口癖 금지(Moreover·delve·pivotal 등), 句長 분산, 관통논리 보존. `Derive: term: z\_shift`(표기 고정, Unicode 첨자 금지).
- **기여 2축**: `Derive: term: information-blocked multi-agent retroduction`(하이픈 고정), `Derive: term: measurement-inference procedure`(A판 제목 핵심어), `Derive: term: Empirical-Bayes shrinkage`.
- **역행추론=retroduction**(retroduce, abduction과 구별). 과대주장 회피(R3): "retroduce/possible/tentative"만, "establish causal/prove" 금지.

### WF1. 6병렬 섹션 작성 — section-writer 위임 패턴
`Derive: preference` 대규모 재작성/영문화는 section-writer 병렬 위임(academic-writing 스킬·glossary 공유).
- **BLK-1**: 공통본문(ch2·model·results·ch4·tables·figures)=1회 처리해 양판 100% 공유(단일소스), 판별 frontmatter만 판별. 6병렬(w1 ch2+ch4/w2 model/w3 results/w4 tables+figures/w5 서론A/w6 서론B), frontmatter는 writer 직접.
- **무결성**: A/B 교차오염 grep diff 점검(input diff=서론 1줄만 정상). 회전 후 변경·미해결을 `.context/handoff/` 기록.
- **섹션 레벨 재편**: \section↔\subsection 승강 시 라벨-레벨 판정(academic-writing SKILL.md:39 — 외부 참조 단위와 라벨 레벨 일치, grep 후 정독).
