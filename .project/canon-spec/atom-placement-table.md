# UMC 최소 단위(원자) 전수 배치표 — 거버넌스 생산 명세 (Canon 확립용)

이 표는 거버넌스 시스템이 `.project/` canon에 **생산·확립해 나갈 목표 데이터 모델**의 전수 명세다. claim·evidence 두 원자 문서의 모든 최소 단위를 한 행씩, **누가 생산·검증·조율하고, 어느 canon 레코드 슬롯에 안착하며, 그 슬롯이 이미 구현됐는지 거버넌스가 앞으로 생산할 미구현 항목인지**까지 추적한다.

**관점(사용자 확정)**: 미구현 슬롯은 "틀린 매핑"이 아니라 **시스템이 생산해 canon에 확립할 작업 항목**이다. 미결정·중복 작업 권한은 시스템 가동 전에 **단일 책임자로 조정**한다.

배치 기준 — 핸드오프 `ADR-canon-unified-2026-06-28.md`(이하 ADR)와 `.project/team.json` 역할. 핵심 원칙: 생산자≠검증자(검증 독립성), 생산자≠조율자(팀장은 조율만), **구조는 자동·내용은 judgment**(ADR D4, 근거 없는 자동저작 금지), 구조 링크는 guard 결정적 검사.

**열 정의**
- **생산 역할 / 검증 역할 / 조율 매개**: 단일 책임자로 확정. 단일화 못 한 건은 `⚠️미결정`(부록 C에 조정안).
- **대응 canon 슬롯**: `.project/{claims,numbers,provenance,lit_props}` 4레코드 중 실제(또는 목표) 슬롯. `↔`/`→`는 그래프 엣지.
- **확립 상태**: `✅구현`=현 canon 스키마에 슬롯 실재(슬라이스 0~2 완료) · `🔲S3`~`🔲S6`=거버넌스가 해당 슬라이스에서 생산할 미구현 슬롯 · `🔲설계`=ADR 설계만(슬라이스 미배정).
- **그래프 분류** (노드/엣지 측면 — Canon 그래프에서의 역할): 원자를 4값으로 분류한다.
  - **NODE** = 노드 식별자. 레코드를 그래프 노드로 만드는 키(`*_id`). guard가 ID 충돌·prefix를 결정적 검사. (4개: claim/number/figure/lit_prop)
  - **EDGE** = 외래참조 간선. 한 노드가 다른 노드(또는 외부 SSOT)를 가리키는 링크. guard가 dangling·deprecated 참조 검사. ADR 강제 간선 3종(claim→number, number→provenance, provenance→claim) + 설계 간선(→lit_prop, →refs.bib).
  - **PROP-j** = judgment 속성. 노드 내부의 내용 값(검증자가 확정, 자동저작 금지 D4). 그래프에서 노드의 검증 대상 속성.
  - **PROP-s** = 구조적 속성. 결정적 값(위치 문자열·사람 이름·상태 등)이라 guard/MS가 형식·일관성 검사하나, 다른 노드를 가리키는 간선은 아님.
  - **PROP-j+EDGE** = 값(judgment 속성)이면서 동시에 다른 노드로의 간선을 동반(예: result_value는 수치 판단이자 `provenance.value→number.value` 간선).

약어 — DE=data-engineer · DC=data-curator · IR=inference-runner · CA=causal-analyst · PS=paper-scout · MW=manuscript-writer · MS=manuscript-steward · SV=stats-validator · QR=quality-reviewer · guard=canon_integrity hook. 팀장: data-lead·analysis-lead·write-lead·scout-lead·review-lead. 묶음: C=claim, Ev=evidence공통, N=number, TF=표·그림, TX=텍스트, L=선행연구.

> 실제 구현 스키마 (대조 기준, 2026-06-28 `.project` 실측 — **S3~S7+risks 구현 완료 후 갱신**):
> - `claim`: claim_id·claim·status·evidence[]·counter_evidence[]·used_in[]·owner_team·verified_by·supersedes·by·ts_ns·clarity_checked·note + **components{target,scope,comparison,finding}·role·grounds[]·counter_grounds[]·relations[] (S3 구현, 9건 전부 컴포넌트화).**
> - `number`: number_id·value·label·provenance[]·status·supersedes·checked_by·by·ts_ns·note.
> - `provenance`: artifact_id·artifact_type·value·source_data(→D)·script_or_process·run_id(→RUN)·related_claims[]·risks[]·manuscript_location·checked_by·status·manifest_ref·derived_from(off-graph, S5)·by·ts_ns·note.
> - `lit_prop` (**S4 구현, 4건**): lit_prop_id(LP)·proposition·bibkey(→refs.bib)·role·locator·manuscript_location·argument_step·status·by·ts_ns.
> - `data_registry` (**S6 구현, 3건**): data_id(D)·label·source_type·period·area·manifest_ref·status. `runs` (**S6, 5건**): run_id(RUN)·label·script_or_process·inputs[]·status.
> - `risk` (**잔존 구현, 4건**): risk_id(R)·label·risk_type·severity·related_claims[]·mitigation·status.
> - guard `canon_integrity.py`: 7 kind·grounds/counter_grounds/risks 링크·relations cycle(DAG)·bibkey 외부SSOT·source_data/run_id scalar·derived_from 검사제외·clarity R8/R9/R10 어휘감사. **canon check 0 error/0 warning, 회귀 테스트 182 passed.**

---

| # | 원자 이름 | 묶음 | 생산 역할 | 검증 역할 | 조율 매개 | 대응 canon 슬롯 | 확립 상태 | 그래프 분류 |
|---|---|---|---|---|---|---|---|---|
| 1 | claim_id | C | MW(기입) | guard | 없음 | claim.claim_id | ✅구현 | NODE |
| 2 | 문장 목적 | C | MW | QR | write-lead | claim.components.role(=clarity R3) | 🔲S3 | PROP-j |
| 3 | 대상 유형 | C | MW | QR | write-lead | claim.components.target.type | 🔲S3 | PROP-j |
| 4 | 대상 명칭 | C | MW | QR | write-lead | claim.components.target.text | 🔲S3 | PROP-j |
| 5 | 분석 단위 〔+ Ev.unit_of_analysis〕 | C+Ev | DC(데이터 정의) | SV | data-lead | claim.components.scope.unit ↔ provenance(신설 unit) | 🔲S3·S6 | PROP-j |
| 6 | 분석 수준 | C | MW | SV | write-lead | claim.components.scope.level | 🔲S3 | PROP-j |
| 7 | 대상 범위 | C | MW | QR | write-lead | claim.components.scope.population | 🔲S3 | PROP-j |
| 8 | 제외 범위 | C | DC(표본 제한) | SV | data-lead | claim.components.scope.exclusion ↔ provenance.source_data(D) | 🔲S3·S6 | PROP-j |
| 9 | 자료 출처 〔+ Ev.source_name + N.산출 자료〕 | C+Ev+N | DC(레지스트리) | SV | data-lead | provenance.source_data(→D 레지스트리) | 🔲S6 (현 placeholder D001) | PROP-j |
| 10 | 자료 시점 〔+ Ev.source_year + Ev.target_period + N.산출 연도〕 | C+Ev+N | DC | SV | data-lead | provenance.source_data.period(신설) | 🔲S6 | PROP-j |
| 11 | 공간 단위 | C | DC | SV | data-lead | claim.components.scope.spatial_unit ↔ provenance | 🔲S3·S6 | PROP-j |
| 12 | 측정 문항 | C | DC | SV | data-lead | provenance.script_or_process(측정 절차) | ✅구현(슬롯 존재) | PROP-j |
| 13 | 측정 척도 〔+ Ev.measurement_scale + N.산출 단위 + N.단위〕 | C+Ev+N | DC | SV | data-lead | number.label(단위 포함) / provenance.script_or_process | ✅구현(부분) | PROP-j |
| 14 | 지표 산식 〔+ N.산식〕 | C+N | IR(분석) | SV | analysis-lead | provenance.script_or_process | ✅구현 | PROP-j |
| 15 | 비교 대상 〔+ Ev.comparison_base + N.비교 대상〕 | C+Ev+N | CA(설계) | SV | analysis-lead | claim.components.comparison.baseline | 🔲S3 | PROP-j |
| 16 | 비교 기준 | C | CA(설계) | SV | analysis-lead | claim.components.comparison.criterion | 🔲S3 | PROP-j |
| 17 | 판단 기준 | C | CA(설계) | SV | analysis-lead | claim.components.comparison.threshold | 🔲S3 | PROP-j |
| 18 | 분석 방법 〔+ Ev.method_used〕 | C+Ev | CA(설계)·IR(실행)→**CA 정본** | SV | analysis-lead | provenance.script_or_process / provenance.artifact_type | ✅구현 | PROP-j |
| 19 | 통제 조건 〔+ Ev.control_condition〕 | C+Ev | CA(식별전략) | SV | analysis-lead | provenance.script_or_process(모형 명세) | ✅구현(슬롯) | PROP-j |
| 20 | 모형 조건 | C | CA(식별전략) | SV | analysis-lead | provenance.script_or_process | ✅구현(슬롯) | PROP-j |
| 21 | 결과 유형 | C | IR(생산) | SV | analysis-lead | provenance.artifact_type | ✅구현 | PROP-j |
| 22 | 결과 방향 〔+ Ev.result_direction〕 | C+Ev | IR(생산) | SV | analysis-lead | claim.components.comparison.result | 🔲S3 | PROP-j |
| 23 | 결과 크기 〔+ Ev.result_size + N.값〕 | C+Ev+N | IR(생산) | SV(독립 재현) | analysis-lead | number.value | ✅구현 | PROP-j |
| 24 | 결과 위치 | C | IR(생산) | SV | analysis-lead | provenance.manuscript_location ↔ claim.used_in | ✅구현 | PROP-j |
| 25 | 반복 여부 | C | IR(생산) | SV | analysis-lead | claim.components.finding(반복 기술) ↔ provenance(TX) | 🔲S3 | PROP-j |
| 26 | 결과 강도 | C | IR(생산) | SV | analysis-lead | claim.components.finding.strength | 🔲S3 | PROP-j |
| 27 | 불확실성 〔+ Ev.uncertainty〕 | C+Ev | SV(독립 재현) | SV | review-lead | number(신설 uncertainty 필드) / N001b 패턴 | 🔲S6 (현 별도 N레코드) | PROP-j |
| 28 | 해석 가능 범위 〔+ Ev.interpretive_limit〕 | C+Ev | MW | QR | write-lead | claim(role=interpretation 별도 claim, R3) | ✅구현(별도 claim) | PROP-j |
| 29 | 인과 주장 강도 | C | CA(설계)→**CA 정본**, MW(기술) | SV·QR | analysis-lead | claim.claim 문장 강도(clarity R9) | ✅구현(clarity 감사) | PROP-j |
| 30 | 일반화 가능 범위 | C | MW | QR | write-lead | claim(role=limit 별도 claim) | ✅구현(별도 claim) | PROP-j |
| 31 | 이론적 의미 | C | MW | QR | write-lead | claim(role=interpretation), claim.grounds → lit_prop | 🔲S3·S4 | PROP-j |
| 32 | 실증적 의미 | C | MW | QR | write-lead | claim(role=interpretation) ← evidence | ✅구현(별도 claim) | PROP-j |
| 33 | 정책적 의미 | C | MW | QR | write-lead | claim(role=policy 별도 claim) | ✅구현(별도 claim) | PROP-j |
| 34 | 한계(claim) | C | MW | QR·SV | write-lead | claim(role=limit) / counter_evidence[] | ✅구현 | PROP-j |
| 35 | 심사자 위험 | C | MW·QR→**QR 정본** | QR | write-lead | risks 레지스트리(미신설) ↔ claim.note | 🔲설계(R001 후보) | PROP-j |
| 36 | 판단동사 | C | MW | QR | write-lead | claim.components.finding.closing_verb(clarity R11) | ✅구현(clarity 감사) | PROP-j |
| 37 | evidence_id | Ev | 생산자(DC/IR) 기입 | guard | 없음 | number.number_id(=claim.evidence 원소) | ✅구현 | EDGE |
| 38 | linked_claim_id | Ev | 생산자 기입 | guard | 없음 | provenance.related_claims → claim.claim_id | ✅구현 | EDGE |
| 39 | evidence_role | Ev | MW(역할 배정) | QR | write-lead | provenance.artifact_type / claim.evidence vs counter_evidence | ✅구현(부분) | PROP-j |
| 40 | evidence_type | Ev | 생산자(DC/IR) | SV | data-lead | provenance.artifact_type | ✅구현 | PROP-j |
| 41 | source_status | Ev | DC | SV | data-lead | provenance.status / source_data(D 레지스트리) | 🔲S6 | PROP-j |
| 42 | source_location | Ev | 생산자(DC/IR) | guard·MS | data-lead | provenance.manuscript_location / run_id | ✅구현 | PROP-s |
| 43 | target_object | Ev | DC | SV | data-lead | provenance.source_data(D) | 🔲S6 | PROP-j |
| 44 | target_group | Ev | DC | SV | data-lead | provenance.source_data(D) | 🔲S6 | PROP-j |
| 45 | target_area | Ev | DC | SV | data-lead | provenance.source_data(D) | 🔲S6 | PROP-j |
| 46 | measurement_object | Ev | DC | SV | data-lead | provenance.script_or_process | ✅구현(슬롯) | PROP-j |
| 47 | measurement_operation | Ev | DC | SV | data-lead | provenance.script_or_process | ✅구현(슬롯) | PROP-j |
| 48 | result_value | Ev | IR(생산) | SV(독립 재현) | review-lead | provenance.value → number.value | ✅구현 | PROP-j+EDGE |
| 49 | claim_support_level | Ev | MW(연결 판단) | QR | write-lead | claim.status(draft/supported/verified) | ✅구현 | PROP-j |
| 50 | risk | Ev | QR | QR | review-lead | risks 레지스트리(미신설) | 🔲설계 | PROP-j |
| 51 | citation | Ev | PS(문헌)·MS(본문)→**MS 정본** | MS·guard | write-lead | lit_prop.bibkey / claim.used_in | 🔲S3·S4 | EDGE |
| 52 | number_id | N | IR(기입) | guard | 없음 | number.number_id | ✅구현 | NODE |
| 53 | 수치명 | N | MS(정본 보관) | SV | review-lead | number.label | ✅구현 | PROP-j |
| 54 | 정본 여부 | N | MS(정본 보관) | SV(독립 재현) | review-lead | number.status(active/replaced) | ✅구현 | PROP-j |
| 55 | 표/그림 연결 | N | DC(생성·파일) | MS·guard | data-lead | provenance.artifact_type=figure/table | ✅구현(슬롯) | EDGE |
| 56 | 원고 위치 | N | MS(정본 위치) | MS·guard | write-lead | provenance.manuscript_location | ✅구현 | PROP-s |
| 57 | 검증자 | N | SV(검증 주체) | review-lead(원장) | review-lead | number.checked_by | ✅구현 | PROP-s |
| 58 | figure_id / table_id | TF | DC(생성·파일·레지스트리) | guard | data-lead | provenance.artifact_id(type=figure/table) | ✅구현(슬롯) | NODE |
| 59 | 표시 대상 | TF | DC | SV | data-lead | provenance.value / source_data | ✅구현(부분) | PROP-j |
| 60 | 시각화 방식 | TF | DC | MS(본문 일관성) | data-lead | provenance.script_or_process | ✅구현(슬롯) | PROP-j |
| 61 | 핵심 패턴 | TF | IR(생산) | SV | analysis-lead | provenance.value(요약) → claim.evidence | ✅구현(슬롯) | PROP-j |
| 62 | 예외 사례 | TF | IR(생산) | SV | analysis-lead | claim.counter_evidence | ✅구현(슬롯) | PROP-j |
| 63 | text_source | TX | DC(원천) | SV | data-lead | provenance.source_data(D, type=text) | 🔲S6 | PROP-j |
| 64 | 수집 기간 | TX | DC | SV | data-lead | provenance.source_data.period | 🔲S6 | PROP-j |
| 65 | 수집 공간 | TX | DC | SV | data-lead | provenance.source_data.area | 🔲S6 | PROP-j |
| 66 | 전처리 기준 | TX | IR(파이프라인) | SV(독립 재현) | data-lead | provenance.script_or_process | ✅구현(슬롯) | PROP-j |
| 67 | 분류 기준 | TX | IR(LLM 코딩) | SV(IRR 설계) | review-lead | provenance.script_or_process | ✅구현(슬롯) | PROP-j |
| 68 | 분류자 | TX | IR(코더 명시) | SV | review-lead | provenance.script_or_process / run_id | ✅구현(슬롯) | PROP-s |
| 69 | 검증 방식 | TX | SV(IRR·교차검증 설계) | SV | review-lead | provenance.artifact_type=validation_result | ✅구현 | PROP-j |
| 70 | 분류 결과 | TX | IR(생산) | SV | analysis-lead | provenance.value(type=pipeline_result) | ✅구현 | PROP-j |
| 71 | 반복 패턴 | TX | IR(생산) | SV | analysis-lead | provenance.value → claim.evidence | ✅구현(슬롯) | PROP-j |
| 72 | 대표 사례 | TX | IR(생산) | QR | review-lead | provenance.value(예시) | ✅구현(슬롯) | PROP-j |
| 73 | 오분류 위험 | TX | SV(오분류 평가) | SV·QR | review-lead | provenance.note / risks 레지스트리 | 🔲설계(부분) | PROP-j |
| 74 | literature_id | L | PS(기입) | guard | 없음 | lit_prop.lit_prop_id | 🔲S3·S4 | NODE |
| 75 | 저자 〔+ Ev.source_author〕 | L+Ev | PS | MS(표기 일관성) | scout-lead | lit_prop.bibkey → refs.bib(SSOT) | 🔲S4 (refs.bib 존재) | EDGE |
| 76 | 연도 | L | PS | MS·guard | scout-lead | lit_prop.bibkey → refs.bib | 🔲S4 | EDGE |
| 77 | 문헌 유형 | L | PS | MS | scout-lead | lit_prop.role(theor/method/empir/contrast) | 🔲S3·S4 | PROP-j |
| 78 | 학문 분야 | L | PS | MS | scout-lead | lit_prop(신설 discipline) | 🔲S4 | PROP-j |
| 79 | 연구 대상 | L | PS | MS | scout-lead | lit_prop.proposition(내) | 🔲S4 | PROP-j |
| 80 | 연구 지역 | L | PS | MS | scout-lead | lit_prop.proposition(내) | 🔲S4 | PROP-j |
| 81 | 연구 시기 | L | PS | MS | scout-lead | lit_prop.proposition(내) | 🔲S4 | PROP-j |
| 82 | 핵심 개념 | L | PS(추출) | MS(개념어 정합) | scout-lead | lit_prop.proposition / role=theoretical | 🔲S3·S4 | PROP-j |
| 83 | 이론적 관점 | L | PS | MS·QR | scout-lead | lit_prop.role=theoretical | 🔲S4 | PROP-j |
| 84 | 자료(선행연구의) | L | PS | MS | scout-lead | lit_prop.proposition(내) | 🔲S4 | PROP-j |
| 85 | 방법(선행연구의) | L | PS | MS | scout-lead | lit_prop.role=methodological | 🔲S4 | PROP-j |
| 86 | 핵심 결과 | L | PS | MS·QR | scout-lead | lit_prop.proposition / role=empirical | 🔲S4 | PROP-j |
| 87 | 주장 강도 | L | PS | QR | scout-lead | lit_prop.status(core/supporting/read-only) | 🔲S4 | PROP-j |
| 88 | 본 연구와의 관련성 | L | MW(연결 판단) | QR | write-lead | claim.grounds → lit_prop (relations supported_by_lit) | 🔲S3·S4 | PROP-j+EDGE |
| 89 | 차용 요소 | L | MW(차용 판단) | QR | write-lead | claim.components.*.grounds | 🔲S3 | PROP-j |
| 90 | 다른 점 | L | MW | QR | write-lead | claim.counter_grounds | 🔲S3·S4 | PROP-j |
| 91 | 한계(선행연구) | L | PS | QR | scout-lead | lit_prop.proposition(한계 기술) | 🔲S4 | PROP-j |
| 92 | 인용 위치 | L | MS(본문 연결) | MS·guard | write-lead | lit_prop.manuscript_location ↔ claim.used_in | 🔲S4 | EDGE |

---

## 부록 A — 병합·누락 회계 (요청 (2)·(4)항)

전수 나열 원자 112개 → 동의 원자를 1개 대표 행에만 흡수(이중흡수 0). 표 데이터 행 = 92.

| 대표 행 # | 합쳐진 원자(원래 이름 전부) | 흡수 수 |
|---|---|---|
| 5 | claim.분석 단위 + Ev.unit_of_analysis | 2 |
| 9 | claim.자료 출처 + Ev.source_name + N.산출 자료 | 3 |
| 10 | claim.자료 시점 + Ev.source_year + Ev.target_period + N.산출 연도 | 4 |
| 13 | claim.측정 척도 + Ev.measurement_scale + N.산출 단위 + N.단위 | 4 |
| 14 | claim.지표 산식 + N.산식 | 2 |
| 15 | claim.비교 대상 + Ev.comparison_base + N.비교 대상 | 3 |
| 18 | claim.분석 방법 + Ev.method_used | 2 |
| 19 | claim.통제 조건 + Ev.control_condition | 2 |
| 22 | claim.결과 방향 + Ev.result_direction | 2 |
| 23 | claim.결과 크기 + Ev.result_size + N.값 | 3 |
| 27 | claim.불확실성 + Ev.uncertainty | 2 |
| 28 | claim.해석 가능 범위 + Ev.interpretive_limit | 2 |
| 75 | 선행연구.저자 + Ev.source_author | 2 |

병합 그룹 13 · 참여 원자 33 · 사라진 행 20. 비병합 의도 구분: `Ev.result_value`(행48, 실제 수치)는 N.값/결과크기(행23, 효과 크기)와 의미가 달라 단독 — `provenance.value → number.value` 엣지로 연결. `Ev.source_year`는 행10에만 흡수, 선행연구.연도(행76)는 문헌 고유 원자로 단독.

**검산: 112(전수) = 92(표 행) + 20(흡수). 생산 역할 미정 0. 이중흡수 0.** ✓

---

## 부록 B' — 노드/엣지 그래프 분류 (재검토 결과)

92개 원자를 Canon 그래프 역할로 재분류했다. 집계: **NODE 4 · EDGE 7 · PROP-s 4 · PROP-j+EDGE 2 · PROP-j 75 = 92**. (구 `judgment/구조` 2분류가 노드키·엣지·속성을 뭉개던 것을 4값으로 분해 — 노드/엣지가 그래프 의미론과 1:1 정렬된다.)

### B'-1. 노드 클래스 (4종) — NODE 식별자 원자

| 노드 클래스 | 식별자 원자(행#) | canon 디렉터리 | 확립 상태 | guard 검사 |
|---|---|---|---|---|
| `claim` | claim_id (1) | `.project/claims` (prefix C) | ✅구현 | ID 충돌·prefix |
| `number` | number_id (52) | `.project/numbers` (prefix N) | ✅구현 | ID 충돌·prefix |
| `provenance/figure` | figure_id/table_id (58) | `.project/provenance` (prefix P, artifact_type=figure/table) | ✅구현(슬롯) | ID 충돌·prefix |
| `lit_prop` | literature_id (74) | `.project/lit_props` (prefix LP, **미신설**) | 🔲S3·S4 | (신설 후 적용) |

> 주의: figure/table은 ADR에서 독립 노드가 아니라 `provenance.artifact_type`로 표현된다(보조 노드). evidence_id(행37)는 독립 노드키가 아니라 **claim.evidence[] 간선이 가리키는 number의 키**이므로 NODE가 아니라 EDGE로 재분류했다.

### B'-2. 간선 (7 EDGE + 2 PROP-j+EDGE) — guard 검사 대상

| 간선 원자(행#) | 출발 노드 | 도착 노드 | canon 링크 | 강제 여부 |
|---|---|---|---|---|
| evidence_id (37) | claim | number | `claim.evidence[] → number` | ✅guard 강제(ADR 유형1) |
| linked_claim_id (38) | provenance | claim | `provenance.related_claims[] → claim` | ✅guard 강제 |
| result_value (48, +PROP-j) | provenance | number | `provenance.value → number.value` | ✅guard 강제(number.provenance) |
| 표/그림 연결 (55) | number | provenance/figure | `number → provenance(figure)` | ✅guard 강제(부분) |
| citation (51) | provenance/claim | lit_prop | `→ lit_prop.bibkey` | 🔲설계(미강제) |
| 저자 (75) | lit_prop | refs.bib | `lit_prop.bibkey → refs.bib(외부 SSOT)` | 🔲설계(미강제) |
| 연도 (76) | lit_prop | refs.bib | `lit_prop.bibkey → refs.bib` | 🔲설계(미강제) |
| 인용 위치 (92) | lit_prop | claim | `lit_prop.manuscript_location ↔ claim.used_in` | 🔲설계(미강제) |
| 본 연구와의 관련성 (88, +PROP-j) | claim | lit_prop | `claim.grounds → lit_prop (relations supported_by_lit)` | 🔲설계(미강제) |

- 현재 guard가 실제 강제하는 간선은 **4개**(claim→number, provenance→claim, provenance→number, number→provenance 일부) — ADR F-D1 "강제는 3개 링크"와 정합(result_value는 number.provenance 경로로 흡수).
- 나머지 5개 간선(→lit_prop, →refs.bib, relations)은 lit_prop·grounds·relations 레코드가 0건이라 **설계만**. 거버넌스가 S3·S4에서 생산해야 guard 강제가 가능해진다.
- **relations(claim→claim) 논증 간선은 표에 독립 행이 없다** — depends_on/contrasts_with는 원자 문서의 "최소 단위"가 아니라 claim 간 메타관계라, 행88(supported_by_lit) 외에는 본 배치표 범위 밖이다(ADR §B.3 relations[]에서 별도 관리). 재검토 한계로 명시한다.

### B'-3. 속성 (4 PROP-s + 75 PROP-j)

- **PROP-s(4)**: source_location(42)·원고 위치(56)·검증자(57)·분류자(68). 위치 문자열·사람 이름이라 결정적이지만 간선은 아니다. guard(형식)·MS(일관성)가 검사한다.
- **PROP-j(75)**: 나머지 모든 내용 값. 노드의 검증 대상 속성이며 생산자가 judgment로 채우고 검증자가 확정(자동저작 금지 D4). Canon에서 검증 상태(미검증→불확실 표기) 부착 대상.

### B'-4. 재분류로 바뀐 행 (구 분류 → 신 분류)

| 행# | 원자 | 구 분류 | 신 분류 | 사유 |
|---|---|---|---|---|
| 37 | evidence_id | 구조 | EDGE | 독립 노드키 아님 — claim→number 간선의 끝점 |
| 38 | linked_claim_id | 구조 | EDGE | provenance→claim 간선 |
| 42 | source_location | 구조 | PROP-s | 위치 속성(간선 아님) |
| 48 | result_value | judgment | PROP-j+EDGE | 값+provenance→number 간선 동반 |
| 51 | citation | 구조 | EDGE | →lit_prop 간선 |
| 55 | 표/그림 연결 | 구조 | EDGE | number→figure 간선 |
| 56 | 원고 위치 | 구조 | PROP-s | 위치 속성 |
| 57 | 검증자 | 구조 | PROP-s | 사람 이름 속성 |
| 68 | 분류자 | 구조 | PROP-s | 코더 식별 속성 |
| 75 | 저자 | 구조 | EDGE | bibkey→refs.bib 간선 |
| 76 | 연도 | 구조 | EDGE | bibkey→refs.bib 간선 |
| 88 | 본 연구와의 관련성 | judgment | PROP-j+EDGE | 판단+claim→lit_prop 간선 동반 |
| 92 | 인용 위치 | 구조 | EDGE | lit_prop↔claim 간선 |
| 1·52·58·74 | 각 *_id | 구조 | NODE | 노드 식별자로 명시 |

---

## 부록 B'' — 구성요소 겹침·중복 점검 (스키마 정합 검사)

guard `canon_integrity.py`의 실제 정의 필드와 배치표 슬롯을 자동 대조해, 겹치거나 어긋나는 지점을 확정했다. 두 종류로 나뉜다 — (1) **스키마 어긋남**(배치표 슬롯이 guard 필드와 불일치, 저작 전 정합 필요)과 (2) **의미 중복**(같은 그래프 간선/값을 두 슬롯이 표현).

### B''-1. 스키마 어긋남 → COMP_SCHEMA 보강으로 해소(완료)

배치표가 명시했으나 워크플로우 초안 COMP_SCHEMA에 없던 components 하위 슬롯 6개를 추가해 정합시켰다(저작 레코드가 배치표와 분리되지 않도록).

| 행# | 배치표 슬롯 | 초안 누락 | 조치 |
|---|---|---|---|
| 5 | claim.components.scope.unit | 없음(spatial_unit만) | `scope.unit` 추가 |
| 6 | claim.components.scope.level | 없음 | `scope.level` 추가 |
| 8 | claim.components.scope.exclusion | 없음 | `scope.exclusion` 추가 |
| 17 | claim.components.comparison.threshold | 없음 | `comparison.threshold` 추가 |
| 26 | claim.components.finding.strength | 없음 | `finding.strength` 추가 |
| 25·89 | finding / components.(불완전 표기) | — | finding.text로 안착(반복 여부 포함) |

### B''-2. 표기 오류 → 정정(완료)

| 행# | 오류 | 정정 |
|---|---|---|
| 31 | `lit_prop.grounds`(grounds는 claim 필드이지 lit_prop 필드 아님) | `claim.grounds → lit_prop`로 정정 |

### B''-3. 의미 중복 — 같은 간선/값을 두 슬롯이 표현 (설계상 의도, 단일 정본 지정)

진짜 "겹침"은 아래 4건이다. 모두 **중복 저장이 아니라 단일 정본 + 파생 표시**로 해소한다(ADR D2 "인덱스=fold 파생", 동기화 부채 0).

| 겹치는 슬롯 | 겹침 내용 | 단일 정본 결정 |
|---|---|---|
| 행88 `claim.grounds`(EDGE) ↔ `relations.supported_by_lit` | 둘 다 claim→lit_prop 간선 | **grounds가 정본.** relations에는 claim→claim만 저장(supported_by_lit는 grounds의 fold 표시로만). 워크플로우 프롬프트에 강제 반영. |
| 행31 이론적 의미 ↔ 행88 관련성 | 둘 다 grounds를 통한 lit_prop 연결 | grounds 슬롯 1개가 정본. 행31은 그 grounds의 *의미 해석*(claim 본문), 행88은 *연결 사실*(grounds 엣지) — 역할 분리(분리되어 중복 아님). |
| 행48 result_value ↔ 행23 결과 크기/N.값 | 둘 다 수치 | **이미 분리됨**(부록 A): result_value=provenance.value(실제값), 결과크기=number.value(효과크기). `provenance.value → number.value` 간선. |
| 행9·10·13·15(병합행) ↔ number/provenance 동의 원자 | claim·Ev·N 3중 동의 | **부록 A 병합으로 1행화**(이미 처리). canon에선 provenance/number 슬롯 1개가 정본, claim은 fold 참조. |

### B''-4. guard 필드 ↔ 배치표 노드 클래스 정합 (확인)

guard에 실제 정의된 7개 노드 kind와 배치표 노드 클래스의 대응 — 모두 정합한다.

| guard kind (prefix) | 배치표 대응 | 정합 |
|---|---|---|
| claim (C) | 행1 claim_id, components 슬롯 | ✅ |
| number (N) | 행52 number_id | ✅ |
| provenance (P) | 행38·58 (figure/table은 artifact_type로 흡수) | ✅ |
| lit_prop (LP) | 행74 literature_id | ✅ |
| data_registry (D) | 행9·43~45·63~65 source_data 대상 | ✅ (S6 신설) |
| runs (RUN) | 행42·68 run_id 대상 | ✅ (S6 신설) |
| risk (R) | 행35·50·73 | ✅ (잔존 신설) |

**결론**: 배치표 구성요소와 guard 스키마 사이의 겹침은 (1)스키마 어긋남 6건 → COMP_SCHEMA 보강으로 해소, (2)표기 오류 1건 → 정정, (3)의미 중복 4건 → 단일 정본 + fold 파생으로 해소. 잔여 충돌 0. 노드 클래스 7종 전부 정합.

---

## 부록 B — 확립 상태 집계 (거버넌스가 생산할 작업량)

| 확립 상태 (2026-06-28 **전 슬라이스 구현 완료**) | 행 수 | 비고 |
|---|---|---|
| ✅구현 — 기반(S0~2) | 44 | claims/numbers/provenance 기반 슬롯 |
| ✅구현 — S3(claim 컴포넌트화) | 12 | components 4슬롯+role+grounds, **claim 9건 전부 컴포넌트화** |
| ✅구현 — S4(lit_prop 명제화) | 20 | `.project/lit_props/` 4건(LP001~004), bibkey→refs.bib 검증 |
| ✅구현 — S6(data_registry·runs) | 13 | D001~003·RUN001~005, **placeholder 11건 경고 전부 해소** |
| ✅구현 — risks 레지스트리 | 3 | `.project/risks/` 4건(R001~004), claim 매핑 |

(합 = 44+12+20+13+3 = 92 데이터 행, **전부 ✅구현**. 거버넌스 미생산 = **0**. canon check 0 error/0 warning.)

**실행 결과(ADR §D 슬라이스 로드맵 완수)**: S3(claim 컴포넌트화)·S4(lit_prop)·S5(derived_from+canon_promote)·S6(data_registry/runs)·S7(clarity guard 어휘감사)·잔존(risks) **전부 구현·검증 완료**. guard 회귀 테스트 182 passed. claim 컴포넌트화는 adversarial verify에서 6건 결함(grounds 오정당화·창작 강도/임계값/모집단)을 잡아 재저작·재검증으로 0건까지 수렴.

---

## 부록 C — 미결정·중복 작업 권한 조정 (사용자 지시: 시스템 가동 전 단일화)

요청 (3)항·ADR 역할 분리에 따라 공동 생산/모호 권한을 단일 책임자로 확정했다. 조정 판단과 근거:

| 행# | 원자 | 충돌(초안) | 조정 결정 | 근거 |
|---|---|---|---|---|
| 5,8,9~11,43~45,63~65 | 자료·계보 원자 | DC·IR 공동 생산 | **DC 단독 생산**, IR은 분석 산출만 | data-lead 경계: 큐레이션·레지스트리=DC, 분석 재실행=IR. 자료 정의는 DC. |
| 14,18,21~26,61,62,70~72 | 결과·산식·분류 결과 | IR·DC / IR·CA 혼재 | **IR 단독 생산**(파이프라인 산출), CA는 설계만, DC는 그림 파일만 | ADR: 생산=IR, 인과 설계·해석=CA, 그림 파일=DC. 3자 분리. |
| 15~20,29 | 비교·방법·통제·모형·인과강도 | IR·CA 공동, MW 혼입 | **CA 단독 정본**(식별전략·설계), IR은 실행, MW는 문장 기술만 | ADR §B.3 인과 설계=CA. 행18·29에 "→CA 정본" 명시. |
| 35,50,73 | 심사자 위험·risk·오분류 위험 | MW·QR·SV 혼재 | **QR 단독 정본**(위험 판정), 생산자는 입력 제공 | risks 레지스트리 owner를 QR로. 단 레지스트리 미신설 → 🔲설계. |
| 51,88~90,92 | 인용·관련성·차용·다른점 | PS·MS·MW 혼재 | **citation/인용=MS 정본**(본문 연결), **관련성·차용·다른점=MW**(본 연구 연결 판단), PS는 lit_prop 사실만 | ADR: LP 저작=PS(문헌 충실성), 본문 연결=MS, 차용 판단=MW. 행51에 "→MS 정본". |
| 53,54 | 수치명·정본 여부 | MS·IR·SV 혼재 | **MS 단독 생산**(정본 보관), SV 검증 | ADR: 정본 보관=MS, 독립 검증=SV(N001 레코드 by=MS·checked_by=SV 실측 일치). |

**잔존 미결정(부록 C로 닫지 못함 — owner/사용자 결정 필요, ADR §F와 연동):**
1. **행35·50·73 risks 레지스트리**: owner를 QR로 잡았으나 `.project/risks/` 디렉터리·스키마 미신설. ADR §F 잔존(R001 후보만 존재). → 신설 여부·스키마 결정 필요.
2. **행2 문장 목적의 검증**: clarity R3(한 문장 한 역할)와 동치이므로 검증을 QR로 뒀으나, R8~R11 어휘검사를 guard로 집행(ADR 슬라이스7)하면 일부가 guard 구조 검사로 이동. → 슬라이스7 시 재배치.
3. **행88~90 grounds 축의 생산 주체** (PS 단독 vs MW 매개): ADR §F 질문3과 동일 미해결. 표는 "사실=PS, 본 연구 연결=MW"로 잠정 분리했으나 owner 확정 대기.

**조정 원칙 요약**: ① 자료=DC · 분석 산출=IR · 인과 설계=CA · 문헌 사실=PS · 문장/연결=MW · 정본 보관·본문 일관성=MS. ② 검증은 수치·계량=SV · 의미·정합성=QR · 개념어·인용=MS · 구조=guard. ③ 조율은 팀장이 라우팅만(생산·판정 비소유). ④ 구조 원자는 guard 자동이라 조율 "없음".

---

총 원자 수 **112** = 표 데이터 행 **92** + 병합 흡수 **20**. 그래프 분류: NODE 4 · EDGE 7 · PROP-s 4 · PROP-j+EDGE 2 · PROP-j 75 = 92. **✅구현 92행 · 거버넌스 미생산 0 (S3~S7+risks 전 슬라이스 완수, 2026-06-28).** 생산 역할 미정 0. 이중흡수 0. canon check 0 error/0 warning · guard 회귀 182 passed.
