# 스킬: team-inbox

## 사용 시점

동일 구조 peer 에이전트들이 **서로에게 구조화된 메시지를 주고받아야** 할 때(다대다 채널). 구체적으로:

- 한 에이전트가 다른 에이전트(또는 팀 전체=broadcast)에게 작업 위임·질의·완료 통지를 보낼 때.
- 받은 메시지를 읽고(unread), 처리 후 소비 표시(ack)할 때.

작업(Task) 단위 진행상태는 미리알림 노트(`reminders-team-bridge`의 `annotate`)에 남기고, 이 스킬은 **에이전트 사이의 직접 메시지**에 쓴다. 서브에이전트 결과 반환과는 다른 계층이다(peer↔peer, 부모↔자식 아님).

## 목적

공유 store(`.team/`) 위에서 손상·유실·머지충돌 없는 다대다 메시지 버스를 제공한다. 단일 가변 로그/JSON 배열을 쓰지 않고, **메시지당 불변 파일 1개**를 수신자 디렉토리에 **atomic rename**으로 게시한다.

## 계약

- 읽는 입력: 발신/수신 정체성(`CLAUDE_AGENT_NAME` 또는 `--from`/`--as`), 공유 store(`$CLAUDE_TEAM_STORE` 또는 `--store`, 기본 `.team`), broadcast 시 `team.json`의 `members`.
- 만드는 출력: `<store>/inbox/<수신자>/<msgid>.json`(불변), stdout JSON `{ok, op, result}`.
- 쓰면 안 되는 위치: 공유 store 파일을 Read/Write/Edit 도구로 직접 건드리지 않는다(이 CLI를 Bash로 호출 — path guard는 Read/Edit/Write만 게이팅하므로 CLI 경유가 정상 경로다).

## 입력

- 안정적 에이전트 정체성. terminal에서 `export CLAUDE_AGENT_NAME=<이름>` 후 `claude` 실행.
- 공유 store 디렉토리(기본 `.team`). broadcast를 쓰려면 `<store>/team.json`에 `members` 배열.

## 절차

1. **보내기:** `python scripts/team_inbox.py post --to <수신자> --subject "<제목>" --body "<본문>"` (반복 `--to`, 또는 `--broadcast`로 로스터 전체-자기 제외). 발신자는 env에서 자동.
2. **읽기:** `python scripts/team_inbox.py read`(자기 unread). 처리할 메시지의 `id`를 확보한다.
3. **소비 표시:** `python scripts/team_inbox.py ack --id <msgid>` (멱등 — 중복 ack는 무해).
4. 답장은 `post ... --reply-to <원본msgid>`.

## 출력 형식

```json
{ "ok": true, "op": "read", "result": [
  { "id": "00000000000000000005__orchestrator__a1b2c3d4", "from": "orchestrator",
    "to": "worker-1", "recipients": ["worker-1"], "subject": "작업 위임",
    "body": "umc: 선행연구 조사 맡아주세요", "reply_to": null, "ts_ns": 5, "_state": "unread" }
] }
```

`msgid`는 `<나노초>__<발신자>__<랜덤>` 형태로 시간순 정렬되며 peer 간 충돌이 없다.

## 내부 자원

- `scripts/team_inbox.py` — CLI/라이브러리. `post`(타겟/broadcast, 수신자별 fan-out, atomic write), `read`(unread, `--all`로 소비분 포함), `ack`(`.consumed/`로 atomic 이동, 멱등). 정체성은 `--from`/`--as` 또는 `CLAUDE_AGENT_NAME`. store는 `--store`/`CLAUDE_TEAM_STORE`/기본 `.team`.
- `scripts/tests/test_team_inbox.py` — CI 안전 단위 테스트(임시 store, 에이전트·osascript 미접촉): msgid 정렬·유일성, fan-out, broadcast 제외-자기, 시간순 읽기, 멱등 ack, env 정체성, CLI 왕복.

## 품질 점검

- `python3 -m pytest .claude/skills/team-inbox/scripts/tests/ -q` 통과.
- 메시지는 수신자 디렉토리에만 생기며, 발신자 inbox는 비어 있다.
- ack 후 unread에서 사라지고 `--all`로만 보인다. 중복 ack는 에러가 아니다.

## 자주 발생하는 실패 사례

- **`no agent identity`** → `CLAUDE_AGENT_NAME` 미설정. 터미널에서 export하거나 `--from`/`--as` 전달.
- **`team roster not found` (broadcast)** → `<store>/team.json`에 `members` 필요. 타겟 `--to`는 로스터 없이 동작.
- **공유 store를 Write 도구로 직접 수정하려다 guard 차단** → 정상. 이 CLI(Bash 경유)로만 접근한다.
- **다른 에이전트의 inbox를 읽어 처리** → 금지. 각자 자기 `--as`만 소비한다.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
