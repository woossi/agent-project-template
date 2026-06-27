# 스킬: team-derive-author

## 사용 시점

`detect_team_derivations.py`가 표면화한 팀 파생 후보(team_term / team_memory)를 **거버넌스 owner가 공유 store에 실제로 기록**해 루프를 닫을 때. 후보 표면화는 탐지기가, 저작은 이 스킬이 담당한다(개별 용어는 `register-term`, 개별 메모리는 `memory.md`).

## 목적

팀 공유 자산을 충돌 없이 저작한다. 가장 위험한 무잠금 writer(`register_term`의 비원자 전체 덮어쓰기)를 **owner 직렬화**로 무력화한다 — `.project/word.json`과 공유 선호는 `governance.authoring_owner` 한 명만 쓰고, 비-owner는 거부되어 inbox 제안으로 유도된다. 단일 작성자라 동시성이 없고, 쓰기는 그래도 atomic(tmp+os.replace)이다. 팀 메모리는 fact당 불변 파일이라 여러 저자도 공유 파일을 손상시키지 않는다.

## 계약

- 읽는 입력: 작성자 정체성(`--by`/`CLAUDE_AGENT_NAME`), 공유 store(`--store`/`CLAUDE_PROJECT_STORE`/`.project`), `governance.authoring_owner`(team-derivation.json).
- 만드는 출력: `.project/word.json`(owner만), `.project/memory/<ns>__<agent>__<slug>.json`(불변) + 렌더된 `.project/memory.md`.
- 쓰면 안 되는 위치: 비-owner는 `.project/word.json`을 쓰지 않는다(거부됨 → inbox 제안). 용어 정의를 추측해 채우지 않는다.

## 입력

- 용어 등록: 4개 필드(`term`/`ko`/`definition`/`use_when`) 모두 — 사용자에게 확인, 추측 금지.
- 메모리 기록: `--key`(안정 키) + `--fact`(팀 결정/사실) [+ `--source`].

## 절차

1. **용어 등록(owner만):**
   ```bash
   CLAUDE_AGENT_NAME=<owner> python scripts/team_derive.py register-term \
     --term "<원어>" --ko "<한국어>" --definition "<정의>" --use-when "<맥락>"
   ```
   비-owner면 거부(종료코드 1)되며 inbox로 owner에게 제안하라는 안내가 나온다.
2. **팀 메모리 기록:**
   ```bash
   python scripts/team_derive.py record-memory --key "<키>" --fact "<팀 결정/사실>" [--source "<출처>"]
   ```
   불변 record 1개 + `.project/memory.md` 자동 렌더.
3. **닫기:** `.claude/hooks/detect_team_derivations.py resolve --kind {term,memory} --key ... --decision promote`.

## 출력 형식

stdout JSON `{ok, op, result}`. 용어는 `.project/word.json`의 `terms[]`에, 메모리는 `.project/memory/`(불변) + `.project/memory.md`(키별 최신 fold).

## 내부 자원

- `scripts/team_derive.py` — `register-term`(owner 직렬화·4필드·중복 차단·atomic), `record-memory`(불변 record), `render-memory`(키별 last-wins fold). owner는 `governance.authoring_owner`(기본 `orchestrator`).
- `scripts/tests/test_team_derive.py` — CI 안전 테스트: 비-owner 거부, 필드 누락/중복 거부, 메모리 불변·렌더·키별 dedup.

## 품질 점검

- `python3 -m pytest .claude/skills/team-derive-author/scripts/tests/ -q` 통과.
- 비-owner의 `register-term`은 종료코드 1로 거부된다.
- `.project/word.json`은 유효 JSON·4필드·중복 term 없음을 유지한다.

## 자주 발생하는 실패 사례

- **`only the team owner '<owner>' may write`** → 정상(직렬화). owner로 실행하거나 inbox로 owner에게 제안한다.
- **`missing required term fields`** → 빠진 필드를 사용자에게 확인. 정의 추측 금지.
- **`term already in team dictionary`** → 이미 등록됨. 갱신 의도라면 별도 정책으로.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
