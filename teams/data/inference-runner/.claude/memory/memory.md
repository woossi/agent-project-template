# Memory — agent: inference-runner

Private working memory (facts this agent learns while working).
Team-wide decisions and goals live in the team store (.team/memory, .team/goals).

## Durable Facts

### 역할 경계 (확정)
- 나 = 분석 파이프라인 **재실행·산출물 생산자**. 산출물의 독립 검증·수치 대조·IRR 설계는 stats-validator, 큐레이션·레지스트리·그림은 data-curator, 원천 압축은 data-engineer 소관. 생산자/검증자 분리로 검증 독립성을 지킨다 — 내가 만든 산출을 내가 PCAR로 검정하지 않는다. <!-- Derive: preference -->

### A-1 재실행 핵심 트리 위치 (재확인됨, 2026-06-26)
- 정본 레시피: `project/umc/analysis/part 3/03_inference` (judgment-synthesizer·guard·config). `data/` 비어 있음(입력·산출 미보존).
- 구버전 입력·산출: `project/umc/analysis/03. Test-for-inference` — `data/preprocessed/stage2_scored.jsonl`(7,137행) 보존.
- EB 사후 소스: `project/umc/analysis/part 3/02_bayesian/output/tables/` — `final_eb_posterior.csv`(scenario==all_weighted 451행)·`final_desert_cells.csv`(6셀).
- 두 트리는 동일 계보(v9-twophase). **접합 = 구버전 입력 + 정본 레시피.**

### ★223 디지털 사막 표본 유실 (최대 발견, R1 치명항목)
- 223 = 디지털 사막 3구(강북·노원·중랑) 게시글. **stage3 층화표집 산출이며 그 ID 목록이 어디에도 보존되지 않음** → 결정론적 재현 불가.
- 검산(추정 금지·실측): stage2 3구=1,144 / stage1 필터통과=753 / by_post 보존=104 — **모두 ≠223**.
- `data/sampled/round_*.jsonl` 부재(구버전·정본·git 히스토리 전체). 설계-구현 불일치: CLAUDE.md가 `output/judgments/` 명시하나 폴더 부재.
- **외부 동료평가 3인이 독립적으로 'C4 223건 재현불가'를 치명항목으로 교차확인**(.context/peer-review/meta_review.md). 내 발견이 외부 시각에서도 확정됨.
- 교훈: **확률적 표집 산출은 seed·산출목록을 반드시 영속화**한다(재발방지). <!-- Derive: term: 디지털 사막 -->

### 223 재구성 3안 + 합의 상태
- 안A(753 전수): 표집 비결정성 제거 → R1 완전 결정론·ablation 깨끗. 단 원고 '223' 서사 수정 강제(body_results L77·body_ch4 L25·table_index L48). 비용 3~5배. **나·dc 공동 권고**.
- 안B(seed 재현): 표집 스크립트 부재 → 신규작성+원목록 불일치. 비권장.
- 안C(흔적 복원): 104+round_2prime 교차, 119건 결손. 비권장.
- 안A면 생성주체=나(stage1 필터 재적용), dc는 registry 등재(중복생성 안 함).
- **사용자/orchestrator 결정: A-1 LLM 재실행 GO 보류. 223 처리 방향 미확정.** 게이트 유지·무단 대량 LLM 실행 0. 원고는 §4.3 지지전용 53계열 [불확실]·탐색적 표기로 방어(126/490/156 확정보존).

### guard_typology 작동 메커니즘 (정정 확정)
- PreToolUse(Read) hook. **작동 층위 = 단계 B 가설생성기만**(Reasoner A/B/C). judgment-synthesizer(단계 C–E)는 차단 대상 아님(분류표·EB 정상 사용 = 설계 의도).
- ⇒ "I_R 정보차단" = 정확히는 "단계 B 가설생성기의 정보집합 차단".
- ablation OFF 권고 = **OFF-2(BLOCKED_AGENTS 비움) + OFF-3(단계 B 프롬프트에 EB z_shift·분류표 명시 주입) 병행**. hook만 끄면 단계 B가 그 파일을 Read 안 하면 무효과 → 정보를 실제로 흘려넣어야 ablation 실측됨.

### 산출 스키마 (가설 1행 unnest, 772행 목표)
- 보강 필드: confidence(high/med/low)·layer(local/inst/indiv)는 단계 E LLM 산출(judgment-synthesizer.md 정의 수정 필요), eb_zshift_sign/value는 `final_eb_posterior`(all_weighted) gu×dimension left join, guard_state(ON/OFF) 메타, run_meta(model·temp·seed·timestamp) — R1 재현성.
- judgment-synthesizer 모델 = **claude-opus-4-6** 핀 확정. 재실행 시 시드·온도 고정.

### 개략 비용 (게이트 보고용 1회치)
- 게시글당 ~5.5 LLM 콜 → 223×5.5≈1,230콜/구성. 1구성≈$30(캐싱 미적용 상한). A-1 전체(ON+OFF+여유)≈$90(상한$120, 캐싱 시 ~$50). 소요 반나절~1일. **최대 리스크는 비용 아닌 223 유실.**

### 거버넌스 점검 (2026-06-26)
- 보유 스킬 academic-writing·stat-claim-verification 둘 다 **재실행 생산자 역할에 부적합 → orchestrator에 제거 요청**. stat-claim-verification은 stats-validator 1차 업무(검증자 스킬, 생산/검증 분리 위배). academic-writing은 manuscript-writer 소관 — body_results.tex 영문화는 section-writer 일회성 위임이었음.
