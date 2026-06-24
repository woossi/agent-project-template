---
name: agent-clone-setup
description: Use when initializing a local agent project — writing the agent-setup.json input and converting AGENTS.md and .claude/CLAUDE.md for that agent — or explicitly creating a cloned subagent bootstrap packet.
---

# 스킬: agent-clone-setup

## 사용 시점

아래 요청에는 이 스킬을 사용한다.

- GitHub 시작 패킷을 복사해 로컬 에이전트 프로젝트로 처음 전환할 때
- "이 프로젝트 자체를 에이전트로 만들기", "초기 진입 파일 맞추기", "문구 삭제하고 에이전트에 맞게 최적화"처럼 `AGENTS.md`와 `.claude/CLAUDE.md`를 재작성해야 할 때
- 전달받은 역할, 목표, 작업 경계, 입력, 산출물로 에이전트 초기 셋업을 고정해야 할 때
- 사용자가 명시적으로 클론 또는 subagent bootstrap 패킷을 요청할 때

기본 경로는 프로젝트 자체 초기 전환이다. `.context/agents/` 산출물은 사용자가 클론 또는 subagent를 분명히 요구한 경우에만 만든다.

## 목적

에이전트가 처음 실행될 때 반드시 알아야 할 역할, 목표, 작업 경계, 입력, 산출물, 검증 기준을 빠짐없이 고정한다.

## 프로젝트 자체 초기 전환 입력

`--project-setup` 모드는 입력 JSON을 stdin이나 `--input` 파일로 받아, 정규화한 정본을 `agent-setup.json`으로 **작성**하고 곧바로 진입 파일까지 전환한다. 입력 작성과 초기 전환이 한 번에 끝난다. 입력 JSON 객체는 아래 필드를 요구한다.

- `agent_name`: 에이전트 이름
- `agent_purpose`: 에이전트 목표
- `role`: 에이전트 역할
- `workspace_paths`: 작업 허용 경로. `.`는 자동 포함되며, 필요한 경우 `/Users/...` 절대 경로를 넣을 수 있다.
- `inputs`: 읽거나 사용할 입력
- `outputs`: 기대 산출물
- `verification`: 결과 검증 기준
- `constraints`: 금지 사항과 제약

선택 필드:

- `operating_rules`: 실행 규칙
- `memory_rules`: 장기 맥락 관리 규칙
- `tools`: 사용할 도구
- `denied_paths`: 명시 차단 경로
- `initial_notes`: 시작 시 강조할 메모
- `bash`: `{ "allow": [...], "deny": [...] }`

## 프로젝트 자체 초기 전환 실행

값을 stdin으로 넘기면 스킬이 `agent-setup.json`을 작성하고 전환까지 한 번에 끝낸다.

```bash
python .claude/skills/agent-clone-setup/scripts/init_agent_clone.py \
  --project-setup \
  --project-root . \
  --update-policy <<'JSON'
{
  "agent_name": "...",
  "agent_purpose": "...",
  "role": "...",
  "workspace_paths": ["..."],
  "inputs": ["..."],
  "outputs": ["..."],
  "verification": ["..."],
  "constraints": ["..."]
}
JSON
```

이미 `agent-setup.json`이 있으면 파일로 줄 수도 있다.

```bash
python .claude/skills/agent-clone-setup/scripts/init_agent_clone.py \
  --project-setup \
  --input agent-setup.json \
  --project-root . \
  --update-policy
```

출력:

- `agent-setup.json` (정규화된 입력 정본. `--no-save-input`이면 건너뛴다)
- `AGENTS.md`
- `.claude/CLAUDE.md`
- 선택: `.claude/policies/agent-workspace.json`의 기본 작업 경계

`--project-setup` 출력에는 시작 패킷, 중립성, 포크 같은 메타 설명을 남기지 않는다. 진입 파일은 실제 로컬 에이전트의 역할과 실행 규칙만 설명한다.

## 클론 bootstrap 입력

클론 또는 subagent를 명시적으로 만들 때만 아래 입력을 사용한다.

- `agent_name`: 클론 에이전트 이름
- `source_agent`: 복제 기준
- `clone_purpose`: 이 클론을 만든 이유
- `role`: 클론 에이전트의 역할
- `task_objective`: 수행할 목표
- `inputs`: 읽거나 사용할 입력 목록
- `allowed_paths`: 접근 허용 경로 glob. 절대 경로는 policy hook이 명시 허용 경계로 처리한다.
- `tools`: 허용 도구 목록
- `outputs`: 기대 산출물
- `handoff_path`: 초기 셋업과 인수인계 파일을 둘 프로젝트 내부 경로
- `verification`: 결과 검증 기준
- `constraints`: 금지 사항과 제약

선택 필드:

- `denied_paths`
- `initial_notes`
- `bash`: `{ "allow": [...], "deny": [...] }`

## 클론 bootstrap 실행

```bash
python .claude/skills/agent-clone-setup/scripts/init_agent_clone.py \
  --input clone-input.json \
  --project-root . \
  --update-policy
```

출력:

- `.context/agents/<agent_name>/bootstrap.md`
- `.context/agents/<agent_name>/clone-input.json`
- 선택: `.claude/policies/agent-workspace.json`의 `agents.<agent_name>` 경계

## 강제 규약

- 필수 입력이 빠지면 exit code `2`로 멈춘다.
- 프로젝트 자체 초기 전환은 입력을 `agent-setup.json`으로 작성한 뒤 `AGENTS.md`와 `.claude/CLAUDE.md`를 함께 갱신한다. `--no-save-input`일 때만 입력 작성을 건너뛴다.
- 클론 bootstrap에서 `handoff_path`는 프로젝트 내부 경로여야 한다.
- `--update-policy`를 쓸 때 정책 파일은 유효한 JSON이어야 한다.
- 원본 클론 입력은 `clone-input.json`으로 정규화해 보존한다.

## 내부 자원

- `scripts/init_agent_clone.py` — 프로젝트 초기 전환, 클론 bootstrap, 선택적 policy 갱신 스크립트
- `scripts/tests/test_init_agent_clone.py` — 스크립트 회귀 테스트

## 품질 점검

- 프로젝트 자체 초기 전환 후 `AGENTS.md`와 `.claude/CLAUDE.md`에 에이전트 이름, 역할, 목표, 작업 경계가 들어간다.
- 생성된 `AGENTS.md`는 `컴포넌트 계층 관계 (Tasks → Skills → Agents)` 섹션과 9단계 권한 순서(`.claude/policies/`·`.claude/agents/` 포함), `.claude/hooks/`·`.claude/policies/`를 포함한 파일 계약을 담는다.
- 생성된 `.claude/CLAUDE.md`는 `운영 원칙`과 `컴포넌트 관리` 섹션을 담는다.
- 프로젝트 자체 초기 전환은 `.context/agents/`를 만들지 않는다.
- 클론 bootstrap은 역할, 목표, 입력, 경계, 산출물, 검증 기준을 `bootstrap.md`에 모두 포함한다.
- `--update-policy` 사용 시 기본 경계 또는 agent 경계가 정책 파일에 반영된다.

## 자주 발생하는 실패 사례

- 프로젝트 자체 전환 요청을 subagent 생성으로 오해함 → `--project-setup`을 사용한다.
- 진입 파일에 시작 패킷 설명이 남음 → `AGENTS.md`와 `.claude/CLAUDE.md`를 에이전트 역할 중심으로 다시 생성한다.
- 외부 지식 루트가 필요한데 정책이 없음 → `workspace_paths`에 절대 경로를 넣고 `--update-policy`를 사용한다.
- 클론 `handoff_path`가 프로젝트 밖을 가리킴 → `.context/agents/<agent_name>` 형태로 고친다.
- 검증 기준이 비어 있음 → 결과를 확인할 수 없으므로 초기화하지 않는다.
