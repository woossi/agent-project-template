# agent-project-template

에이전트 프로젝트를 시작할 때 복사하는 중립 템플릿입니다.

공유 계약은 `AGENTS.md`에 둡니다.
Claude 실행 규칙은 `.claude/CLAUDE.md`에 둡니다.
프로젝트별 맥락은 `.claude/` 아래에만 추가합니다.

## How to start

1. 이 템플릿을 새 프로젝트 루트에 복사합니다.
2. `AGENTS.md`, `.claude/CLAUDE.md`, `.claude/settings.json`을 확인합니다.
3. 사용자 초기설정에 따라 템플릿 내용을 유지, 전체 재설정, 부분 갱신 중 하나로 정합니다.
4. 프로젝트 맥락은 `.claude/memory/`에 둡니다.
5. 현재 작업은 `.claude/tasks/`에 둡니다.
6. 반복 역할은 `.claude/agents/`에 둡니다.
7. 반복 절차는 `.claude/skills/`에 둡니다.
8. 클론 에이전트가 필요하면 `agent-clone-setup`을 실행합니다.

## Initial skill setup

먼저 `clone-input.json`을 만듭니다.

```json
{
  "agent_name": "reviewer-a",
  "source_agent": "reviewer-template",
  "clone_purpose": "Review scoped documentation changes.",
  "role": "Read assigned files and report risks.",
  "task_objective": "Find contract drift in template docs.",
  "inputs": ["README.md", "AGENTS.md"],
  "allowed_paths": ["README.md", ".claude/**"],
  "denied_paths": [".env", "data/raw/**"],
  "tools": ["Read", "Bash"],
  "outputs": ["findings with file anchors"],
  "handoff_path": ".context/agents/reviewer-a",
  "verification": ["all findings have file anchors"],
  "constraints": ["do not edit files"],
  "initial_notes": ["keep the review scoped"],
  "bash": {
    "allow": ["rg *", "sed *"],
    "deny": ["rm *"]
  }
}
```

그다음 초기 셋업을 생성합니다.

```bash
python .claude/skills/agent-clone-setup/scripts/init_agent_clone.py \
  --input clone-input.json \
  --project-root . \
  --update-policy
```

`--update-policy`를 빼면 workspace policy는 바꾸지 않습니다.

## User input

| 파일 | 역할 |
| --- | --- |
| `clone-input.json` | 클론 에이전트 초기설정 입력 |
| `.claude/memory/memory.md` | 확정된 장기 맥락 |
| `.claude/memory/user_preferences.md` | 프로젝트 범위 선호 |
| `.claude/tasks/tasks.md` | 현재 작업 단위 |

## Auto-updated files

| 파일 | 갱신 조건 |
| --- | --- |
| `.context/agents/<agent_name>/bootstrap.md` | `agent-clone-setup` 실행 |
| `.context/agents/<agent_name>/clone-input.json` | `agent-clone-setup` 실행 |
| `.claude/policies/agent-workspace.json` | `--update-policy` 사용 |
| `.claude/skills/skills.md` | skill index 훅 실행 |
| `.claude/agents/agents.md` | agent index 훅 실행 |
| `write-*/templates/*` | 계약 구조 동기화 훅 실행 |
| `.claude/memory/word.json` | `register-term` 사용 |

## Memory rule

`.claude/memory/`는 짧게 유지합니다.
확정된 사실만 남깁니다.
임시 로그, 진행상황, handoff, 대량 산출물은 `.claude/tasks/`나 `.context/`에 둡니다.

## Core files

| 파일 | 역할 |
| --- | --- |
| `AGENTS.md` | 모든 에이전트의 공유 계약 |
| `.claude/CLAUDE.md` | Claude 런타임 어댑터 |
| `.claude/settings.json` | Claude Code 프로젝트 설정 |
| `.claude/agents/agents.md` | 반복 역할 색인 |
| `.claude/skills/skills.md` | 반복 절차 색인 |
| `.claude/policies/agent-workspace.json` | 에이전트 작업 경계 |

## Built-in skills

| 스킬 | 역할 |
| --- | --- |
| `agent-clone-setup` | 클론 에이전트 bootstrap 생성 |
| `write-skill` | 새 스킬 작성 |
| `write-task` | 현재 작업 패킷 작성 |
| `write-subagent` | 서브에이전트 정의 작성 |
| `update-skill-index` | 스킬 색인 갱신 |
| `register-term` | 용어 사전 갱신 |
