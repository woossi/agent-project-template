# agent-project-template

로컬 에이전트 프로젝트를 시작할 때 복사해 쓰는 시작 패킷입니다.

## How to start

1. 이 폴더를 새 프로젝트 루트에 복사합니다.
2. `agent-setup.json`을 작성합니다.
3. `agent-clone-setup`을 `--project-setup`으로 실행합니다.
4. 생성된 `AGENTS.md`, `.claude/CLAUDE.md`, `.claude/settings.json`을 확인합니다.
5. 장기 맥락은 `.claude/memory/`, 현재 작업은 `.claude/tasks/`, 임시 산출물은 `.context/`에 둡니다.

## Initial skill setup

`agent-setup.json` 예시:

```json
{
  "agent_name": "knowledge-base-manager",
  "agent_purpose": "지식 DB 관리와 지식 그래프 유지 및 업데이트",
  "role": "로컬 지식 관리 에이전트",
  "workspace_paths": [".", "/Users/ujunbin/knowledge"],
  "inputs": ["사용자 요청", "/Users/ujunbin/knowledge"],
  "outputs": ["갱신된 지식 DB", "검증된 지식 그래프"],
  "verification": ["변경 파일과 그래프 연결을 확인한다"],
  "constraints": ["근거 없이 지식을 만들지 않는다"],
  "operating_rules": ["필요한 최소 맥락만 읽는다"],
  "memory_rules": ["확정된 장기 맥락만 짧게 남긴다"],
  "initial_notes": ["시작 패킷 설명을 진입 파일에 남기지 않는다"],
  "bash": {
    "allow": ["rg *", "sed *"],
    "deny": ["rm *"]
  }
}
```

실행:

```bash
python .claude/skills/agent-clone-setup/scripts/init_agent_clone.py \
  --project-setup \
  --input agent-setup.json \
  --project-root . \
  --update-policy
```

`--update-policy`를 빼면 작업 경계 정책은 바꾸지 않습니다.

## User input

| 파일 | 역할 |
| --- | --- |
| `agent-setup.json` | 프로젝트 자체 초기 전환 입력 |
| `.claude/memory/memory.md` | 확정된 장기 맥락 |
| `.claude/memory/user_preferences.md` | 프로젝트 범위 선호 |
| `.claude/tasks/tasks.md` | 현재 작업 단위 |

## Auto-updated files

| 파일 | 갱신 조건 |
| --- | --- |
| `AGENTS.md` | `agent-clone-setup --project-setup` 실행 |
| `.claude/CLAUDE.md` | `agent-clone-setup --project-setup` 실행 |
| `.claude/policies/agent-workspace.json` | `--update-policy` 사용 |
| `.claude/skills/skills.md` | skill index hook 실행 |
| `.claude/agents/agents.md` | agent index hook 실행 |
| `.claude/memory/word.json` | `register-term` 사용 |

## Memory rule

`.claude/memory/`는 압축적으로 관리합니다.
확정된 장기 맥락만 남깁니다.
임시 로그, 진행상황, handoff, 대량 산출물은 `.claude/tasks/`나 `.context/`에 둡니다.

## Clone packet

subagent 또는 클론 작업자가 필요할 때만 `agent-clone-setup`을 `--project-setup` 없이 실행합니다.
그때만 `.context/agents/<agent_name>/bootstrap.md`가 생성됩니다.
