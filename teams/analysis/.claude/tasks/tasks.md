# analysis 팀 보드

> analysis-lead(orchestrator)가 받은 편지함을 분류해 워커 섹션으로 배분한다.
> 배분의 실효 전달 채널은 team-inbox(read --team analysis)다. 이 tasks.md는 팀장의 배분·추적 기록이며,
> 워커(causal-analyst)의 read 경계(allow=자기 워커 폴더)에는 포함되지 않으므로 워커는 team-inbox로 수신한다.
> 팀 구성: causal-analyst(인과추론 설계·식별전략·해석), analysis-lead(조율 전담).

---

## causal-analyst

### 작업: A-1 산출물 기반 인과 설계·해석 명세 작성

## 상태
진행 중 (초안 v0.1 선제 산출 / 입력 산출물 도착 대기)

## 목표
A-1 재실행 산출물(C-E 223건·guard on/off ablation·EB 재실행)에 대한 인과추론 식별전략·estimand·counterfactual 명세와 인과효과 해석을 작성하고 stats-validator 독립 검증으로 인계한다.

## 배경
받은 편지함 보고 2건(01782572324636219000, 01782572416373210000) → 무할당 확인. 역할 경계상 후속은 A-1 산출물 기반 인과 설계·해석. causal-analyst가 입력 도착 전 작성 가능한 설계 골격을 선제 산출(초안 v0.1, msgid 01782572774579600000)하고 정식 할당을 요청 → 본 작업으로 확정.

## 입력
- causal-analyst 선제 산출 초안 v0.1: (causal-analyst 워크스페이스) .context/handoff/a1-guard-ablation-causal-design-draft-2026-06-28.md
- (대기 중) inference-runner A-1 산출물 — .project/tasks 의 a-1-재실행 작업(assignee=inference-runner, status=pending)

## 기대 산출물
- Estimand 명세: ATT_proc(장치 처치효과, within-item) tau_i = Y_i(guard_on) − Y_i(guard_off), 모표적 E[tau] over 223건 — '기제 인과 발견' 아닌 '정보차단 장치 on→off 절차적 처치효과'로 한정(과대주장 절제)
- 식별전략: within-item(쌍체) 설계로 반사실 근본문제 해소, 입력 이질성·교란 차단
- 식별 가정 5종(A1 장치외불변·A2 SUTVA·A3 확률잡음통제·A4 지표타당도·A5 blind coding)과 위협·완화 표
- 추정: 쌍체 차이 부호검정(Wilcoxon)+반복측정 시 혼합효과. EB 재실행과 estimand 혼동 금지 명시
- inference-runner 인수 체크리스트 5종(223표본·스키마 / guard diff / 시드·온도·모델버전 / case 독립성 / Y1-3 원자료)

## 사용할 스킬
- team-inbox — inference-runner에 인수 체크리스트 전달·산출물 요청, stats-validator에 독립 검증 의뢰

## 필요한 결정
- 초안 v0.1을 정식 산출로 확정(완료). 입력 산출물(A-1) 도착 시 분석계획서로 확정.

## 위험
- 최대 리스크: guard_off가 '장치만' 끄는지(가정 A1) — inference-runner 구현 diff 없이는 보증 불가. → 인수 체크리스트로 등록 시 검증.
- 선행 의존 A-1이 status=pending. estimand 확정 추정은 산출물 등록 후 가능.

## 검증
- 식별전략·estimand 명세가 stats-validator 독립 검증(verdict)을 통과.
- A-1 산출물 등록 시 인수 체크리스트 5종이 충족되는지 대조.

## 완료 기준
- 식별전략·estimand·counterfactual 명세와 인과효과 해석이 작성되고, stats-validator 독립 검증 대상으로 인계됨.

## 다음 조치(analysis-lead)
- inference-runner(data팀)에 인수 체크리스트 5종을 A-1 산출물 등록 시 함께 제공하도록 조정 → 등록 시 즉시 분석계획서 확정.
- A-1이 완료 전환·등록되면 본 작업의 입력 대기 해제를 team-inbox로 알림.
