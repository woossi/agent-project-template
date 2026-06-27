# agent-project-template

로컬 에이전트 프로젝트를 시작할 때 복사해 쓰는 시작 패킷입니다.

## How to start

1. 이 폴더를 새 프로젝트 루트에 복사합니다.
2. `agent-clone-setup`을 `--project-setup`으로 실행하며 에이전트 정보를 stdin으로 넘깁니다. 스킬이 `agent-setup.json`을 작성하고 진입 파일까지 한 번에 전환합니다.
3. 생성된 `agent-setup.json`, `AGENTS.md`, `.claude/CLAUDE.md`를 확인합니다.
4. 장기 맥락은 `.claude/memory/`, 현재 작업은 `.claude/tasks/`, 임시 산출물은 `.context/`에 둡니다.

> 단일 에이전트가 아니라 **여러 에이전트를 팀으로** 운영하려면 아래 [멀티에이전트 팀 세팅](#멀티에이전트-팀-세팅-model-y-터미널-claude)을 참고하세요.

## Component relationships (Tasks → Skills → Agents)

세 컴포넌트는 상향식 생성 사슬을 이룹니다. 정본 정의는 `AGENTS.md`의 *Component Layer Relationships*에 있으며, 요약은 다음과 같습니다.

- **Tasks (`.claude/tasks/`)** — 가장 작은 작업 단위. 에이전트가 실행 작업을 자동으로 기록·갱신하며(사용자가 큐레이션하지 않음), 작업 패킷은 현재 상태만 담습니다. 실행 로그와 handoff는 `.context/`로 둡니다.
- **Skills (`.claude/skills/`)** — 반복되는 작업 묶음이 하나의 포괄 이름으로 묶일 수 있을 때 그 묶음을 승격해 만든 재사용 절차.
- **Agents (`.claude/agents/`)** — 특정 스킬 패키지를 독립 컨텍스트에서 관리해야 할 때 만드는 서브에이전트.

이 사슬의 트리거는 훅으로 강제됩니다. `.claude/hooks/task_ledger.py`가 실행 작업과 스킬 사용을 `.context/task-log/`에 자동 기록하고, `.claude/hooks/detect_promotions.py`가 `.claude/policies/promotion.json`의 조건으로 평가해 승격 후보를 매 턴 다시 띄웁니다. 후보 저작은 `write-skill`/`write-subagent`로 하고, `detect_promotions.py resolve`로 닫습니다. 조건은 `promotion.json`에서 조정합니다.

## Initial skill setup

`agent-clone-setup --project-setup`은 아래 필드를 입력으로 받아, 정규화한 정본을 `agent-setup.json`으로 작성하고 곧바로 진입 파일까지 전환합니다. 입력 작성과 초기 전환이 한 번에 끝납니다. 루트의 `agent-setup.json`에는 동작하는 예시 값(`knowledge-base-manager`)이 들어 있습니다.

필수 필드:

| 필드 | 의미 |
| --- | --- |
| `agent_name` | 에이전트 이름 (영문·숫자·`-`·`_`만) |
| `agent_purpose` | 에이전트 목표 |
| `role` | 에이전트 역할 |
| `workspace_paths` | 작업 허용 경로 (`.`는 자동 포함) |
| `inputs` | 읽거나 사용할 입력 |
| `outputs` | 기대 산출물 |
| `verification` | 결과 검증 기준 |
| `constraints` | 금지 사항과 제약 |

선택 필드: `operating_rules`, `memory_rules`, `tools`, `denied_paths`, `initial_notes`, `bash`(`{ "allow": [...], "deny": [...] }`).

값을 stdin으로 넘기면 스킬이 `agent-setup.json`을 만들고 전환까지 합니다.

```bash
python .claude/skills/agent-clone-setup/scripts/init_agent_clone.py \
  --project-setup \
  --project-root . \
  --update-policy <<'JSON'
{
  "agent_name": "knowledge-base-manager",
  "agent_purpose": "지식 DB 관리와 지식 그래프 유지 및 업데이트",
  "role": "로컬 지식 관리 에이전트",
  "workspace_paths": ["/Users/~/knowledge"],
  "inputs": ["사용자 요청", "/Users/~/knowledge"],
  "outputs": ["갱신된 지식 DB", "검증된 지식 그래프"],
  "verification": ["변경 파일과 그래프 연결을 확인한다"],
  "constraints": ["근거 없이 지식을 만들지 않는다"]
}
JSON
```

이미 `agent-setup.json`이 있으면 파일로 줄 수도 있습니다.

```bash
python .claude/skills/agent-clone-setup/scripts/init_agent_clone.py \
  --project-setup \
  --input agent-setup.json \
  --project-root . \
  --update-policy
```

`--update-policy`를 빼면 작업 경계 정책은 바꾸지 않습니다. `--no-save-input`을 주면 `agent-setup.json` 작성을 건너뜁니다.

## User input

| 파일 | 역할 |
| --- | --- |
| `agent-setup.json` | 단일 에이전트 프로젝트 전환 입력. 비워 두면 스킬이 stdin 값으로 작성합니다 |
| `team-setup.json` | 팀 정의 입력(`team-init`). `team`·`members` 필수, 선택 `reminders_list`·`roles`·`authoring_owner`·`min_distinct_agents` |

## Auto-updated files

| 파일 | 갱신 조건 |
| --- | --- |
| `AGENTS.md` | `agent-clone-setup --project-setup` 실행 |
| `.claude/CLAUDE.md` | `agent-clone-setup --project-setup` 실행 |
| `.claude/policies/agent-workspace.json` | `--update-policy` 사용 |
| `.claude/skills/skills.md` | skill index hook 실행 |
| `.claude/agents/agents.md` | agent index hook 실행 |
| `.claude/memory/word.json` | `register-term` 사용 |
| `.context/task-log/*.jsonl` | 모든 도구 실행 시 `task_ledger.py`가 자동 기록 (git-ignore) |
| `.context/promotions/candidates.json` | `detect_promotions.py`가 승격 조건 평가 시 갱신 (git-ignore) |

`.context/`는 git-ignore 대상이라 커밋되지 않습니다. 승격 조건(스킬·에이전트 임계값)은 `.claude/policies/promotion.json`에서 조정합니다.

## Inter-agent feedback

두 에이전트 프로젝트를 양방향 작업 피드백으로 잇는 드롭인 시스템이 포함되어 있습니다.
`detect_feedback.py` hook + `feedback.json` 정책 + `give-feedback`/`process-feedback` 스킬로,
한 에이전트가 상대 산출물에 보낸 피드백이 상대 받은편지함(`.context/feedback/inbox.jsonl`)에
쌓이고 매 세션·턴 재표면화되어 처리·승격·파생 사슬에 연결됩니다.

두 프로젝트를 페어링하려면 각 프로젝트에서 `feedback.json`의 `agent` 블록,
`agent-workspace.json`의 상대 inbox allow, `AGENTS.md` 작업 경계를 채웁니다.
자세한 절차와 설계는 `.claude/policies/FEEDBACK.md`를 보세요.

## 멀티에이전트 팀 세팅 (Model Y, 터미널 Claude)

단일 에이전트 클론(위) 외에, 이 템플릿은 **동일 구조 peer 에이전트들의 팀**으로도 운영할 수 있습니다.
Conductor 없이 **터미널 Claude**로 각 에이전트를 띄우며, 공유 `.claude/` 한 벌을 symlink로 공유하고
정체성(`CLAUDE_AGENT_NAME`)만 다릅니다. 사람은 **미리알림**으로, 에이전트끼리는 **팀 mailbox**로 같은 작업 위에서 협업합니다.

### 구조

```
<Team 루트 = 이 저장소>
  .claude/                     # 공유 템플릿 1벌 (hooks·policies·skills·계약) — 단일 소스
  .project/                       # 팀 공유 상태
    team.json                  #   로스터·미리알림 바인딩·목표 디렉토리
    goals/<id>.json            #   목표 (계약 요소 포함)            [durable]
    tasks/<goal>__<slug>.json  #   목표에서 분해된 작업              [durable]
    word.json · memory/        #   팀 용어·결정 (owner 직렬화)       [durable]
    policies/team-*.json       #   팀 승격/파생 임계값·거버넌스
    promotions/ · derivations/ #   팀 후보·결정                      [runtime, git-ignore]
  teams/<팀>/.claude/inbox/     # 팀 mailbox                         [runtime, git-ignore]
  teams/.orchestrator/inbox/    # 총괄 mailbox                       [runtime, git-ignore]
  teams/<팀>/<워커>/             # 워커별 작업 공간
    .claude/memory · tasks     #   개별(사적) 실파일
    .claude/{hooks,policies,skills,settings.json,CLAUDE.md} → 루트로 symlink (공유)
    AGENTS.md → 루트로 symlink
    .context/                  #   개별 실행 원장                    [runtime, git-ignore]
```

### 1. 전제조건

- macOS + `python3`. 테스트: `python3 -m pytest .claude -q`.
- 미리알림 연동은 `osascript`(JXA)와 **자동화(TCC) 권한**이 필요합니다. 샌드박스 셸이면 권한 허용 또는 샌드박스 해제 후 실행하세요(미허용 시 `-1743`).

### 2. 팀 정의 — `team-setup.json` → `team-init`

팀 정의는 손으로 여러 파일에 쓰지 않고, **`team-setup.json` 한 장**에서 생성합니다(루트에 동작 예시 포함).
`agent-clone-setup`의 *json→전환*, `create-team-agent`의 *스캐폴딩*을 팀 레벨로 합친 진입점입니다.

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

```bash
python .claude/skills/team-init/scripts/team_init.py init --input team-setup.json
```

이 한 번으로 `.project/team.json` + `.project/policies/team-{promotion,derivation}.json` + 디렉토리가 생성되고,
`authoring_owner`(누가 팀 자산을 저작하는지)·`min_distinct_agents`(팀 승격 임계값)가 정책에 전파됩니다.
`--create-agents`를 붙이면 아래 3절(멤버 에이전트 생성)까지 한 번에 끝납니다. stdin으로도 줄 수 있습니다.

### 3. 에이전트 생성 — `create-team-agent`

`team-init --create-agents`가 멤버를 한 번에 만들지만, 나중에 멤버를 **추가**하거나 개별 생성할 때는 이 스킬을 직접 씁니다.
생성 시점은 사용자가 판단합니다. 생성하면 개별 자산(memory·tasks·`.context`)은 실파일로 seed되고,
공유 자산(hooks·policies·skills·settings·계약)은 루트로 symlink되며 `team.json` 로스터에 등록됩니다.

```bash
python .claude/skills/create-team-agent/scripts/team_agent.py create orchestrator --role "백로그 분해·할당·완료 추적"
python .claude/skills/create-team-agent/scripts/team_agent.py create worker-1     --role "작업 실행·진행 기록·완료 체크"
python .claude/skills/create-team-agent/scripts/team_agent.py list   # 폴더↔로스터 정합 확인
```

### 4. 에이전트로 실행 — 런치 계약

각 터미널에서 **정체성만 다르게** 주고, 해당 에이전트 폴더에서 `claude`를 띄웁니다.

```bash
# 터미널 1
export CLAUDE_AGENT_NAME=orchestrator
cd . && claude

# 터미널 2
export CLAUDE_AGENT_NAME=data-engineer
cd teams/data/data-engineer && claude
```

`CLAUDE_AGENT_NAME`은 guard(`guard_agent_workspace.py`)와 모든 팀 CLI가 읽는 정체성입니다.
설정하지 않으면 `main`으로 떨어져 정체성이 붕괴하므로 **반드시 export**합니다. 폴더 경계 덕에
각 에이전트의 `.context/`는 자동 격리되고, 형제 폴더 접근은 차단됩니다.

### 5. 두 작업 채널

**미리알림 (목록=팀, 할일=Task)** — 사람도 보는 백로그:

```bash
B=.claude/skills/reminders-team-bridge/scripts/reminders_bridge.py
python $B list-teams                       # 목록(=팀 후보) + open/total
python $B pull umc                          # 팀 백로그 읽기(JSON)
python $B annotate umc "[worker-1] 착수" --id <reminder-id>   # 노트에 진행상태
python $B complete umc --id <reminder-id>   # 완료 체크백
```

**팀 mailbox** — 팀 단위 구조화 메시지:

```bash
I=.claude/skills/team-inbox/scripts/team_inbox.py
python $I post --to-team data --subject "위임" --body "<요청>"   # 발신=$CLAUDE_AGENT_NAME
python $I read --team data                  # 팀장/총괄만 가능
python $I claim --team data --id <msgid>    # 팀장/총괄만 가능
python $I ack --team data --id <msgid>      # 처리 표시(멱등)
```

워커는 mailbox를 직접 읽지 않는다. 팀장이 팀 보드(`teams/<팀>/.claude/tasks/tasks.md`)에 워커별 작업을 배정하고, 워커는 완료/질문을 `post --to-team <팀>`으로 보고한다.

### 6. 목표 — `set-team-goal`

사용자가 추상 목표를 **계약 요소**와 함께 설정하면, 팀이 success_criteria마다 구체 Task로 분해합니다.
목표는 미리알림과 별개이며, `progress`가 자율 작업의 **정지조건**이 됩니다.

```bash
G=.claude/skills/set-team-goal/scripts/team_goal.py
python $G --by orchestrator set --title "UMC 논문화" --objective "..." --deliverable "..." \
  --success-criteria "전 섹션 초고 완성" --success-criteria "방법론 기여 명확화" --verification "지도교수 리뷰 통과"
python $G --by orchestrator decompose --id umc-논문화 --task "섹션 초고" --criterion "전 섹션 초고 완성" --assign worker-1
python $G progress --id umc-논문화          # 어떤 기준이 done task로 덮였는지 + complete 여부
```

### 7. 팀 승격/파생 (개별 루프 위의 2계층)

개별 루프(세션 재발)는 그대로 두고, 팀 계층은 **여러 에이전트에 걸친 재발**(`min_distinct_agents`)로 트리거합니다.
탐지기는 `agents/*/.context/`를 읽기 전용 롤업해 후보를 SessionStart마다 표면화합니다.

```bash
# 팀 승격(스킬/에이전트) — distinct-agent 재발
python .claude/hooks/detect_team_promotions.py evaluate
python .claude/hooks/detect_team_promotions.py resolve --kind team_skill --key <sig> --decision promote --by orchestrator

# 팀 파생(용어/선호/메모리) — 저작은 owner 직렬화
python .claude/hooks/detect_team_derivations.py evaluate
python .claude/skills/team-derive-author/scripts/team_derive.py --by orchestrator \
  register-term --term LISA --ko "국소 모란 지수" --definition "..." --use-when "..."   # owner만
python .claude/hooks/detect_team_derivations.py resolve --kind term --key LISA --decision promote --by orchestrator
```

### 팀 컴포넌트 한눈에

| 스킬/훅 | 역할 |
| --- | --- |
| `team-init` | `team-setup.json` → `.project` 정의(team.json·정책·디렉토리) 생성, `--create-agents`로 멤버까지 |
| `create-team-agent` | Model Y peer 스캐폴딩 + 로스터 등록 |
| `reminders-team-bridge` | 미리알림 ↔ 팀 백로그 양방향(JXA) |
| `team-inbox` | peer↔peer 다대다 채널(불변 파일·atomic·멱등) |
| `set-team-goal` | 목표(계약 요소) + 분해 + 정지조건 progress |
| `team-derive-author` | 팀 용어·메모리 저작(owner 직렬화) |
| `detect_team_promotions.py` | 팀 스킬/에이전트 승격(distinct-agent) |
| `detect_team_derivations.py` | 팀 용어/선호/메모리 파생(distinct-agent + `Share:` 마커) |
| `task_ledger.py record-skill-use` | 심볼릭 공유 skill 사용 신호 stamp |

### durable vs runtime

`.project/{goals,tasks,memory,word.json,policies}`와 에이전트 seed는 **추적**합니다.
`.project/{inbox,promotions,derivations}`와 `agents/*/.context/`는 런타임이라 **git-ignore**됩니다.

## Memory rule

`.claude/memory/`는 압축적으로 관리합니다.
확정된 장기 맥락만 남깁니다.
현재 작업 상태는 `.claude/tasks/`에 두고, 에이전트의 실행 로그·진행상황·handoff·대량 산출물은 `.context/`에 둡니다.
