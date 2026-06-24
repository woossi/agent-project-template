# agent-project-template

로컬 에이전트 프로젝트를 시작할 때 복사해 쓰는 시작 패킷입니다.

## How to start

1. 이 폴더를 새 프로젝트 루트에 복사합니다.
2. `agent-clone-setup`을 `--project-setup`으로 실행하며 에이전트 정보를 stdin으로 넘깁니다. 스킬이 `agent-setup.json`을 작성하고 진입 파일까지 한 번에 전환합니다.
3. 생성된 `agent-setup.json`, `AGENTS.md`, `.claude/CLAUDE.md`를 확인합니다.
4. 장기 맥락은 `.claude/memory/`, 현재 작업은 `.claude/tasks/`, 임시 산출물은 `.context/`에 둡니다.

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
| `agent-setup.json` | 프로젝트 전환 입력. 비워 두면 스킬이 stdin 값으로 작성합니다 |

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
