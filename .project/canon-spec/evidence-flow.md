# Evidence output hierarchy

상태: 2026-06-28 사용자 결정 반영.

## 원칙

- Worker와 team 단계는 근거 내용을 생성하지 않는다. 사용자 분석에서 나온 근거와 위치, 실행 메타, 검증 상태만 전달한다.
- Worker와 team 단계의 산출은 비정본 packet 또는 handoff다. 최종 구조화 JSON은 project canon에서만 생성한다.
- Project canon JSON은 owner approve 이후에만 작성한다. 자동 승격은 금지한다.
- `number` 클래스는 제거됐다. 근거 노드는 `.project/evidence/*.json`의 `evidence_id`가 정본이다.
- `evidence.derived_from[]`은 evidence 간 파생 계보 엣지다. 이 엣지는 내용 합성이 아니라 기존 evidence ID 사이의 구조 관계만 표현한다.

## 계층

| 계층 | 허용 산출 | 금지 산출 | 책임 |
| --- | --- | --- | --- |
| worker | `teams/<team>/<worker>/.context/evidence-packets/*.md`, 실행 로그, handoff | `.project/evidence/*.json` 직접 작성 | 분석 결과·출처·해시·불확실성 보고 |
| team | `teams/<team>/.context/evidence-candidates/*.md`, `team-quality-ledger` verdict, team-inbox 전달 | project canon JSON 직접 작성 | 팀장이 worker packet을 검수·집계해 owner에게 올림 |
| project | `.project/evidence/*.json`, `.project/provenance/*.json`, `.project/data_registry/*.json`, `.project/runs/*.json` | owner decision 없는 canon write | owner approve 후 최종 정본 작성 |

## 흐름

```text
worker evidence packet
  -> team evidence candidate
  -> review/team verdict
  -> owner approve decision
  -> project canon JSON
  -> canon_integrity check/fold
```

## Worker packet 최소 항목

Worker packet은 Markdown/handoff로 작성한다. canon ID는 제안값으로만 적고, 확정 ID가 아니다.

- `task_ref`
- `worker`
- `source_paths`
- `source_hashes`
- `run_meta`
- `proposed_evidence_label`
- `proposed_provenance_refs`
- `claim_refs`
- `uncertainty`
- `handoff_to`

## Team candidate 최소 항목

- `candidate_ref`
- `owner_team`
- `worker_packet_refs`
- `artifact_refs`
- `quality_gate`
- `verdict`
- `reviewer`
- `proposed_project_target`
- `owner_approval_ref`

## Project final JSON

Project final JSON은 `.project/schema/evidence.schema.json`을 따른다. 시스템은 evidence 내용을 합성하지 않고, 사용자가 입력·등록한 내용과 검증된 구조 링크만 직렬화한다.
