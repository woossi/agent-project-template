# 작업

## 상태
완료 (R10: B판 §2.2 선행연구 재작성 — 결함0, §2.2 CLOSE → §2 전체 CLOSE 복원). 축A 일반명제 한정 가드·축B 1:1 동일시 금지 가드 본문 실측 작동, 인용키10 전수 refs.bib, du2023/liang2023 본문·refs 모두 0건 확인. §2(복원)·§3 모두 CLOSE. orchestrator+mw 회신 delivered. 다음=타 장(§1 서론·§4 결과·§5 논의) 학위논문 기준 전수평가 대기.

## 목표
manuscript-writer가 통합한 R&R 신규 참고문헌 10개의 본문 통합을 Q1·정합성 관점에서 독립 검수하고 결과를 통지한다.

## 직전 작업 (1차)
UMC 원고 독립 품질 검수 프레임(review-checklist.md)과 1차 진단(diagnosis-report-v1.md) 산출, 투고차단 4건 통지. 게이트 유지.

## 배경
orchestrator inbox 작업지시: 집필자(manuscript-writer)와 분리된 독립 검수자로서 전 섹션 정합성·완결성, 방법론 기여의 SSCI Q1 정렬, SSCR(SAGE) 투고요건 충족을 판정한다. 집필 금지, 검수의견·체크리스트·재작업지시만 산출.

## 입력
- 원고: /Users/ujunbin/research/UMC/parts/body_*.tex, umc_paper.tex, tables_main.tex, figure_index.md, table_index.md, refs.bib
- 팀 목표: .project/goals/umc-논문화.json
- 투고요건(orchestrator inbox 요약): ≤10,000단어·초록150-200·APA7·double-anonymized·AI공개

## 기대 산출물
- .context/review-checklist.md (게이트 기준 v1)
- .context/diagnosis-report-v1.md (1차 진단+재작업 지시)
- orchestrator·manuscript-writer inbox 완료 통지

## 사용할 스킬
- team-inbox — 받은 편지함 read/ack 및 완료 통지 post

## 사용할 서브에이전트
- (없음)

## 필요한 결정
- SSCR 단어수 산정 기준(표·참고문헌 포함 여부)·AI공개 정확 문구: paper-scout에 저널 원문 재확인 요청
- 실제 사용 AI 모델명: manuscript-writer/data-curator 확정 필요

## 위험
- 본문 단어수는 한글→영문 환산 추정치(약 11,800~15,700단어)로 번역 후 확정 필요(불확실)
- 투고요건 기준이 inbox 요약 근거 — 저널 원문 대조 권장(불확실)

## 검증
- 산출물 2종 .context/ 생성 확인됨
- 인용 30개 전부 refs.bib(51) 정의·깨진 \ref 없음·figure 10종 실재 확인됨
- inbox 통지 delivered(orchestrator, manuscript-writer) 확인됨

## 완료 기준
- 차단 4건(언어/익명화/AI공개/단어수) 및 주의·경미 항목을 우선순위와 함께 진단 리포트에 명시 → 충족
- manuscript-writer 수정 통지 시 review-checklist.md로 재판정(후속)

<!-- component-contract:start -->
## 계약 연계

- 작업은 에이전트가 실행하는 가장 작은 작업 단위이며, 에이전트가 자동으로 기록하고 갱신한다.
- 작업 패킷은 현재 상태(목표, 입력, 검증, 완료 기준)만 담고, 진행 로그와 handoff는 `.context/`에 둔다.
- `사용할 스킬`에는 필요한 능력과 절차를 참조로 적는다. 절차를 복사하지 않는다.
- `사용할 서브에이전트`에는 역할, 담당 범위, handoff 위치를 적는다.
- 결과는 작업의 검증과 완료 기준으로 되돌아온다.
<!-- component-contract:end -->
