# 작업

## 상태
완료 (Task #3 QA 2차 검수기준 선행정비). review-lead 할당(msg 01782563163424536000) claim·처리·회신·ack 완료. 산출=/Users/ujunbin/research/UMC/.context/revision-plan/qa-gate-rq-and-claims-2026-06-27.md: (A)RQ1~4 정합성 점검 체크리스트(✅/⛔ 경계 실측 대조) (B)status-of-claims 규율 점검(한정 세종류·단정동사 0건·단계E 상대적설득력) + ★B4 κ↔claim 공유표(stats-validator 핸드오프 중복↓). 본검수 아님 — 재분류 4지표 게이트 통과·v8 확정 후 R<n> 라운드로 실 PASS/FAIL. 다음=게이트통과 통지·입력확정(223 vs 753/1144)·W5 κ 산출 후 본검수 착수.

## 목표
재분류 게이트 통과 전 선행 가능한 QA 점검 '기준'을 정비한다: (1)RQ재구성(RQ1~4) 정합성 점검 체크리스트, (2)status-of-claims 규율(기제확정 금지·상대적설득력 지지전용) 위반 점검 기준. stats-validator(W5 κ)와 공유 문서로 두어 핸드오프 중복을 줄인다.

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
