# 팀 작업 — review 팀 (보드 정본: review-lead 워크스페이스)

## 상태
진행 중

## 목표
재분류 게이트(분류변화율·검색확장회수율·κ·비용 4지표) 통과 전, 본검수 라운드(R<n>)를 게이트 통과 즉시 무지연 착수하도록 검증·검수 선행 자산을 정비한다. 게이트 통과·v8 산출물 확정·입력확정(223 vs 753/1144)은 review 팀 권한 밖(orchestrator/데이터팀)이며, 통지 수신 시 review-lead가 모아 워커에 전달한다.

## 공통 착수 게이트 (모든 본검수 작업의 선행조건 — 충족 시 review-lead가 통지)
1. 재분류 4지표 게이트 통과 통지(orchestrator)
2. 입력확정(223 vs 753/1144)
3. 코드북 v8 + 03_umc_classified_v8 + 단계E v8 산출물 확정
4. W5 κ/α IRR 산출(stats-validator) — 게이트 (c)κ 지표와 동일 산출

> 현 시점 1·2·3 미충족(v8 산출물 디스크 부재). 따라서 아래 작업은 실측 PASS/FAIL 부여가 아니라 게이트 통과 즉시 적용할 **선행 정비**다.

---

## [stats-validator] T-RV-01 — W5 인간코딩 IRR(κ/α) 산출 프로토콜 선행 설계
- 상태: 진행 중 (배분 통지 발송)
- 목표: 재분류 spec W5(2인 독립 인간코딩·Cohen κ·Krippendorff α·차원별 F1)를 v8 산출물 확정 즉시 무지연 실행하도록, IRR 설계·표본추출·임계·게이트(c)κ 보고 포맷을 사전 고정.
- 배경: W5는 게이트 4지표 중 (c)κ를 산출하는 책임 작업(spec 작업분해 W5 담당=stats-validator). 선행(W1→W2→W4 코드북 v8) 미완으로 실데이터 산출 불가하나, 프로토콜·코드·표본설계·임계규칙은 데이터 독립적으로 선행 가능.
- 입력: `/Users/ujunbin/research/UMC/.context/revision-plan/karrot-reclassification-spec-2026-06-27.md`(§4·§7·W5), `.../qa-gate-rq-and-claims-2026-06-27.md`(κ↔claim 공유표·B4 트리거)
- 기대 산출물: IRR 프로토콜 + 재현 스크립트 골격을 `.context/`에. 포함 — 2인 독립코딩 절차(동일 v8 코드북·맹검), 표본설계(핵심 셀 50~100 + 차원균형 + R2 신규유입 τ보정), Cohen κ(주차원)·Krippendorff α(다중라벨)·차원별 F1(LLM vs 인간합의) 산출식, 성공기준 κ≥0.6 및 κ<0.6 차원 가설강등 규칙, 게이트(c)κ 보고 포맷(공유표 정합).
- 사용할 스킬: stat-claim-verification(검증 절차), team-inbox(완료 시 review-lead/quality-reviewer post 통지).
- 필요한 결정: τ 보정 표본은 W2 산출 의존 → W2 미산출 시 표본설계를 파라미터화(placeholder), 게이트 통과 시 실표본 바인딩.
- 위험: 외부 코더 2인 확보·일정은 review 팀 밖 → 프로토콜은 코더 독립적으로 작성, 확보 책임은 orchestrator 통지에 위임(review-lead 경유).
- 검증: 프로토콜이 spec §4·§7과 1:1 매핑(κ·α·F1·임계·게이트 지표)되는가 / qa-gate κ↔claim 공유표 단일 판정규칙과 충돌 없는가.
- 완료 기준: 프로토콜·스크립트 골격이 `.context/`에 저장 + review-lead/quality-reviewer에 post 통지 + 게이트 통과 시 데이터만 바인딩하면 즉시 산출 가능한 상태.

---

## [quality-reviewer] T-RV-02 — §C 본검수 예약항목 선행 점검 준비
- 상태: 진행 중 (배분 통지 발송)
- 목표: 본검수 §C 예약항목(v8 정합성·재현성 한계 갱신·부록A 재확인)을 게이트 통과 즉시 실행하도록, 점검 체크리스트·대조 대상(파일:줄) 매핑을 사전 고정.
- 배경: quality-reviewer가 Task #3(qa-gate-rq-and-claims 문서) 완료 후 §C 예약점검 준비 상태로 대기 통지(msgid 01782565424633088000). RQ1~4 정합성·status-of-claims 규율은 이미 정비됨 → 다음 단계 §C 3항목 선행 체크리스트화가 선행 가능.
- 입력: `.../qa-gate-rq-and-claims-2026-06-27.md`(§A·§B), `.../revision-plan-2026-06-27.md`(§8·부록A), `.../karrot-reclassification-spec-2026-06-27.md`(v8 명세·재현성 보존규칙)
- 기대 산출물: §C 선행 점검 체크리스트를 `.context/`에. 포함 — (1) v8 정합성: RQ↔v8 산출 정합·✅/⛔ 경계 대조 목록, (2) 재현성 한계 갱신: dbId+원문300자 보존·run.json·codebook_hash·고정설정 점검, (3) 부록A 재확인 항목과 v8 반영 시 갱신 트리거.
- 사용할 스킬: team-quality-ledger(검수 게이트 5축·E축/D축 라우팅), team-inbox(완료 시 review-lead/stats-validator post 통지).
- 필요한 결정: 본검수 아님(prep). 실 PASS/FAIL은 게이트 통과·v8 확정 후 R<n>에서 부여 — 체크리스트는 '검증 대상 가설' 형태(보고를 PASS 근거로 쓰지 않음).
- 위험: v8 미확정으로 파일:줄 실대조 불가 → 대조 대상은 산출물 슬롯으로 명시, 게이트 통과 시 실파일 바인딩.
- 검증: 체크리스트가 qa-gate §A·§B와 중복·충돌 없이 §C 3항목을 빠짐없이 덮는가 / κ↔claim 공유표 단일 판정규칙과 정합한가.
- 완료 기준: §C 선행 체크리스트가 `.context/`에 저장 + review-lead/stats-validator에 post 통지 + 게이트 통과 시 실파일 대조만으로 R<n> 착수 가능한 상태.

---

## 배분 처리 로그 (메일박스 → 보드)
- 입력 메시지 5건(quality-reviewer 3 / stats-validator 2) 모두 "신규 작업 없음·대기" 보고. 공통 결론: 본검수 착수 선행조건(게이트 4건) 미충족.
- 분류: 신규 외부 작업은 없음 → 게이트 미충족 상태에서도 선행 가능한 준비작업 2건(T-RV-01, T-RV-02)을 배분.
- 게이트 충족(통지 1·2·3) 수신 시 review-lead가 모아 워커에 전달하고 본검수 R<n> 라운드를 별도 배분한다.
- handoff/진행 로그는 `.context/`에. 본 보드는 현재 상태만 유지.

<!-- component-contract:start -->
## 계약 연계

- 작업은 에이전트가 실행하는 가장 작은 작업 단위이며, 에이전트가 자동으로 기록하고 갱신한다.
- 작업 패킷은 현재 상태(목표, 입력, 검증, 완료 기준)만 담고, 진행 로그와 handoff는 `.context/`에 둔다.
- `사용할 스킬`에는 필요한 능력과 절차를 참조로 적는다. 절차를 복사하지 않는다.
- `사용할 서브에이전트`에는 역할, 담당 범위, handoff 위치를 적는다.
- 결과는 작업의 검증과 완료 기준으로 되돌아온다.
<!-- component-contract:end -->
