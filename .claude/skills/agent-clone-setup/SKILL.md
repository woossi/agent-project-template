---
name: agent-clone-setup
description: Use when cloning, spawning, or initializing a Claude subagent from provided role, scope, context, tool, output, and verification inputs; creates the required bootstrap packet and optional workspace policy entry for the cloned agent.
---

# 스킬: agent-clone-setup

## 사용 시점

에이전트를 복제하거나 새 subagent 세션을 시작하면서, 전달받은 입력으로 에이전트가 반드시 알아야 할 초기 설명 패킷을 만들어야 할 때 사용합니다.

## 목적

클론 에이전트에게 전달할 필수 설명을 누락 없이 고정하고, 입력값으로 `.context/agents/<agent_name>/` 초기 셋업을 생성합니다.

## 필수 입력

입력은 JSON 객체이며 아래 필드를 모두 포함해야 합니다.

- `agent_name`: 클론 에이전트 이름
- `source_agent`: 복제 기준이 되는 에이전트 또는 템플릿 이름
- `clone_purpose`: 이 클론을 만든 이유
- `role`: 클론 에이전트의 역할
- `task_objective`: 수행할 목표
- `inputs`: 읽거나 사용할 입력 목록
- `allowed_paths`: 접근 허용 경로 glob
- `tools`: 허용 도구 목록
- `outputs`: 기대 산출물
- `handoff_path`: 초기 셋업과 인수인계 파일을 둘 `.context/agents/<agent_name>` 경로
- `verification`: 결과 검증 기준
- `constraints`: 금지 사항과 제약

선택 필드:

- `denied_paths`: 명시 차단 경로 glob
- `initial_notes`: 시작 시 강조할 메모
- `bash`: `{ "allow": [...], "deny": [...] }`

## 강제 규약

- 필수 입력이 빠지면 초기화하지 않습니다.
- `handoff_path`는 프로젝트 내부 경로여야 합니다.
- 클론 에이전트에게 전달할 설명은 `bootstrap.md`에 모읍니다.
- 원본 입력은 정규화해 `clone-input.json`으로 보존합니다.
- 경로나 Bash 경계를 정책으로 반영해야 하면 `--update-policy`를 사용합니다.

## 실행

```bash
python .claude/skills/agent-clone-setup/scripts/init_agent_clone.py \
  --input clone-input.json \
  --project-root . \
  --update-policy
```

`--update-policy`는 `.claude/policies/agent-workspace.json`의 `agents.<agent_name>` 항목을 입력값으로 갱신합니다.

## 출력 형식

- `.context/agents/<agent_name>/bootstrap.md`
- `.context/agents/<agent_name>/clone-input.json`
- 선택: `.claude/policies/agent-workspace.json`의 agent boundary 항목

## 내부 자원

- `scripts/init_agent_clone.py` — 입력 검증, bootstrap 생성, 선택적 policy 갱신 스크립트
- `scripts/tests/test_init_agent_clone.py` — 스크립트 회귀 테스트

## 품질 점검

- 필수 입력 누락 시 exit code `2`
- 생성된 `bootstrap.md`에 역할, 목표, 입력, 경계, 산출물, 검증 기준이 모두 포함
- `--update-policy` 사용 시 agent 이름 아래 `allow`, `deny`, `bash`가 반영

## 자주 발생하는 실패 사례

- `handoff_path`가 프로젝트 밖을 가리킴 → `.context/agents/<agent_name>` 형태로 고칩니다.
- `allowed_paths`가 비어 있음 → 클론 에이전트가 읽을 최소 경계를 명시합니다.
- 검증 기준이 비어 있음 → 결과를 확인할 수 없으므로 초기화하지 않습니다.
