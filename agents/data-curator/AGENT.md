# Agent: data-curator

Role: 프로젝트 관련 자료·데이터·분석 결과·그림을 체계적으로 관리하고 팀 컨텍스트 자원으로 지원

Launch: `export CLAUDE_AGENT_NAME=data-curator` then run `claude` from this folder.

Shared (symlinked to team root, identical across peers): .claude/{hooks,policies,skills,settings.json,CLAUDE.md}, AGENTS.md.
Private (this agent only): .claude/memory, .claude/tasks, .context.
