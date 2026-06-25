# 스킬: team-init

## 사용 시점

새 팀을 정의하거나 팀 정의를 갱신할 때 — `team-setup.json` 하나로 `.team/` 공유 상태(로스터·미리알림 바인딩·승격/파생 정책·디렉토리)를 한 번에 작성한다. `agent-clone-setup`의 *json→전환*, `create-team-agent`의 *스캐폴딩*을 팀 레벨로 합친 진입점이다.

## 목적

팀 "정의"를 손으로 여러 파일에 쓰지 않고, 단일 입력 json으로 일관되게 생성한다. `--create-agents`를 주면 멤버 에이전트까지 `create-team-agent`로 스캐폴딩해, json 한 장에서 실행 가능한 Model Y 팀까지 한 단계로 만든다.

## 계약

- 읽는 입력: `team-setup.json`(파일 `--input` 또는 stdin). 필수 `team`, `members`. 선택 `reminders_list`, `roles`, `authoring_owner`(기본 `members[0]`), `min_distinct_agents`(기본 2).
- 만드는 출력: `.team/team.json`, `.team/policies/team-promotion.json`, `.team/policies/team-derivation.json`, `.team/{goals,inbox}/.gitkeep`. 정규화 입력을 `team-setup.json`으로 저장(끄려면 `--no-save-input`). stdout JSON 요약.
- 쓰면 안 되는 위치: 개별 에이전트 자산을 직접 만들지 않는다(그건 `create-team-agent`/`--create-agents`가 한다). 런타임(`.team/inbox` 내용 등)은 만들지 않는다.

## 입력

`team-setup.json` 예시(루트의 `team-setup.json`에 동작 예시 포함):

```json
{
  "team": "research-umc",
  "reminders_list": "umc",
  "members": ["orchestrator", "worker-1"],
  "roles": {
    "orchestrator": "백로그 분해·할당·완료 추적",
    "worker-1": "작업 실행·진행 기록·완료 체크"
  },
  "authoring_owner": "orchestrator",
  "min_distinct_agents": 2
}
```

## 절차

1. **팀 정의 작성:**
   ```bash
   python .claude/skills/team-init/scripts/team_init.py init --input team-setup.json
   ```
   stdin으로 줄 수도 있다: `... team_init.py init <<'JSON' ... JSON`.
2. **멤버까지 한 번에 생성(선택):** `--create-agents`를 붙이면 각 멤버를 `create-team-agent`로 스캐폴딩한다.
3. **확인:** `python .claude/skills/create-team-agent/scripts/team_agent.py list`로 폴더↔로스터 정합을 본다.

`authoring_owner`/`min_distinct_agents`는 정책에 그대로 반영되며, 이후 `.team/policies/team-*.json`에서 조정한다.

## 출력 형식

```json
{ "ok": true, "op": "init", "result": {
  "team": "research-umc", "members": ["orchestrator","worker-1"],
  "authoring_owner": "orchestrator", "min_distinct_agents": 2, "reminders_list": "umc",
  "files": [".team/team.json", ".team/policies/team-promotion.json", ".team/policies/team-derivation.json"],
  "agents_created": [] } }
```

## 내부 자원

- `scripts/team_init.py` — `init`(파일/stdin 입력→정의 작성, `--create-agents`, `--save-input`/`--no-save-input`, `--team-root`). 정책은 탐지기가 읽는 스키마로 생성하고, `min_distinct_agents`·`authoring_owner`를 전파. atomic 쓰기.
- `scripts/tests/test_team_init.py` — CI 안전 테스트: 검증(team/members/owner/min), 정책 전파, 파일·디렉토리 작성, `--create-agents`(스텁), CLI 저장.

## 품질 점검

- `python3 -m pytest .claude/skills/team-init/scripts/tests/ -q` 통과.
- 생성된 `.team/policies/team-*.json`은 `detect_team_promotions.py`/`detect_team_derivations.py`가 읽는 키를 갖는다.
- `authoring_owner`는 반드시 `members`에 속한다(아니면 거부).

## 자주 발생하는 실패 사례

- **`needs a non-empty 'team' name` / `needs 'members'`** → 필수 필드 누락. team·members를 채운다.
- **`authoring_owner ... must be one of members`** → owner를 멤버 중에서 지정한다.
- **`--create-agents`인데 스캐폴딩 안 됨** → `create-team-agent` 스킬이 있어야 하며, `--team-root`가 repo 루트여야 한다.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
