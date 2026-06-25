# 스킬: set-team-goal

## 사용 시점

사용자가 팀에게 **추상적 목표(Goal)를 설정**해 일을 이끌 때. 목표는 미리알림과 **별개**로 다뤄지며, 팀은 이를 구체 Tasks로 분해해 달성한다. 구체 작업을 직접 등록하려는 경우(목표 우회)는 미리알림(`reminders-team-bridge`)을 쓴다.

## 목적

팀의 최상위 컨텍스트인 목표를 **구체적 계약 요소와 함께** `.team/goals/`에 기록한다. 목표의 계약(특히 `success_criteria`/`verification`)은 이후 (1) Tasks 분해의 기준이자 (2) 팀 자율 작업의 **정지 조건**이 된다. 계약 요소는 사용자에게 확인받아 채우며, 임의로 창작하지 않는다.

## 계약

- 읽는 입력: 목표 제목 + 계약 요소(필수: objective, deliverable, ≥1 success_criteria, ≥1 verification; 선택: scope, constraints), 공유 store(`$CLAUDE_TEAM_STORE` 또는 `--store`, 기본 `.team`), 작성자(`$CLAUDE_AGENT_NAME` 또는 `--by`).
- 만드는 출력: `.team/goals/<id>.json`(id=slug(title), canonical 1파일/목표, `os.replace` 원자적 갱신), stdout JSON.
- 쓰면 안 되는 위치: 목표를 미리알림 목록으로 만들지 않는다(목표는 미리알림과 별개). 계약 요소를 추측해 채우지 않는다.

## 입력

- 목표 1건의 계약 요소. `success_criteria`/`verification`은 **반드시 사용자에게 확인**한다 — 빈 값이면 CLI가 거부(종료코드 1).

## 절차

1. **계약 요소를 확보한다.** objective(한 문장 결과), deliverable(구체 산출물), success_criteria(달성 기준), verification(검증 방법)을 사용자에게 확인한다. 모호하면 추측하지 말고 묻는다.
2. **목표를 기록한다:**
   ```bash
   python scripts/team_goal.py set \
     --title "<제목>" --objective "<한 문장>" --deliverable "<산출물>" \
     --success-criteria "<기준1>" --success-criteria "<기준2>" \
     --verification "<검증>" [--scope "<범위>"] [--constraints "<제약>"]
   ```
3. **Tasks로 분해한다(판단 단계).** 목표의 success_criteria마다 구체 Task를 도출해 기록한다:
   ```bash
   python scripts/team_goal.py decompose --id <goal> --task "<제목>" --criterion "<해당 success_criterion>" [--assign <agent>]
   ```
   분해는 자동화하지 말고(판단 단계), 각 task를 목표의 어떤 기준에 매핑하는지 `--criterion`으로 명시한다. 이 task들은 `.team/tasks/`(미리알림과 별도 내부 백로그)에 쌓이고, `--assign`으로 에이전트에 배정된다.
4. **진행/정지조건 확인:** `python scripts/team_goal.py progress --id <goal>` — 어떤 success_criterion이 done task로 덮였는지와 `complete` 여부를 본다(목표가 자율 작업의 정지조건). task 상태는 `task-status --id <goal> --task-slug <slug> --set {pending,in-progress,done,dropped}`.
5. **목표 상태 관리:** `python scripts/team_goal.py status --id <id> --set {pending,active,done,dropped}`.

## 출력 형식

```json
{ "ok": true, "op": "set", "result": {
  "id": "연구-목표", "title": "연구 목표", "objective": "...", "deliverable": "...",
  "success_criteria": ["..."], "verification": ["..."], "constraints": ["..."],
  "status": "active", "created_by": "orchestrator", "updated_ts_ns": 100 } }
```

## 내부 자원

- `scripts/team_goal.py` — CLI/라이브러리. 목표: `set`(계약 요소 검증 후 기록), `status`, `list`, `show`. 분해: `decompose`(success_criterion에 매핑된 task를 `.team/tasks/`에 배정), `tasks`(목록), `task-status`, `progress`(criteria 충족·정지조건 뷰). 목표·task당 canonical 1파일 + `os.replace` 원자적 갱신, 재설정 시 생성 메타 보존. 정체성은 `--by`/`CLAUDE_AGENT_NAME`(기본 `user`), store는 `--store`/`CLAUDE_TEAM_STORE`/`.team`.
- `scripts/tests/test_team_goal.py` — CI 안전 단위 테스트: 계약 누락 거부, 재설정 메타 보존, 상태 갱신, 목록 필터, CLI 왕복.

## 품질 점검

- `python3 -m pytest .claude/skills/set-team-goal/scripts/tests/ -q` 통과.
- success_criteria·verification이 비어 있으면 목표 생성 거부(종료코드 1).
- 같은 제목 재설정은 새 목표가 아니라 기존 목표 갱신(생성 메타 보존).

## 자주 발생하는 실패 사례

- **`missing required contract elements`** → objective/deliverable/success_criteria/verification 중 빠진 것을 사용자에게 확인해 채운다. 추측 금지.
- **목표를 미리알림에 등록하려 함** → 범위 밖. 목표는 `.team/goals/`, 구체 작업 직접 등록만 미리알림.
- **목표 분해를 자동 생성으로 처리** → 분해는 판단 단계. 각 task를 success_criteria에 매핑해 작성한다.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
