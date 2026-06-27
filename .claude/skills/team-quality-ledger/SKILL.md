# 스킬: team-quality-ledger

## 사용 시점

팀 오케스트레이터(팀장)가 **자율 할당한 작업의 품질을 추적**하고, **2회 연속 부적절 시 전문화 워커 생성 신호**를 띄워야 할 때 사용한다. 구체적으로:

- 검증팀(원고=quality-reviewer, 데이터/분석=stats-validator)이 산출물에 PASS/PARTIAL/FAIL verdict를 냈을 때 그 결과를 (worker, kind)별로 기록할 때.
- 같은 (worker, kind)에서 **2연속 비-PASS**가 쌓였는지(전문화 워커가 필요한지) 신호를 확인할 때.
- 전문화 워커를 이미 만들었음을 마킹해 중복 생성을 막을 때.

품질을 직접 판정하지 않는다(판정은 검증팀 review-gate가 정본). 이 스킬은 **verdict를 기록·집계·신호화**만 한다.

## 목적

팀장의 자율 운영 루프 중 "할당 → 검증팀 판정 → 카운트 → 2연속 실패 신호"를 결정적으로 굴린다. 사용자 결정(2026-06-27): 품질 평가는 검증팀에 위임, 카운트는 **PASS만 통과·리셋, PARTIAL/FAIL 둘 다 실패**, 자율 수준은 **L1**(신호 후 팀장 판단으로 생성).

## 계약

- 읽는 입력: 검증팀 verdict(team-inbox reply의 `verdict` 필드 또는 직접 전달), 대상 (worker, kind).
- 만드는 출력: 팀장 폴더의 append-only 원장 `teams/<팀>/<팀장>/.context/quality-ledger.jsonl`, 그리고 `signal` 산출(2연속 실패 키 목록 + 권고).
- 쓰면 안 되는 위치: 다른 워커 폴더, 공유 store(원장은 팀장 자기 폴더에만). 워커 생성 자체는 이 스킬이 하지 않는다(create-team-agent가 담당).

## 입력

- `--team` (생략 시 `$CLAUDE_AGENT_NAME`의 소속 팀에서 추론).
- `record`: `--worker --kind --result {pass|partial|fail}` (+ `--work-ref --by --round`).
- `signal`: `--threshold`(기본 2).
- `mark-spawned`: `--worker --kind`.

## 절차

1. **verdict 기록.** 검증팀이 PASS/PARTIAL/FAIL을 내면 `record`로 (worker, kind)에 1줄 append. PARTIAL은 실패로 센다(Q1). by에 검증자(quality-reviewer | stats-validator)를 남긴다.
2. **신호 확인.** `signal`로 2연속 비-PASS 키를 본다. PASS가 끼면 카운터가 리셋되므로 "최근 연속분"만 센다.
   - `recommend: spawn_specialized_worker` — 아직 전문화 워커를 안 만든 키. (다)로 받은 `create-team-agent`로 자기 팀에 워커 생성 검토.
   - `recommend: rebalance` — 이미 한 번 워커를 만든 키가 또 실패. 워커를 더 만들지 말고 **역할 경계 재조정** 검토(detect_team_promotions의 rebalance 신호와 합류).
3. **전문화 워커 생성(L1, 팀장 판단).** 신호를 보고 팀장이 결정하면 `create-team-agent create <새워커> --subteam <자기팀> --role "<실패 kind 전문화>" --requester <팀장>`. 원 워커 role에서 그 kind를 떼어내 역할 중복을 막는다.
4. **마킹.** 생성했으면 `mark-spawned`로 그 (worker, kind)를 표시 — 다음 실패는 spawn이 아니라 rebalance 신호가 된다(anti-thrash).

## 출력 형식

- `record` → `{ok, op:"record", team, result:{worker, kind, result, ...}}`
- `signal` → `{ok, op:"signal", team, result:{signals:[{worker, kind, consecutive_failures, already_spawned, recommend, last_results}]}}`
- 원장은 1줄=1 verdict의 JSONL(append-only, 과거 줄 미수정).

## 내부 자원

- `scripts/quality_ledger.py` — 기록·집계·신호 로직(결정적, 시계 주입 가능). 워커 생성·verdict 판정은 하지 않는다.

## 품질 점검

- 카운트는 PASS에서만 리셋된다(PARTIAL/FAIL 둘 다 실패). 신호는 그 키의 trailing 연속분만 센다.
- 원장은 팀장 자기 폴더에만 쓴다(격리 안전).
- 워커 생성은 이 스킬이 직접 하지 않는다 — 신호만 띄우고 생성은 팀장이 create-team-agent로 한다(L1).
- mark-spawned 이후 같은 키의 신호는 rebalance로 격하된다(무한 생성 방지).

## 자주 발생하는 실패 사례

- **PARTIAL을 통과로 셈** → Q1 위반. PARTIAL은 실패다.
- **신호만 보고 워커를 자동 생성** → L3 무인은 범위 밖. L1: 신호 뜨면 팀장이 확인 후 생성.
- **rebalance 신호인데 워커를 또 생성** → 역할 경계가 틀린 것. 생성 말고 경계 재조정.
- **품질을 팀장이 직접 판정** → 검증 독립성 위반. 판정은 검증팀 review-gate(원고)·stats-validator(데이터/분석)가 한다.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
