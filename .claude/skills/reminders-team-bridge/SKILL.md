# 스킬: reminders-team-bridge

## 사용 시점

macOS Apple 미리알림(Reminders)을 에이전트 **팀의 작업 백로그**로 직접 연동해 읽고/쓸 때. 구체적으로:

- 미리알림 목록(=팀)에 담긴 할일(=작업)을 에이전트가 읽어 작업 큐로 삼을 때.
- 에이전트가 진행상태를 항목 노트(body)에 남기거나, 완료 시 체크백할 때.
- 팀 후보 목록 목록화, 새 작업 추가, 일회용 샌드박스 목록 생성/삭제가 필요할 때.

미리알림과 무관한 일반 작업 추적은 `.claude/tasks/`를 쓰고, 이 스킬은 미리알림이 작업의 진실원천일 때만 쓴다.

## 목적

미리알림 구조를 팀 작업 모델로 차용해 **실제로 양방향 동기화**한다. 매핑은 미리알림 API가 견고하게 지원하는 2단계 표면(목록→할일)에만 올라탄다:

| 미리알림 | 팀 모델 |
| --- | --- |
| 목록(list, 목록) | **Team** |
| 할일(reminder, 할일) | **Task** `{ id, name, completed, priority, due, notes }` |
| 노트(body) | 사람·에이전트가 진행상태를 비동기로 append하는 free-text 채널 |
| 우선순위(0·1·5·9) | 작업 우선순위/예산 입력값 |

## 계약

- 읽는 입력: 대상 미리알림 목록 이름(=팀), 작업 선택자(`--id` 우선, 없으면 `--name`), 선택적 본문/우선순위/마감.
- 만드는 출력: stdout에 한 줄 JSON(`{ok, op, result}`); 쓰기 연산은 미리알림 DB를 실제로 변경.
- 쓰면 안 되는 위치: 사용자 실데이터 목록을 명시 지시 없이 일괄 변경 금지. 쓰기 검증은 일회용 샌드박스 목록(생성→검증→삭제)으로 한다.

## 입력

- macOS + 미리알림 앱 + `osascript`(JXA 사용).
- 호출 프로세스에 미리알림 자동화(TCC) 권한. 샌드박스 셸에서는 샌드박스를 해제해야 하며, 권한 미허용 시 `-1743`을 반환한다.
- 대상 목록 이름. 후보는 `list-teams`로 먼저 확인한다.

## 절차

1. **팀 후보 확인:** `python scripts/reminders_bridge.py list-teams` — 모든 목록을 `open/total` 카운트와 함께 본다.
2. **백로그 읽기:** `python scripts/reminders_bridge.py pull "<팀=목록>"` (완료 포함은 `--all`). 각 작업의 안정 `id`를 이후 선택자로 쓴다.
3. **작업 추가(선택):** `python scripts/reminders_bridge.py add "<팀>" "<제목>" [--notes ... --priority 1 --due 2026-06-30]`
4. **진행상태 기록:** `python scripts/reminders_bridge.py annotate "<팀>" "[<agent>] <메모>" --id "<reminder-id>"` — 노트 채널에 한 줄 append.
5. **완료 체크백:** `python scripts/reminders_bridge.py complete "<팀>" --id "<reminder-id>"` (되돌리기는 `reopen`).
6. **쓰기 검증은 샌드박스로:** `create-list __agent_sandbox__` → 위 연산 → `delete-list __agent_sandbox__`. 실데이터 목록에 시험 쓰기 금지.
7. 변경한 작업과 목록을 사용자에게 보고한다.

작업 선택은 항상 `--id`(안정 `x-apple-reminder://…`)를 우선한다. 동명 작업이 있을 수 있어 `--name`은 차선이다.

## 출력 형식

stdout에 한 줄(메인은 들여쓴) JSON.

```json
{ "ok": true, "op": "pull", "result": [
  { "id": "x-apple-reminder://...", "name": "선행연구 조사", "completed": false,
    "priority": 5, "due": "2026-06-30T15:00:00.000Z", "notes": "#아이디어" }
] }
```

실패 시 종료코드 1과 `{ "ok": false, "error": "<원인>" }`. 한글·ISO 날짜는 그대로 보존된다.

## 내부 자원

- `scripts/reminders_bridge.py` — argparse CLI. 서브커맨드: `list-teams`, `pull`, `add`, `complete`, `reopen`, `annotate`, `create-list`, `delete-list`. 읽기는 부작용 없음, 쓰기는 명시 서브커맨드. JXA 경계는 `run_jxa(runner=...)`로 주입 가능(테스트용).
- `scripts/reminders.jxa.js` — `osascript -l JavaScript`로 실행되는 JXA 워커. argv[0]의 JSON 명령을 받아 미리알림을 조작하고 `JSON.stringify`로 깨끗한 UTF-8 JSON을 반환한다(AppleScript `as text`의 UTF-16 깨짐 회피).
- `scripts/tests/test_reminders_bridge.py` — CI 안전 단위 테스트(osascript·실데이터 미접촉). `build_command`(순수)와 `run_jxa`(가짜 runner) 검증.

## 품질 점검

- `python3 -m pytest .claude/skills/reminders-team-bridge/scripts/tests/ -q` 가 통과해야 한다.
- 읽기 연산(`list-teams`/`pull`)은 미리알림을 변경하지 않는다.
- 쓰기 검증 후 샌드박스 목록은 반드시 `delete-list`로 제거되어 흔적이 남지 않는다.
- 작업 선택자는 `--id`를 우선 사용한다.

## 자주 발생하는 실패 사례

- **`-1743` / Not authorized** → 호출 프로세스에 미리알림 자동화 권한이 없음. 샌드박스를 해제하고, 시스템 설정 > 개인정보 보호 및 보안 > 자동화에서 권한을 허용한다.
- **`list (team) not found`** → 목록 이름 오타. `list-teams`로 정확한 이름을 확인한다(한글 공백 포함).
- **`select the task with --id or --name`** → `complete`/`annotate`에 선택자 누락. `pull`로 얻은 `id`를 전달한다.
- **AppleScript `as text`로 직접 읽어 한글이 깨짐** → 금지. 반드시 이 스킬(JXA)을 거친다.
- **그룹(폴더) 단위로 조작 시도** → 불가. 미리알림 API는 그룹을 노출하지 않는다(목록의 container는 account). 팀 단위는 항상 "목록"이다.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
