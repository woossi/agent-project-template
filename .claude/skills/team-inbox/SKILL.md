# 스킬: team-inbox

## 사용 시점

동일 구조 peer 에이전트들이 **팀 mailbox로 구조화된 메시지를 주고받아야** 할 때. 구체적으로:

- 한 에이전트가 특정 팀에 작업 위임·질의·완료 통지를 남길 때.
- 팀장이 자기 팀 mailbox를 읽고, claim/ack 후 팀 보드에 작업을 분배할 때.
- 워커가 완료/질문/검증 결과를 자기 팀 또는 상대 팀 mailbox로 보고할 때.

작업(Task) 단위 진행상태는 미리알림 노트와 팀 보드에 남기고, 이 스킬은 **팀 간/팀장 수신 구조화 메시지**에 쓴다. 개인→개인 메시지와 broadcast는 사용하지 않는다.

## 목적

팀 루트 위에서 손상·유실·머지충돌 없는 팀 mailbox를 제공한다. 단일 가변 로그/JSON 배열을 쓰지 않고, **메시지당 불변 파일 1개**를 팀 mailbox 디렉토리에 **atomic rename**으로 게시한다.

## 계약

- 읽는 입력: 발신/행위 정체성(`CLAUDE_AGENT_NAME` 또는 `--from`/`--as`), 팀 루트(`--root`, 기본 `.project/team.json` 앵커), `.project/team.json`의 subteams.
- 만드는 출력: `teams/<팀>/.claude/inbox/<msgid>.json` 또는 `teams/.orchestrator/inbox/<msgid>.json`, stdout JSON `{ok, op, result}`.
- 권한: `post`는 누구나 가능하다. `read`/`claim`/`ack`는 해당 팀장 또는 company owner만 가능하다. `orchestrator` mailbox는 company owner만 읽는다.

## 입력

- 안정적 에이전트 정체성. terminal에서 `export CLAUDE_AGENT_NAME=<이름>` 후 `claude` 실행.
- 팀 루트의 `.project/team.json`.

## 절차

1. **보내기:** `python scripts/team_inbox.py post --to-team <팀> --subject "<제목>" --body "<본문>"`. 발신자는 env에서 자동.
2. **읽기:** 팀장만 `python scripts/team_inbox.py read --team <팀>`으로 미처리 메시지를 본다. 총괄은 `--team orchestrator`.
3. **Claim:** 팀장만 `python scripts/team_inbox.py claim --team <팀> --id <msgid>`로 메시지를 자기 이름의 `.claimed/`로 이동한다.
4. **소비 표시:** 팀장만 `python scripts/team_inbox.py ack --team <팀> --id <msgid>`로 `.consumed/`로 이동한다.
5. 답장은 `post ... --reply-to <원본msgid>`.

## 출력 형식

```json
{ "ok": true, "op": "read", "result": [
  { "id": "00000000000000000005__orchestrator__a1b2c3d4", "from": "orchestrator",
    "to_team": "data", "recipients": ["data-lead", "data-engineer"], "subject": "작업 위임",
    "body": "umc-data 요청", "reply_to": null, "ts_ns": 5, "_state": "unclaimed" }
] }
```

`msgid`는 `<나노초>__<발신자>__<랜덤>` 형태로 시간순 정렬되며 peer 간 충돌이 없다.

## 내부 자원

- `scripts/team_inbox.py` — CLI/라이브러리. `post`(팀 mailbox에 atomic write), `read`(`--all`로 claimed/consumed 포함), `claim`(`.claimed/`로 atomic 이동), `ack`(`.consumed/`로 atomic 이동, 멱등). 정체성은 `--from`/`--as` 또는 `CLAUDE_AGENT_NAME`. root는 `--root`/`CLAUDE_TEAM_ROOT`/`.project/team.json` 앵커.
- `scripts/tests/test_team_inbox.py` — CI 안전 단위 테스트(임시 root, 에이전트·osascript 미접촉): msgid 정렬·유일성, 팀 mailbox 위치, lead-only read/claim/ack, orchestrator mailbox 권한, 시간순 읽기, 멱등 ack, env 정체성, CLI 왕복.

## 품질 점검

- `python3 -m unittest discover -s .claude/skills/team-inbox/scripts/tests -p 'test_*.py'` 통과.
- 메시지는 팀 mailbox에만 생긴다.
- claim 후 unclaimed에서 사라지고 `--all`로 claimed/consumed를 볼 수 있다. 중복 ack는 에러가 아니다.

## 자주 발생하는 실패 사례

- **`no agent identity`** → `CLAUDE_AGENT_NAME` 미설정. 터미널에서 export하거나 `--from`/`--as` 전달.
- **`no team for '<agent>'`** → `.project/team.json`의 subteams에 정체성이 없다. 팀 설정을 고친 뒤 `team-init`을 다시 실행한다.
- **워커가 read/claim/ack 거부됨** → 정상. 워커는 mailbox를 직접 읽지 않고 팀 보드의 자기 섹션을 수행한다.
- **다른 팀 inbox를 Read/Grep/Bash로 직접 읽으려다 guard 차단** → 정상. 팀 mailbox는 `post` drop-off만 허용된다.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
