# Memory — agent: stats-validator

Private working memory (facts this agent learns while working).
Team-wide decisions and goals live in the team store (.team/memory, .team/goals).

## Durable Facts

> 방법론 원칙(재현-우선·banker's rounding·임계값 카운트·인접 트리 탐색·역산≠코드확정·3분류)은 `stat-claim-verification` 스킬에 내재화돼 있다. 여기엔 검증으로 *확정된 도메인 지형 사실*만 둔다.

### 산출물 트리 이중구조 (탐색 시 둘 다 본다)
- 분석 산출 계층 = `/Users/ujunbin/project/umc/analysis/part N/...`. 논문화 재현 계층 = `/Users/ujunbin/research/UMC/active_inference/reproduction/`. 둘은 별개 트리다.
- 베타-이항 강건성(B-6)은 `project/umc`에서 "부재"로 오판됐으나 실제론 `research/UMC/active_inference/reproduction/`(zshift_betabinom_fair.py·zshift_sensitivity_summary.txt)에 있었다. 강건성·민감도 등 *논문화 단계 산출*은 후자 트리에 별도 존재한다. "부재" 단정 전 두 트리 모두 확인.

### 확정된 baseline·구조 사실
- EB posterior 정본 = `part 3/02_bayesian/output/tables/final_eb_posterior.csv` = 450행(3시나리오×150셀), 150셀 = 25자치구×6차원(차원당 25셀).
- **baseline 시나리오 = `all_weighted`** ("All weighted candidates"). |z|>1.0/1.5/2.0 임계 카운트 = **54/22/3**으로 tex와 일치 확정. 인접 시나리오 ambiguous_excluded·candidate_count_1은 55/21/4로 다르다 — baseline 혼동 금지.
- "차원별 상위10%(18셀)"의 절사규칙 = **ceil**로만 재현(ceil(2.5)=3×6=18). round/floor/trunc는 전부 12. 단 top-k 산출 코드는 경계 내 부재(수치 역산 확정).

### 미해결 결함 (원고에만 존재, 산출물로 재현 불가)
- **§4.3 126 vs 53 내적 불일치**: 단계E 표·자치구별 지지 = 126(중랑106+강북13+노원7), 차원별·층위별·확신도 분해는 모두 53. 단계E 지지전용 판정 산출물(supported/refuted/undetermined+차원+층위)이 작업 경계 어디에도 없어 53의 정의(126의 어느 부분집합인지) 재현 불가 [불확실]. 126·53·772·490·156은 research/UMC 원고·리포트에만 존재, project/umc 분석 트리엔 0건.
- 외부 행정지표(노인비율 26.03%·기초생활수급률 14.58%·노원 고령 21.43%)는 **UMC 모델 변수(L2 카탈로그 27변수)가 아니다** — 분석 파이프라인 밖 외부 인용이라 자치구별 출처 테이블이 경계 내 부재. aging_rate max=0.2603만 간접 확인됨.

### 검증→톤다운 근거 제공 역할 (1차 검증 위 확장)
- 단순 수치 대조를 넘어 *식별력 경계 판정*까지 수행한다. 판정 프레임 = **3계층 독립 보강**(①단계E 지지건수=텍스트 근거 ②EB z_shift 강건성=집계 근거 ③분류 F1=측정 근거). 셋 다 충족해야 '단정 가능'.
- 자치구 기제 근거두께: 중랑 CQ만 단정 가능(106건·밀도2.12·z=+1.69·F1 0.78). 강북·노원은 차원당 지지 3~4건이라 가설수준. 강북 SAF는 EB·F1 독립보강으로 '준-단정'.
- **과대주장 톤다운 핵심 원칙**: 긍정선언 대상(절차·설계: EB비교·정보차단 멀티에이전트의 *작동*)과 절제 대상(발견 라벨: 인과규명·디지털사막·베이지안 추론 과용의 *증거지위*)은 충돌이 아니라 구분 대상이다. 설계 작동은 단정 유지, 산출의 증거지위는 탐색적으로 절제.

### 안정적 선호·반복 용어
- z_shift = 차원 *내* 표준화 괴리, 통계 유의가 아닌 **실무 선별/우선검토 신호**(본문 자인). 결과 서술에서 "유의" 언어 금지, "우선검토 후보"로 일관. Derive: term: z_shift
- EB 수축(empirical-Bayes shrinkage) = 베이지안 **부분 풀링 사전**(null/ICC를 효과검정이 아닌 정칙화 사전으로 사용). Derive: term: EB 수축
- 검증 리포트는 항상 ✅정합/⚠️불일치/❓출처불확실 3분류로 닫고, 임의 보정 없이 실측 확정·집필자 적용으로 라우팅한다(원고 직접 수정 금지, 대체표현 예시만 제시). Derive: preference
- ICC 0.49% = 자치구 효과를 *보증하지 않는다*. null 모델은 부분풀링 사전으로만 정당하며 결과장 전체에서 '효과' 언어를 회피한다. Derive: term: ICC
